# Default calling-convention experiment

Run from the workspace root:

```sh
python3 llvm-z80/z80-utils/benchmarks/default-cc/run.py \
    --output scratch/tmp/default-cc-results.json
```

`--baseline-only` captures the unmodified compiler before implementation.
Requires the workspace z88dk, ntvcm, assertions clang and existing
`scratch/dcc-clang-bench/ticks_cpm.py`. Uses only Python's standard library.
All compiler/emulator working directories are created below `scratch/tmp`
and automatically removed. Results and the adjacent artifact directory
(sources, binaries, maps and assembly) are intentionally retained.

The corpus reuses z88dk's `test/suites` callbench, queenbench, sortbench and
sieve without changing workloads. The small replacement `test.h` runs tests
immediately and emits `PASS` only after their assertions finish. It avoids
introducing the test framework's separate callback ABI. No LTO or static
frames are enabled; recursive workloads remain reentrant. Normal compiler
inlining stays enabled, so check retained assembly before attributing any
change to a particular call.

Cells at both `-Os` and `-O2`:

| Cell | Default | Additional annotations |
|---|---|---|
| baseline | No option | None |
| A | sdcccall1 | None |
| B | sdcccall0 | None |
| C | sdcccall0 | Frozen named-function policy in `run.py` |

C uses callee cleanup on callbench's dispatch/apply/compose, queenbench's
safe, and sortbench's qsort_rec/ins_sort/checksum/is_sorted. Queenbench's
single-argument place uses fastcall. Pointer-target signatures are left
unmodified; sieve has no annotations and is a control. This is one explicit
policy, not a claim of optimal annotation coverage or automatic selection.

Correctness precedes scoring: the host compiler and two emulators must pass.
Python independently verifies the prime and queen counts and sorting
checksums using trial division, permutations and `sorted`, plus a masked
integer reference for the call checksum. No-op/A binaries and cycles must
match exactly. A hand-countable prefixed-instruction probe checks ticks
against 63 T-states. Timing covers the entire CP/M executable, including
startup and the fixed console/BDOS shim; it is not kernel-only timing.

Binary size includes everything serialized in the COM file; use retained
linker maps to distinguish code, initialized data, read-only data and BSS.
Do not label COM byte counts as code size. The four workloads are a bounded
initial corpus, not a universal calling-convention performance claim.

## Workload-preserving Whetstone and Dhrystone extension

Run the separate float/integer workloads from the workspace root:

```sh
python3 llvm-z80/z80-utils/benchmarks/default-cc/run_whetstone_dhrystone.py \
    --output scratch/tmp/default-cc-whet-dhry-results.json
```

This companion copies z88dk's Whetstone and Dhrystone 2.1 sources into
automatically cleaned per-cell working directories. Whetstone runs its fixed
default `LOOP=10`, `II=1` workload, with `--math32` on every cell. The harness
captures binary32 snapshots after modules 2, 3, 7, 8, 9 and 11 plus integer
state from modules 4, 6 and 9. A separate Python implementation rounds each
operation to IEEE binary32, computes the transcendental modules on the host,
and checks all emitted target values using a stated tolerance. The observer
build runs under ntvcm; the timed build retains the same snapshots as volatile
stores but emits only `PASS`, so hex reporting does not dominate the ticks
score. Float tolerance is `0.0001 + 0.0001 * abs(expected)`. Dhrystone runs
20,000 iterations and checks Weicker's published
version-2.1 final numeric variables and strings, then emits the observed
values in the observer build and `PASS` in both builds.

The copied-source transformations are limited to fixed-argument Whetstone
`main(void)`, Dhrystone's standard `int main(void)`, result snapshots/output,
correctness checks after `TIMER_STOP`, and benchmark-only workload guards.
Whetstone's module-6 loop is built as a separate translation unit with no LTO:
O2 can otherwise fold its constant state and discard its array writes, which
module 9 overwrites. The helper's `z88dk_fastcall` ABI is fixed in every
variant so it does not participate in the default-CC comparison. Whetstone's
`P3` is marked `noinline` in every variant so O2 cannot collapse the module-8
repeated-call workload. The harness checks all seven nonzero module loops in
`main`, plus the module-6 helper loop and module-8 call loop, in generated
assembly. Dhrystone's optional `PRINTF` output is deliberately disabled:
enabling it pulls unresolved dtoa symbols in the current z88dk link setup.
No benchmark source in z88dk is edited.

Before scores are measured, C's annotation policy is fixed in the script:
single-argument original benchmark functions use `z88dk_fastcall`,
multi-argument functions use `z88dk_callee`, and `main`, zero-argument
routines, and library prototypes are excluded. The module-6 helper is the
fixed-ABI exception described above. Dhrystone's `dhry.h` declarations and
both translation-unit definitions are annotated consistently. No LTO or
static-frame allocation is used. Because zcc's Z80 backend enables static
frames by default, every cell passes `-mllvm -z80-static-frames=false`; the
harness rejects artifacts containing the static-frame marker. Each binary
must pass ntvcm and ticks completion checks before its cycles are recorded.
The harness reuses this directory's shared linker-map parser and 63-T-state
ticks control; it defaults to a 500-million-cycle cap and rejects a capped run.

The result JSON and its sibling artifact directory retain the transformed
sources, `.COM` files, assembly, maps, correctness output and per-section
sizes. All temporary compiler/emulator working directories are removed
automatically. See `RESULTS.md` for the measured values and exact compiler
identity.

## Original-compute Whetstone mode

Run only the eight Whetstone cells (no Dhrystone rerun) with optimizer freedom:

```sh
python3 llvm-z80/z80-utils/benchmarks/default-cc/run_whetstone_dhrystone.py \
    --whetstone-mode original-compute \
    --output scratch/tmp/default-cc-whetstone-original-compute.json
```

This mode starts from z88dk's original compute source, fixes only `main` to
`int main(void)` for the fixed `LOOP=10`, `II=1` harness, and adds a `PASS`
completion marker after the computation. Its timed source has no intermediate
snapshots, `noinline`, module-6 helper, forced call/loop checks, or LTO.
`PRINTOUT`, `TIMEFUNC`, and `COMMAND` are not enabled: benchmark printing and
timer code are absent, while ticks measures the completed CP/M executable.
Consequently the optimizer may remove work whose results are not observable.

Each cell also has a separate observer build for correctness. It adds volatile
snapshots after the original modules and prints their lossless values only after
the benchmark computation; these observer builds run under ntvcm, not ticks.
An independent Python binary32/integer oracle must pass before that cell's
timed build is scored. Timed builds must emit `PASS` under both ntvcm and ticks.
The unflagged and A (`sdcccall1`) timed COMs and cycle counts must match exactly
at each optimization level. Generated observer/timed sources, maps, assembly,
COMs, output, and section sizes are retained with the JSON. The measured stock
source results and optimizer-elimination evidence are in `RESULTS.md`.
