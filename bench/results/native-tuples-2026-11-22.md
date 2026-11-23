# Generic native Tuple construction experiment — 22 November 2026

The temporary compiler correction improves Tidy runtime by 6.70%, allocated
bytes by 12.73% and allocation count by 14.25% relative to the current compiler.
It is not integrated into production gopurs. The original compiler/fork sources
and published altbak.pub application table remain unchanged.

## Correction

TypedExprs already computes the native Tuple pointer required by the annotated
result, but did not forward that representation to constructor translation.
AdtExprs consequently constructed boxed Tuple fields, followed by a conversion
back to the native layout. For composite fields this traverses and allocates
records, lists and arrays unnecessarily.

The temporary correction forwards the already-selected native representation
only to a freshly constructed canonical Tuple. AdtExprs checks the expected
pointer identity and instantiated type arguments, then constructs that pointer
with its native fields directly. Source types, field evaluation order and the
fallback ABI are preserved. There is no mutation, ownership inference, unsafe
cast or TAST erasure. The exact two-source-file patch and new tests are archived.

The regenerated insertDefault worker has zero Rebox calls and zero boxed Tuple
constructions, down from five and two respectively. This reproduces the effect
of the previous two-site manual patch, and also applies to other constructions.
A first attempt changed AdtExprs alone but missed these sites; a focused pipeline
test demonstrated the missing expected-type propagation and now covers it.

The unmodified compiler was first run with the same JavaScript host used for
the temporary compiler. All nine generated Go files matched the usual native
compiler host byte for byte, eliminating the host as a code-generation confound.

## Runtime and allocations

Each fresh process runs Main.main: ten formatting operations followed by full
UTF-8 output consumption, including process startup. Medians use 24 samples per
variant, all 24 execution orders, one excluded warm-up and no outlier removal.
Three separate allocation-counter runs follow timing. No build or profiler ran
alongside the timing campaign. Node 24.8.0 and Go 1.27.0 use default GC settings.

| Variant | Median runtime | Allocated bytes | Allocation count |
| --- | ---: | ---: | ---: |
| Current Go compiler | 616.05 ms | 1,063,289,952 | 22,908,345 |
| Previous manual two-site prototype | 596.45 ms | 1,004,262,728 | 21,526,054 |
| Generic compiler correction | 574.78 ms | 927,889,952 | 19,642,916 |
| Official JavaScript | 291.02 ms | ~817,981,336 heap + 146,240 buffer payload | — |

The generic correction is faster than current Go in all 24 paired rounds.
Relative to the manual prototype it reduces runtime by another 3.63%, allocated
bytes by 7.60% and allocation count by 8.75%; it is faster in 21 of 24 paired
rounds. Its runtime remains 1.975 times official JS, versus 2.117 for current Go.
These ratios and percentage reductions use the variant medians. The JSON also
records paired-round reductions and every raw observation.

Go allocation is TotalAlloc; JavaScript allocation is estimated from V8 heap
growth between GC boundaries plus known UTF-8 buffer payload. They are different
accounting methods, and neither is peak memory consumption.

The published altbak.pub application baseline remains JS 289.06 ms / Go 621.78 ms.
The earlier pre-TypeApp Go campaigns measured 586.45–588.95 ms and approximately
963–965 MB allocated. The new generic result is numerically below those historical
figures, but pre-TypeApp Go was not rerun in this campaign. Causal gain claims
above compare the current balanced campaign's control/manual/generic variants.

## Output verification

All 35 cases produce byte-identical output across official JS and the three Go
variants: the benchmark fixture, 31 repository snapshots with the measurement
options, a Unicode case, a layout case and malformed input. Every timed process
returns checksum 32412660080. The fixture output is 14,624 bytes with SHA-256
c8f7710cf563c22508c32ced1e9bbd15a12f3ea547e88bee2410cd5dfbb3395e.

## TAST preservation

All 273 TAST JSON files are byte-identical across control, manual and generic Go
variants. They retain 103 data declarations, 134 class declarations, 316 foreign
annotations, 178,085 type-table entries, 23,346 TypeApp nodes and 138,345 typed
annotations. The PureScript fork is unchanged by this experiment.

## Compiler validation

The temporary compiler builds successfully. Six focused suites pass all 28 tests,
including the real TypedExprs-to-ConstructorExprs pipeline, native composite
fields, boxed and struct-value fallbacks, constructor identity, evaluation order
and immutable aliases. An independent source review found no blocking defect.
The complete compiler regression suite remains part of a future integration;
this experiment validates the correction's effect on Tidy and focused contracts.

## Evidence and cleanup

The adjacent JSON contains raw samples, fingerprints, output checks, TAST hashes,
static generated-code comparisons, review scope and restoration checks. The
adjacent tar.gz retains the exact compiler patch and test, measurement wrapper,
source manifests, generated worker excerpts and build/test/review logs. It
contains no binaries, dependency caches or whole generated application trees.

The production output directory and binary were restored; all 285 recorded
production fingerprints match the preceding experiment, and the restored binary
returns the expected checksum. All original versioned/untracked source files
were checked against the initial inventory. Existing workspace changes are
preserved. Only this experiment's three evidence files are added to gopurs-tidy;
the owned temporary directory is removed after archive verification.

## Reproduction

Apply native-tuple-compiler.patch to an isolated copy of the recorded original
gopurs working tree, then run npm run build and the focused test command in the
JSON. Generate control and generic Go from the same corrected TAST and from the
same bench-go working directory, freezing each output and tidy-bench binary under
an isolated workspace's control/ and generic/ directories. For manual/, copy
control/ and apply manual/patch.py (the previous two-site prototype).

Backend generation uses node --stack-size=65536 <compiler>/bin/gopurs.js --main
Main, GOPURS_GO_PACKAGES=1, GOPURS_GO_PACKAGE_OVERLAY=1,
GOPURS_BUILD_MANIFEST=1, and GOPURS_PBO_JOBS/GOPURS_PREPARE_JOBS/GOPURS_EMIT_JOBS=8.
Build each binary from its output directory with go build -mod=readonly -trimpath
-o ../tidy-bench ./main, GOWORK=off, GOTOOLCHAIN=local and GOPROXY=off.

After all builds finish, run measure_generic.py --workspace <workspace>
--tidy-root <tidy-checkout> --runs 24 --output <report.json>. It reuses the
unchanged bench/measure.py and official JS artifacts. Preserve the usual
bench-go fixture path; restore canonical artifacts after isolated generation.
