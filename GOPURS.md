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

- The typed PureScript compiler fork (`purs`) and Spago 1.0.3 on `PATH`.
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
(cd output && GOWORK=off GOPROXY=off GOTOOLCHAIN=local go build -mod=readonly -o ../tidy-bench ./main)
./tidy-bench
```

The fixture is `bench/fixture.purs` (a copy of `src/Tidy/Doc.purs`, 514
lines). `Main` parses, formats and prints the formatted length 10 times with
`pageWidth: 80`. The JavaScript run needs `--stack-size=4000` for this fixture
with Node 24; the Go side does not.

## First results

Same fixture and iteration count on both sides; checksums are identical
(`146240`). Median of 7 warm runs, single-threaded:

| Backend | Median |
| --- | ---: |
| JavaScript (official compiler, Node 24) | 0.397 s |
| Go (gopurs release, Go 1.27) | 1.063 s |

Go is about **2.68×** slower than JavaScript on this formatter workload. This
is a first measurement, not yet integrated into the altbak.pub result tables.
