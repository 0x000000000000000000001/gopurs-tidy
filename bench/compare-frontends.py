#!/usr/bin/env python3
"""Compare three already-built JavaScript Tidy applications.

Compilation must finish before starting this script. Each timed process runs
the same Main.main: ten complete parse/format/UTF-8-consume iterations. The
compiled output directories must contain the same bench/src/Main.purs build.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import time

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
LABELS = ("before", "after", "official")
EXPECTED_BYTES = 14624
EXPECTED_SHA256 = "c8f7710cf563c22508c32ced1e9bbd15a12f3ea547e88bee2410cd5dfbb3395e"
EXPECTED_HASH = 3241266008
EXPECTED_SUM = EXPECTED_HASH * 10
MAIN_PROGRAM = "const { main } = await import(process.argv[1]); main();"
VERIFY_PROGRAM = r"""
import fs from 'node:fs';
const { formatOnce, consume } = await import(process.argv[1]);
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map(({ name, source }) => {
  const output = formatOnce(source);
  if (!output.isWellFormed()) throw new Error('Invalid Unicode in ' + name);
  const bytes = Buffer.from(output, 'utf8');
  return { name, output: bytes.toString('base64'), checksum: consume(output) };
});
console.log(JSON.stringify(results));
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(node, output, program):
    return [node, "--stack-size=4000", "--input-type=module", "--eval", program,
            (output / "Main/index.js").as_uri()]


def invoke(args, input_text=None):
    return subprocess.run(args, cwd=BENCH, input=input_text, text=True,
                          capture_output=True, check=True, timeout=120)


def sources():
    paths = {Path(__file__).resolve(), BENCH / "fixture.purs"}
    for folder in (ROOT / "src", BENCH / "src", BENCH / ".spago/p"):
        paths.update(path for path in folder.rglob("*") if path.is_file()
                     and path.suffix in {".purs", ".js"})
    paths.update((ROOT / "test/snapshots").rglob("*.input"))
    for filename in ("spago.yaml", "spago.lock"):
        for folder in (ROOT, BENCH):
            if (folder / filename).is_file():
                paths.add(folder / filename)
    return paths


def fingerprints(outputs):
    result = {"sources": {str(path.relative_to(ROOT)): digest(path)
                          for path in sorted(sources())}}
    for label, output in outputs.items():
        result[label] = {str(path.relative_to(output)): digest(path)
                         for path in sorted(output.rglob("*")) if path.is_file()
                         and (path.suffix == ".js" or path.name == "package.json")}
    return result


def verification_cases():
    cases = [{"name": "fixture", "source": (BENCH / "fixture.purs").read_text()}]
    cases.extend({"name": str(path.relative_to(ROOT)), "source": path.read_text()}
                 for path in sorted((ROOT / "test/snapshots").rglob("*.input")))
    cases.extend([
        {"name": "unicode-literals", "source":
         'module Unicode where\n\nmessage = "é λ 😀"\n'},
        {"name": "nested-layout", "source":
         'module Layout where\n\nf x =\n  let\n    a = case x of\n'
         '      true -> [ 1, 2 ]\n      false -> []\n  in a\n'},
        {"name": "malformed", "source": "module Broken where\nvalue = (\n"},
    ])
    return cases


def verify(node, outputs):
    import base64

    cases = verification_cases()
    results = {label: json.loads(invoke(command(node, output, VERIFY_PROGRAM),
                                       json.dumps(cases)).stdout)
               for label, output in outputs.items()}
    reference = results["official"]
    if any(value != reference for value in results.values()):
        failures = [case["name"] for index, case in enumerate(cases)
                    if any(result[index] != reference[index] for result in results.values())]
        raise ValueError("Frontend outputs differ: " + ", ".join(failures))
    checks = []
    if len(reference) != len(cases):
        raise ValueError("Verification did not return every input case")
    for case, result in zip(cases, reference):
        data = base64.b64decode(result["output"], validate=True)
        fnv = 2166136261
        for byte in data:
            fnv = ((fnv ^ byte) * 16777619) & 0xffffffff
        if fnv != result["checksum"]:
            raise ValueError("UTF-8 consumption differs from independent FNV: " + case["name"])
        checks.append({"name": case["name"], "input_sha256": hashlib.sha256(
            case["source"].encode()).hexdigest(), "output_bytes": len(data),
            "output_sha256": hashlib.sha256(data).hexdigest(), "checksum": fnv})
    fixture = checks[0]
    if (fixture["output_bytes"], fixture["output_sha256"], fixture["checksum"]) != (
            EXPECTED_BYTES, EXPECTED_SHA256, EXPECTED_HASH):
        raise ValueError("Fixture no longer matches the recorded output oracle")
    if checks[-1]["output_bytes"] != 0:
        raise ValueError("Malformed input should be rejected by formatOnce")
    if not all(case["output_bytes"] for case in checks[-3:-1]):
        raise ValueError("Additional valid Unicode/layout input was rejected")
    return {"exact_bytes_equal": True, "cases": checks,
            "nonempty_cases": sum(case["output_bytes"] > 0 for case in checks),
            "empty_cases": [case["name"] for case in checks if not case["output_bytes"]],
            "scope": "Main.formatOnce with benchmark options on all snapshot inputs; "
                     "does not execute snapshot-specific formatting directives"}


def timed_main(node, output):
    start = time.perf_counter_ns()
    process = invoke(command(node, output, MAIN_PROGRAM))
    elapsed = (time.perf_counter_ns() - start) / 1e9
    # Float accepts PureScript's optional '.0' suffix without weakening the oracle.
    if float(process.stdout.strip()) != EXPECTED_SUM:
        raise ValueError("Timed Main.main returned an unexpected checksum: " + process.stdout)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for label in LABELS:
        parser.add_argument("--" + label, required=True, type=Path,
                            help="Compiled JS output directory for " + label)
    parser.add_argument("--runs", type=int, default=18,
                        help="Runs per frontend, a positive multiple of six (default: 18)")
    parser.add_argument("--output", required=True, type=Path, help="JSON report destination")
    args = parser.parse_args()
    if args.runs <= 0 or args.runs % 6:
        parser.error("--runs must be a positive multiple of six for balanced order")
    outputs = {label: getattr(args, label).resolve() for label in LABELS}
    for output in outputs.values():
        if not (output / "Main/index.js").is_file():
            parser.error("Missing compiled Main/index.js in " + str(output))
    node = shutil.which("node")
    if not node:
        parser.error("node is not on PATH")
    initial = fingerprints(outputs)
    validation = verify(node, outputs)
    warmups = {label: timed_main(node, output) for label, output in outputs.items()}
    samples = []
    orders = list(itertools.permutations(LABELS)) * (args.runs // 6)
    for round_index, order in enumerate(orders):
        for position, label in enumerate(order):
            elapsed = timed_main(node, outputs[label])
            samples.append({"round": round_index + 1, "position": position + 1,
                            "frontend": label, "seconds": elapsed})
    if fingerprints(outputs) != initial:
        raise RuntimeError("Sources or generated JavaScript changed during the campaign")
    summaries = {}
    for label in LABELS:
        values = [sample["seconds"] for sample in samples if sample["frontend"] == label]
        summaries[label] = {"runs": len(values), "median_seconds": statistics.median(values),
                            "min_seconds": min(values), "max_seconds": max(values)}
    before, after, official = (summaries[label]["median_seconds"] for label in LABELS)
    baseline = 0.281233479
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {"iterations_per_process": 10, "full_utf8_consumption": True,
                     "timing": "Fresh process wall time, including imports and fixture read",
                     "driver": MAIN_PROGRAM, "node_flags": ["--stack-size=4000"],
                     "runs_per_frontend": args.runs, "warmups_per_frontend": 1,
                     "order": "All six frontend permutations, repeated in order",
                     "excluded_samples": "One warm-up per frontend only; no outlier removal",
                     "expected_checksum_per_process": EXPECTED_SUM},
        "environment": {"node": invoke([node, "--version"]).stdout.strip(),
                        "node_sha256": digest(Path(node).resolve()),
                        "platform": platform.platform(), "machine": platform.machine(),
                        "NODE_OPTIONS": os.environ.get("NODE_OPTIONS")},
        "compiler_headers": {label: (output / "Main/index.js").read_text().splitlines()[0]
                             for label, output in outputs.items()},
        "verification": validation, "summaries": summaries,
        "comparison": {"after_over_before": after / before,
                       "runtime_reduction_percent": 100 * (1 - after / before),
                       "before_over_official": before / official,
                       "after_over_official": after / official},
        "historical_reference": {"source": "altbak.pub/README.md application benchmark; "
                                 "application-2026-11-22.json",
                                 "official_js_median_seconds": baseline,
                                 "current_official_over_historical": official / baseline,
                                 "note": "Historical run used run-js.mjs rather than --eval; "
                                         "causal comparison uses the three current builds."},
        "warmup_seconds": warmups, "samples": samples, "fingerprints": initial,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"summaries": summaries, "comparison": report["comparison"],
                      "verified_cases": len(validation["cases"]),
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
