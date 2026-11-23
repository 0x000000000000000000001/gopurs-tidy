# gopurs port and benchmark

This branch makes `purescript-tidy` build with the
[gopurs](https://github.com/0x000000000000000000001/gopurs) Go backend.

## Layout

The Go build expects the gopurs checkout and its library ports next to this
repository:

```text
htdocs/
├── gopurs/
│   ├── gopurs/          # compiler checkout
│   ├── gopurs-arrays/
│   ├── gopurs-strings/
│   └── ...
└── gopurs-tidy/
    ├── bench/           # JavaScript benchmark
    └── bench-go/        # Go benchmark (gopurs overrides)
```

`bench-go/spago.yaml` selects the gopurs ports with `workspace.extraPackages`.
`bench/src` is shared by both workspaces through a symlink.

## Prerequisites

- Spago 1.0.3, the official PureScript compiler for `bench/`, and the typed
  PureScript fork for `bench-go/`. Select the appropriate `purs` through `PATH`.
- Node.js 24 and Go 1.27.
- A built `gopurs` compiler checkout (`gopurs/bin/gopurs`).

## JavaScript benchmark

```bash
cd bench
spago build
node --stack-size=4000 run-js.mjs
```

## Go benchmark

```bash
cd bench-go
spago build
node ../../gopurs/gopurs/tools/library-go-dependencies.mjs output ../../gopurs/gopurs-strings
../../gopurs/gopurs/bin/gopurs --main Main
(cd output && GOWORK=off GOPROXY=off GOTOOLCHAIN=local go build -mod=readonly -trimpath -o ../tidy-bench ./main)
./tidy-bench
```

The fixture is `bench/fixture.purs` (a copy of `src/Tidy/Doc.purs`, 514
lines). `Main` parses and formats it ten times with `pageWidth: 80`, consumes
every UTF-8 byte with FNV-1a32, and prints the sum of the ten hashes:
`32412660080` (a trailing `.0` is equivalent). The sum uses `Number`, which
represents these integers exactly, to avoid a 32-bit `Int` overflow. JavaScript
encodes the result with `Buffer.from`; Go reads its native UTF-8 string. The JS
run needs `--stack-size=4000` for this fixture with Node 24.

## Reproduce the application measurement

After both builds finish, run from the repository root:

```bash
python3 bench/measure.py --runs 18 --output bench/results/application-repeat.json
```

The harness verifies the full formatted output against a fixed oracle before
timing: 14,624 bytes with SHA-256
`c8f7710cf563c22508c32ced1e9bbd15a12f3ea547e88bee2410cd5dfbb3395e`.
It runs the actual `Main.main` applications in alternating JS/Go and Go/JS
order, excludes one warmup per backend and retains every timed sample. Each
sample includes process startup and ten complete format-and-consume iterations.
It does not measure compilation time or update the compiler.

Three separate allocation runs measure the same formatting and consumption,
with fixture loading and output I/O outside the counters. Go uses `TotalAlloc`
and `Mallocs`; JS sums V8's `allocated=` GC trace estimates, bracketed by forced
GCs, and reports the UTF-8 buffer payload separately. These are cumulative
allocations, not live memory or peak RSS. The V8 estimate is not an exact
equivalent of Go's counter; an invalid wrapped trace is rejected. No GC
instrumentation is enabled during runtime measurements.

The report records raw samples, output checks, tool versions and source/payload
hashes, and rejects changes to those inputs during the campaign. Temporary
measurement-driver builds are automatically removed. Do not run other builds
while measuring.

The application is named
[purescript-tidy](https://github.com/natefaubion/purescript-tidy) in
[altbak.pub's application tables](../altbak.pub/README.md#application-benchmark-results).
Its process-level measurements are separate from the core/extended microbenchmark
totals. The results below preserve the earlier length-only optimization history.

The current campaign measures **289.06 ms** for official JavaScript and
**621.78 ms** for Go rebuilt with the corrected typed fork 0.15.17
(**2.15×** Go/JS) per ten format-and-consume iterations. The complete outputs
match. Cumulative allocations are approximately **817 MB** on the V8 heap
(an estimate, plus 146,240 bytes of UTF-8 buffer payload) and **1,064 MB** via
Go's exact `TotalAlloc` counter. The
[current report](bench/results/typeapp-go-2026-11-22.json) includes both Go
versions, all samples, output checks and source hashes.

The [earlier application campaign](bench/results/application-2026-11-22.json)
used the typed fork 0.15.16 for Go: **281.23 ms** for official JS,
**550.39 ms** for Go and approximately **940 MB** of Go allocations. Those
historical measurements are retained; they are not the before baseline of
the controlled 0.15.17 comparison below.

## Go after the TypeApp correction — 22 November 2026

Both Go variants use the same 0.15.17 fork sources based on
`c68a1b08706507f3bba9420d943a1a8614dc20da`, with only the optimizer correction
differing, and the same gopurs compiler and application inputs. Each variant
was regenerated in the canonical `bench-go` workspace from fresh frontend
output, preserving identical source paths. The current official JavaScript
reference uses PureScript 0.15.15.

| Go frontend | Median runtime | Allocated bytes | Allocations |
| --- | ---: | ---: | ---: |
| Before TypeApp correction | 586.45 ms | 965,186,304 | 20,587,242 |
| After TypeApp correction | 621.78 ms | 1,063,512,040 | 22,908,396 |

On Go this change increases runtime by **6.02%**, allocated bytes by **10.19%**
and allocation count by **11.27%**. The Go/official-JS ratio moves from
**2.03×** to **2.15×**. This is a measured regression for this workload;
the campaign does not include a CPU profile establishing its internal cause.

There are 18 runtime samples per variant, cycling through all six orders of
JS, Go before and Go after. One warmup per variant is excluded; all timed
samples are retained. Three separate allocation runs per variant use cyclic
order. Outputs match byte for byte on all 35 verification inputs, including
Unicode and layout examples and the expected empty result for malformed input.

For reproduction, preserve compiler executables from the same fork revision
before and after the correction. Build the before variant from a fresh output
directory using the Go procedure above, then move its output and binary aside:

```bash
tidy_before=$(mktemp -d)
mv bench-go/output "$tidy_before/output"
mv bench-go/tidy-bench "$tidy_before/tidy-bench"
```

Rebuild the canonical `bench-go` workspace with the corrected compiler, using
the same application sources, dependency source list and gopurs executable.
Run `library-go-dependencies.mjs` before invoking gopurs: a fresh build needs
its Go module dependencies available during generation. Rebuild `bench/`
with the official compiler, finish all builds, then run from the repository root:

```bash
python3 bench/measure.py --runs 18 \
  --before-go-output "$tidy_before/output" \
  --before-go-binary "$tidy_before/tidy-bench" \
  --output bench/results/typeapp-go-repeat.json
rm -rf "$tidy_before"
```

The report retains the baseline fingerprints and measurements after the
baseline workspace is removed. The harness removes its own temporary drivers.

## Typed-fork JavaScript correction — 22 November 2026

The CoreFn optimizer now recognizes `Data.Function.apply` and `applyFlipped`
through `TypeApp` wrappers while preserving the retained operands and result
type annotations. This restores optimizations such as Dodo's tail-call loop.
The before/after pair uses the current typed fork **0.15.17**, based on
`c68a1b08706507f3bba9420d943a1a8614dc20da`, without and with this correction.
The official comparison uses **0.15.15**. The older installed 0.15.16 fork is
not the before reference for this experiment.

| JavaScript frontend | Median runtime |
| --- | ---: |
| Typed fork before correction | 344.35 ms |
| Typed fork after correction | **274.22 ms** |
| Official compiler | 272.96 ms |

The correction reduces runtime by **20.37%**. The corrected fork's median is
**0.46%** above the official compiler's, placing them close together in this
campaign. All three builds format the same fixture ten times and consume the
complete UTF-8 output. Each frontend has 18 fresh-process samples, balanced
across all six execution orders, plus one excluded warmup. Process startup,
module loading and input reading are included; compilation and validation run
outside the timings. Node is 24.8.0 with `--stack-size=4000`.

The full output matches byte for byte on 35 inputs: the benchmark fixture,
31 snapshot inputs, Unicode and nested-layout examples, and a malformed input
whose expected result is empty. Snapshot inputs use the benchmark's default
formatting options; this comparison does not execute their individual
formatting directives. Every timed process returns checksum `32412660080`.
The [report](bench/results/typeapp-js-2026-11-22.json) retains raw samples,
output checks and source/generated-code fingerprints.

The historical official-JS reference of **281.23 ms** belongs to the
previous 0.15.16 JS/Go campaign. Its driver uses `run-js.mjs`; this three-way comparison
uses an identical `--eval` driver for all frontends. The official-JS
measurement in this JS-only experiment is about 2.9% lower than that historical
reference. The later Go rebuild campaign above provides the current published
JS/Go application table.

To reproduce, first preserve a compiler executable built before the correction,
then build the corrected compiler from the same checkout. Compile all three
variants from the same Spago source list into fresh directories. From this
repository, substitute the four absolute paths below:

```bash
cd bench
python3 - /path/to/purs-before /path/to/purs-after /path/to/official-purs /tmp/tidy-frontends <<'PY'
import json
from pathlib import Path
import subprocess
import sys

sources = json.loads(subprocess.run(
    ["spago", "sources", "--offline", "--json"],
    check=True, capture_output=True, text=True).stdout)
destination = Path(sys.argv[4]).resolve()
for label, compiler in zip(("before", "after", "official"), sys.argv[1:4]):
    output = destination / label
    if output.exists():
        raise SystemExit("Choose fresh output directories: " + str(output))
    subprocess.run([compiler, "compile", *sources, "-o", str(output),
                    "-g", "js,corefn", "+RTS", "-N4", "-RTS"], check=True)
PY
cd ..
python3 bench/compare-frontends.py \
  --before /tmp/tidy-frontends/before \
  --after /tmp/tidy-frontends/after \
  --official /tmp/tidy-frontends/official \
  --runs 18 --output bench/results/typeapp-js-repeat.json
```

Run the [comparison harness](bench/compare-frontends.py) after all builds have
finished, with no other builds running. It verifies outputs before timing and
rejects source or generated-JavaScript changes during the campaign.

## First results

Same fixture and iteration count on both sides; checksums are identical
(`146240`). Median of 7 warm runs:

| Backend | Median |
| --- | ---: |
| JavaScript (typed PureScript fork 0.15.16, Node 24) | 0.397 s |
| Go (gopurs release, Go 1.27) | 1.063 s |

Go is about **2.68×** slower than JavaScript on this formatter workload. This
is the initial length-only measurement, retained here as historical context.

## Integrated runtime improvements — 22 November 2026

The compiler now retains existing boxed composites until a native consumer
requires conversion, returns instantiated Tuple payloads from native workers,
shares literal record keys, and stores two-Int records compactly. Tidy uses
`Tidy.Printer.plainText`: persistent fragments on Go, a String buffer on JS.
These changes are in source; the measured Go was regenerated by the rebuilt
native compiler without editing generated Go.

Apple M4 Pro, Go 1.27.0, Node 24.8.0; same fixture and ten iterations as above.
Medians of 12 warm runs per variant, balanced execution order, one excluded
warmup each, no outliers removed. No builds ran during measurement. The JS
reference is the original compiled output, frozen before integration. Its
generated module headers identify the typed PureScript fork 0.15.16; these
historical figures are not measurements of the official 0.15.15 compiler used
by the current application benchmark.

| Variant | Runtime | Allocated bytes | Allocations |
| --- | ---: | ---: | ---: |
| Original Go, remeasured | 0.957 s | 2,268,389,760 | 31,865,485 |
| Last temporary prototype | 0.651 s | 1,115,960,536 | 23,601,934 |
| Integrated Go | **0.559 s** | **943,138,432** | **20,148,504** |
| Original JavaScript | 0.377 s | — | — |

The integrated version reduces runtime by **41.5%**, allocated bytes by
**58.4%**, and allocation count by **36.8%** versus the original Go measured
in the same campaign. It also reduces runtime by **14.0%** versus the last
temporary prototype: the generic conversion rules remove additional redundant
conversions beyond its exact patches. Allocation counters are medians of three
separate runs around the ten iterations; they measure cumulative allocation,
not peak or retained memory. GC settings use Go defaults.

In this historical campaign, Go was **1.48× slower than JS** (2.54× for the original
Go in this campaign; the historical initial result was 2.68×). This is progress
toward runtime parity, not a parity result. The official
[altbak.pub baselines](../altbak.pub/README.md) cover different workloads
(stable Go total 10.25 ms versus JS 129.10 ms); those totals cannot establish
Tidy parity. The application row is separate from those microbenchmark totals.

Outputs match byte for byte across all three Go variants on nine source files.
The main fixture and 16 extra cases also match the frozen JS reference. Six
malformed cases check the empty `formatOnce` result, not diagnostic text.
The fixture output remains 14,624 bytes, checksum `146240` over ten iterations.
Tidy's full tests/snapshots, focused compiler/runtime tests (including race
checks), eight Release fixtures and two Dev fixtures pass. This is targeted
validation; the full compiler qualification campaign was not rerun.

[Raw runs, allocation counters and output hashes](bench/results/runtime-2026-11-22.json)
record the protocol and binary identities. Compilation time is outside this
optimization campaign.

## Compilation times

Measured on the same checkout with `spago` 1.0.3 and the typed `purs` fork.
These are indicative only: the JavaScript number includes parsing,
type-checking and JS code generation, while the gopurs numbers are the
backend's own `[gopurs] backend total` (frontend excluded).

| Step | Time |
| --- | ---: |
| JavaScript `spago build` (273 modules) | 4.04 s |
| gopurs backend, release | 14.88 s |
| gopurs backend, `--dev` | 9.68 s |

The Go columns match the altbak.pub compilation table's protocol; integrating
this row would require a matched frontend/backend measurement campaign.
