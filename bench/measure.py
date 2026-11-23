#!/usr/bin/env python3
"""Measure built JS/Go Tidy applications after checking their complete output.

Build both workspaces first; see GOPURS.md. Compilation of the small Go
measurement driver also finishes before timing. No compiler is rebuilt here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import tempfile
import time

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
GO_OUTPUT = ROOT / "bench-go/output"
GO_BINARY = ROOT / "bench-go/tidy-bench"
ITERATIONS = 10
EXPECTED_HASH = "c8f7710cf563c22508c32ced1e9bbd15a12f3ea547e88bee2410cd5dfbb3395e"
EXPECTED_BYTES = 14624
EXPECTED_CHECKSUM = 32412660080


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprints(go_artifacts):
    paths = {BENCH / "fixture.purs", Path(__file__).resolve(),
             BENCH / "measurement.go", BENCH / "measurement.mjs", BENCH / "run-js.mjs"}
    for folder, extensions in [(ROOT / "src", {".purs", ".go", ".js"}),
                               (BENCH / "src", {".purs", ".go", ".js"}),
                               (BENCH / "output", {".js"}),
                               (ROOT / "test/snapshots", {".input"})]:
        paths.update(path for path in folder.rglob("*") if path.is_file()
                     and path.suffix in extensions)
    for name in ["bench/spago.yaml", "bench/spago.lock", "bench-go/spago.yaml", "bench-go/spago.lock"]:
        path = ROOT / name
        if path.is_file(): paths.add(path)
    result = {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}
    for backend, (output, binary) in go_artifacts.items():
        prefix = "bench-go" if backend == "Go" else backend
        result[prefix + "/tidy-bench"] = digest(binary)
        for path in sorted(output.rglob("*")):
            if (path.is_file() and ".gopurs-cache" not in path.parts
                    and (path.suffix == ".go" or path.name in {"corefn.json", "go.mod", "go.sum"})):
                result[prefix + "/output/" + path.relative_to(output).as_posix()] = digest(path)
    return result


def prepare_go_driver(directory, output=GO_OUTPUT):
    directory.mkdir(parents=True, exist_ok=True)
    module = re.search(r"(?m)^module\s+(\S+)", (output / "go.mod").read_text()).group(1)
    symbols = {"Call_Main_formatOnce": [], "Main_Consume": []}
    for path in (output / "purescript").rglob("*.go"):
        content = path.read_text()
        for symbol, owners in symbols.items():
            if re.search(r"(?m)^func " + symbol + r"\(", content):
                owners.append(module + "/" + path.parent.relative_to(output).as_posix())
    if any(len(owners) != 1 for owners in symbols.values()):
        raise ValueError("Rebuild Go output: expected one formatter and UTF-8 consumer: " + repr(symbols))
    packages = {path: "p" + str(i) for i, path in enumerate(sorted({v[0] for v in symbols.values()}))}
    imports = [f'{alias} "{path}"' for path, alias in packages.items()]
    if (output / "purescript/init_all").is_dir():
        imports.append(f'_ "{module}/purescript/init_all"')
    source = (BENCH / "measurement.go").read_text().replace("// GOPURS_IMPORTS", "\n".join(imports))
    source = source.replace("FORMAT_CALL", packages[symbols["Call_Main_formatOnce"][0]] + ".Call_Main_formatOnce")
    source = source.replace("CONSUME_CALL", packages[symbols["Main_Consume"][0]] + ".Main_Consume")
    driver = directory / "main.go"
    driver.write_text(source)
    binary = directory / "measure-go"
    subprocess.run(["go", "build", "-mod=readonly", "-trimpath", "-o", str(binary), str(driver)],
                   cwd=output, env={**os.environ, "GOWORK": "off", "GOTOOLCHAIN": "local"}, check=True)
    return binary


def invoke(command, cwd=BENCH):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True, timeout=120)


def verification_cases():
    cases = [("fixture", (BENCH / "fixture.purs").read_bytes())]
    cases.extend((path.relative_to(ROOT).as_posix(), path.read_bytes())
                 for path in sorted((ROOT / "test/snapshots").rglob("*.input")))
    cases.extend([
        ("unicode-literals", 'module Unicode where\n\nmessage = "é λ 😀"\n'.encode()),
        ("nested-layout", ('module Layout where\n\nf x =\n  let\n'
                           '    a = case x of\n      true -> [ 1, 2 ]\n'
                           '      false -> []\n  in a\n').encode()),
        ("malformed", b"module Broken where\nvalue = (\n"),
    ])
    return cases


def verify(go_drivers, directory):
    commands = {"JS": ["node", "--stack-size=4000", str(BENCH / "measurement.mjs")]}
    commands.update({backend: [str(driver)] for backend, driver in go_drivers.items()})
    cases = []
    input_file = directory / "verify-input.purs"
    for name, source in verification_cases():
        input_file.write_bytes(source)
        outputs, checks = {}, {}
        for backend, command in commands.items():
            destination = directory / (backend + ".purs")
            process = invoke(command + ["verify", str(input_file), str(destination)])
            checks[backend] = json.loads(process.stdout)
            outputs[backend] = destination.read_bytes()
        output = outputs["JS"]
        if any(value != output for value in outputs.values()) or any(
                value != checks["JS"] for value in checks.values()):
            raise ValueError("Outputs or consumption checksums differ on " + name)
        checksum = 2166136261
        for byte in output: checksum = ((checksum ^ byte) * 16777619) & 0xffffffff
        if checks["JS"] != {"bytes": len(output), "checksum": checksum}:
            raise ValueError("Independent UTF-8 consumption check failed on " + name)
        cases.append({"name": name, "input_sha256": hashlib.sha256(source).hexdigest(),
                      "output_bytes": len(output), "output_sha256": hashlib.sha256(output).hexdigest(),
                      "checksum": checksum})
    fixture = cases[0]
    if (fixture["output_bytes"] != EXPECTED_BYTES or fixture["output_sha256"] != EXPECTED_HASH
            or fixture["checksum"] * ITERATIONS != EXPECTED_CHECKSUM):
        raise ValueError("Output no longer matches the versioned fixture oracle")
    if cases[-1]["output_bytes"] or any(not case["output_bytes"] for case in cases[:-1]):
        raise ValueError("Expected nonempty formatted valid inputs and rejected malformed input")
    return {"bytes": EXPECTED_BYTES, "sha256": EXPECTED_HASH,
            "checksum_per_iteration": fixture["checksum"], "iterations": ITERATIONS,
            "checksum": EXPECTED_CHECKSUM, "identical": True, "backends": list(commands),
            "cases": cases,
            "scope": "Main.formatOnce with benchmark options on all snapshot inputs; "
                     "does not execute snapshot-specific formatting directives"}


def runtime(backend, go_artifacts):
    command = (["node", "--stack-size=4000", "run-js.mjs"] if backend == "JS" else [str(go_artifacts[backend][1])])
    cwd = BENCH if backend == "JS" else ROOT / "bench-go"
    start = time.perf_counter_ns()
    process = invoke(command, cwd)
    seconds = (time.perf_counter_ns() - start) / 1e9
    checksum = float(process.stdout.strip())
    if not math.isfinite(checksum) or checksum != EXPECTED_CHECKSUM:
        raise ValueError("Wrong benchmark checksum; rebuild both applications: " + process.stdout)
    return {"backend": backend, "seconds": seconds, "checksum": checksum}


def allocations(backend, driver):
    fixture = str(BENCH / "fixture.purs")
    command = (["node", "--stack-size=4000", "--expose-gc", "--trace-gc-nvp",
                str(BENCH / "measurement.mjs"), "allocations", fixture] if backend == "JS"
               else [str(driver), "allocations", fixture])
    process = invoke(command)
    row = json.loads(process.stdout.strip().splitlines()[-1])
    if row["checksum"] != EXPECTED_CHECKSUM: raise ValueError("Wrong allocation-run checksum")
    if backend == "JS":
        region = process.stdout.split("ALLOC_BEGIN\n", 1)[1].split("\nALLOC_END", 1)[0]
        values = [int(value) for value in re.findall(r"\ballocated=(\d+)", region)]
        if not values or any(value >= 2**63 for value in values):
            raise ValueError("V8 heap-size trace is missing or wrapped; do not publish an allocation estimate")
        row.update(v8_heap_allocation_estimate_bytes=sum(values), gc_events=len(values),
                   utf8_buffer_payload_bytes=EXPECTED_BYTES * ITERATIONS)
    row["backend"] = backend
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=18, help="runs per backend (default 18)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before-go-output", type=Path,
                        help="Generated Go output from the uncorrected frontend")
    parser.add_argument("--before-go-binary", type=Path,
                        help="Executable built from --before-go-output")
    args = parser.parse_args()
    if bool(args.before_go_output) != bool(args.before_go_binary):
        parser.error("--before-go-output and --before-go-binary must be provided together")
    comparing = args.before_go_output is not None
    multiple = 6 if comparing else 2
    if args.runs < multiple or args.runs % multiple:
        parser.error("--runs must be a positive multiple of " + str(multiple))
    go_artifacts = {"Go": (GO_OUTPUT, GO_BINARY)}
    if comparing:
        go_artifacts["Go_before"] = (args.before_go_output.resolve(), args.before_go_binary.resolve())
    for output, binary in go_artifacts.values():
        if not (output / "Main/corefn.json").is_file() or not binary.is_file():
            parser.error("Missing generated Main/corefn.json or executable: " + str(output))
    backends = ["JS", *go_artifacts]
    orders = list(itertools.permutations(backends))
    with tempfile.TemporaryDirectory(prefix="tidy-measure-") as temporary:
        directory = Path(temporary)
        sources = fingerprints(go_artifacts)
        go_drivers = {backend: prepare_go_driver(directory / backend, output)
                      for backend, (output, _) in go_artifacts.items()}
        checked = verify(go_drivers, directory)
        print("Complete outputs verified; beginning runtime measurements", flush=True)
        warmups = [runtime(backend, go_artifacts) for backend in backends]
        runs = []
        for round_index in range(args.runs):
            for position, backend in enumerate(orders[round_index % len(orders)]):
                row = runtime(backend, go_artifacts)
                row.update(round=round_index + 1, position=position + 1)
                runs.append(row)
        print("Runtime complete; beginning separate allocation measurements", flush=True)
        allocation_runs = []
        for round_index in range(3):
            order = (backends[round_index:] + backends[:round_index]) if comparing else (
                backends if round_index % 2 == 0 else list(reversed(backends)))
            for backend in order:
                row = allocations(backend, go_drivers.get(backend))
                row["round"] = round_index + 1
                allocation_runs.append(row)
        if sources != fingerprints(go_artifacts):
            raise ValueError("Sources or built payloads changed during measurement")
        medians = {backend: statistics.median(row["seconds"] for row in runs if row["backend"] == backend)
                   for backend in backends}
        runtime_summary = {backend: {
            "min_seconds": min(row["seconds"] for row in runs if row["backend"] == backend),
            "max_seconds": max(row["seconds"] for row in runs if row["backend"] == backend),
            "median_seconds": medians[backend], "runs": args.runs} for backend in backends}
        allocation_medians = {}
        for backend in backends:
            keys = (["v8_heap_allocation_estimate_bytes", "gc_events", "utf8_buffer_payload_bytes"]
                    if backend == "JS" else ["total_alloc_bytes", "mallocs", "num_gc"])
            allocation_medians[backend] = {
                key: statistics.median(row[key] for row in allocation_runs if row["backend"] == backend)
                for key in keys}
        frontends = {"JS": (BENCH / "output/Main/index.js").read_text().splitlines()[0]}
        frontends.update({backend + "_TAST": json.loads((output / "Main/corefn.json").read_text())["builtWith"]
                          for backend, (output, _) in go_artifacts.items()})
        report = {"schema": "tidy-runtime-v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                  "host": {"system": platform.platform(), "machine": platform.machine(), "logical_cpus": os.cpu_count()},
                  "versions": {name: invoke(command).stdout.strip() for name, command in
                               {"node": ["node", "--version"], "go": ["go", "version"]}.items()},
                  "frontends": frontends,
                  "protocol": {"iterations_per_process": ITERATIONS, "runs_per_backend": args.runs,
                               "timing": "whole process including startup; Main.main formats and consumes all UTF-8 bytes",
                               "order": "all frontend permutations repeated; one excluded warmup per backend; no sample exclusions",
                               "allocation_order": "three cyclic backend rotations" if comparing else "alternating JS/Go and Go/JS",
                               "allocations": "three separate runs around formatOnce + consume, excluding input/output I/O",
                               "JS_allocation_method": "estimated V8 heap-size growth between GCs, bracketed by forced GCs; external UTF-8 buffer payload reported separately; not exact Go TotalAlloc equivalence",
                               "gc_environment": {key: os.environ.get(key) for key in ["GOGC", "GOMEMLIMIT", "GOMAXPROCS", "GODEBUG", "NODE_OPTIONS"]}},
                  "sources_sha256": sources, "correctness": checked, "warmups": warmups,
                  "runtime_runs": runs, "runtime_median_seconds": medians, "runtime_summary": runtime_summary,
                  "Go_over_JS": medians["Go"] / medians["JS"],
                  "allocation_runs": allocation_runs, "allocations_median": allocation_medians}
        if comparing:
            before = allocation_medians["Go_before"]
            after = allocation_medians["Go"]
            report["before_after"] = {
                "runtime_after_over_before": medians["Go"] / medians["Go_before"],
                "runtime_reduction_percent": 100 * (1 - medians["Go"] / medians["Go_before"]),
                "allocated_bytes_after_over_before": after["total_alloc_bytes"] / before["total_alloc_bytes"],
                "allocated_bytes_reduction_percent": 100 * (1 - after["total_alloc_bytes"] / before["total_alloc_bytes"]),
                "mallocs_after_over_before": after["mallocs"] / before["mallocs"],
                "mallocs_reduction_percent": 100 * (1 - after["mallocs"] / before["mallocs"]),
                "Go_before_over_JS": medians["Go_before"] / medians["JS"],
                "Go_after_over_JS": medians["Go"] / medians["JS"],
            }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"runtime_median_seconds": medians, "Go_over_JS": report["Go_over_JS"],
                          "allocations_median": allocation_medians,
                          **({"before_after": report["before_after"]} if comparing else {})}, indent=2))
        print("Saved", args.output)


if __name__ == "__main__":
    main()
