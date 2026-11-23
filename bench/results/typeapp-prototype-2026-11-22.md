# Temporary native Tuple prototype — 22 November 2026

This experiment profiles the Go regression following the typed fork's TypeApp
optimizer correction. It changes two expressions in a temporary copy of generated
Go. The PureScript and gopurs source changes already present in the workspace are
preserved, and the normal corrected Go build is restored. The prototype is not
integrated or used in the public altbak.pub application table.

## Cause and intervention

Allocation profiles identify `PureScript.CST.Layout.insertLayout`: its subtree
allocates an additional 9,415,016 bytes per fixture formatting, almost the whole
9,413,008-byte allocation-profile delta. Four layout `Rebox` functions and
`RecordShape2` account for about 86% of the additional flat allocation bytes.

TypeApp-aware simplification exposes native specialized workers. In the affected
`insertDefault` worker, gopurs still constructs Tuple values through boxed
composite fields, then converts them to the native pointer representation the
consumer expects. This recursively copies layout stacks, token records and arrays.
The relevant compiler paths are `AdtExprs.saturatedFieldType` and `saturated`,
`ConstructorLayout.withExpectedRepresentation`, and `GoConversions.coerceGoExpr`.
The machine-readable diagnosis records source lines and the exact replacements.

The prototype directly constructs the native Tuple(token, stack) before `snoc`
and Tuple(stack, tokenArray) at return. Both retain the existing field values
and structural types. No mutation, unsafe cast, ownership inference or global
memoization is introduced; array `snoc` retains its normal copy behavior.

CPU profiles cover 100 format-and-consume operations per baseline. They are
dominated by runtime/system frames, so the precise attribution above comes from
allocation stacks. Allocation profiles sample every allocation over one operation,
subtract a baseline, and flush profiles with GC. Instrumented elapsed times are
not runtime benchmark results.

## Uninstrumented measurements

Each fresh process runs ten complete format-and-UTF-8-consume iterations.
Medians use 24 runs per variant, covering all 24 execution orders, with one
excluded warm-up and no outlier removal. Allocation counters use three separate
runs. Node 24.8.0 and Go 1.27.0 run with default GC/thread settings.

| Variant | Runtime | Allocated bytes | Allocation count |
| --- | ---: | ---: | ---: |
| Go before TypeApp correction | 588.95 ms | 962,872,536 | 20,586,913 |
| Go after TypeApp correction | 623.23 ms | 1,062,593,912 | 22,908,189 |
| Go with temporary Tuple prototype | 604.36 ms | 1,004,149,104 | 21,526,043 |
| Official JavaScript | 292.27 ms | ~822,530,064 | — |

The prototype improves median Go runtime by 3.03%, allocated bytes by 5.50%,
and allocation count by 6.03% relative to the corrected fork. It is faster in
19 of 24 paired rounds. It remains 2.62% slower and allocates 4.29% more bytes
than the pre-correction Go baseline; this is a partial correction. Its runtime
is 2.07× official JS. JS allocation is a V8 heap estimate plus 146,240 bytes of
UTF-8 buffer payload; Go uses TotalAlloc, so these are different accounting methods.

The prototype allocation profile removes 5,614,536 bytes from insertLayout's
subtree per formatting operation, approximately 60% of the identified regression.
Totals in the table come from the separate uninstrumented allocation campaign.

The existing altbak.pub reference remains JS 289.06 ms / Go 621.78 ms,
measured in the preceding campaign. This prototype does not replace it.

## Verification and evidence

All 35 inputs produce identical bytes and checksums across the four variants.
The principal fixture remains 14,624 bytes, SHA-256
`c8f7710cf563c22508c32ced1e9bbd15a12f3ea547e88bee2410cd5dfbb3395e`.
Every timed process returns checksum 32412660080. All 273 generated TAST JSON
files are byte-identical between the corrected build and prototype, including
type tables, TypeApp nodes, declarations and annotations. The reconstructed
before baseline reproduces all nine generated Go file hashes from the previous
campaign.

The adjacent JSON contains raw samples, fingerprints, validation, diagnosis and
profile summaries. The adjacent `.tar.gz` contains the exact temporary patch and
measurement wrapper, driver source, readable pprof tables and compressed CPU and
allocation profiles; it contains no compiler or application executables.

For reproduction, rebuild the recorded before/after variants using the same
sources and compiler identities. Put each output directory and tidy-bench binary
under an isolated workspace's before/after subdirectories. Copy after to prototype,
apply `prototype/patch.py` to its output, rebuild with `go build -mod=readonly
-trimpath -o ../tidy-bench ./main` from that output, then invoke the archived
`measure_prototype.py --workspace <workspace> --tidy-root <tidy-checkout>
--runs 24 --output <report.json>`. Compilation and profiling must finish before
timing. Source locations for pprof may require `-source_path` pointing at the
corresponding generated output. Remove isolated builds after retaining results.
