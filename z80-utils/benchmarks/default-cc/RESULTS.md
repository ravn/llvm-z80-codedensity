# Initial default-CC results (2026-10-04)

Experimental branch: `experiment-default-cc-ab-20261004`, based on
`cdf7fbabe800`. Compiler changes are confined to the experiment branch. No production
default was changed. See README for the fixed corpus and annotation policy.

The real driver accepts `-fdefault-calling-conv=sdcccall0` and `sdcccall1`
for C on Z80. A uses 1, B uses 0, C uses 0 plus the documented annotations.
Explicit external conventions and compiler-generated runtime calls remain
fixed. Under default 0, standalone `z88dk_callee` selects
`Z80_SDCCCall0Callee` (cc132), not the register-base callee convention.

## Correctness and controls

All 32 cells completed and passed their assertions under ntvcm and ticks.
Native compilation plus independent Python algorithms verify expected
counts/checksums. The prefixed-instruction cycle probe yields the
hand-calculated 63 T-states. No-flag versus explicit-1 binaries and cycles
are identical at both optimization levels for all four benchmarks. The final
no-flag artifacts and cycles also match the pre-implementation baseline.

Latest regression gates: clang runtime 438 PASS / 6 SM83-only SKIP,
runner lit 155 PASS, SDCC cross-compiler runtime 174 PASS and active z88dk
integration 14/14 PASS. Agent-run focused frontend/backend lit: 5/5 PASS;
new runtime fixtures: 12/12 PASS. A broader Rust unit-test run had two
failures reported by the implementation agent:
`keeps_dirs_owned_by_a_live_process` and
`rel_link_error_is_fatal_even_when_ihx_exists`. They were not fixed here;
that broader suite is not green and no baseline comparison was captured
to independently establish their pre-existing status.

## Measurements

Bytes below are linker-map code + rodata + initialized data, not COM bytes.
Cycles cover complete execution including CRT and the fixed console shim.
Positive deltas mean more cycles (slower); all deltas are relative to A.

| Workload | Opt | A bytes | B bytes | C bytes | A cycles | B cycle delta | C cycle delta |
|---|---|---:|---:|---:|---:|---:|---:|
| callbench | Os | 6215 | 6377 | 6379 | 36,742,247 | +26.83% | +30.06% |
| callbench | O2 | 6183 | 6208 | 6210 | 27,427,016 | +8.63% | +13.50% |
| queenbench | Os | 5965 | 5981 | 5983 | 21,066,306 | +18.72% | +20.51% |
| queenbench | O2 | 5967 | 5983 | 5985 | 21,054,504 | +18.73% | +20.52% |
| sortbench | Os | 6933 | 6981 | 6988 | 22,066,097 | +0.96% | +1.09% |
| sortbench | O2 | 6950 | 7000 | 7005 | 22,200,668 | +0.96% | +1.09% |
| sieve | Os | 5950 | 5948 | 5948 | 6,079,413 | -0.85% | -0.85% |
| sieve | O2 | 5986 | 5984 | 5984 | 6,079,369 | -0.85% | -0.85% |

B/C BSS is 2 bytes larger for callbench and 4 bytes smaller for queenbench
than A; sortbench/sieve BSS is unchanged. Full COM sizes, individual section
sizes, source/compiler/binary hashes and cycles are in
`scratch/tmp/default-cc-final.json` at the workspace root. Its adjacent
artifact directory retains source, COM, assembly and linker maps.

## Interpretation and limitations

In these LLVM-Z80 workloads, register-default A reduces cycles substantially
for indirect calls and N-queens, barely for sorting, and loses slightly for
sieve. The documented fastcall/callee policy does not recover the difference
here; it is not an optimal-policy claim. Normal inlining remains enabled;
retained queenbench assembly confirms real calls to safe and recursive
place survive. Microbenchmark and recursive-call results cannot establish
a universal percentage for applications or another compiler.

Earlier preliminary C scores used an incorrect register-base callee
composition under default 0. They are superseded by this entire rerun.
Do not cite them as evidence for sdcccall(0) plus callee cleanup.

Commands have a 180-second timeout; ticks also has a 500-million-cycle
limit, which is rejected as a completed measurement. No benchmark hit
either limit. This run exercises C on Z80 only, not SM83, C++, LTO or
multi-compiler comparisons. Multi-TU and callback ABI correctness are
covered by runtime fixtures, not a separate multi-TU benchmark workload.

## Whetstone and Dhrystone extension (2026-10-04)

This companion run measures the same compiler and z88dk revisions as the
experiment above: branch `experiment-default-cc-ab-20261004` at
`68ec61b0a2096c284e5bd7c21ddac4f9baaea6bc`; clang reports base
`cdf7fbabe8000fa55f056e64ceb42b1e6f0d868f`; compiler binary SHA-256
`42aabcfd84bd9caf931cbc9d9ebf66dc0b6b7565953cdb0f3ed4ddf86291681f`;
z88dk revision `8979df43e6289313f0dc12d31a10c03c07944f4c`. The matrix has
16 cells:
Whetstone and Dhrystone, `-Os` and `-O2`, each with no option, A
(`sdcccall1`), B (`sdcccall0`), and C (`sdcccall0` plus the fixed annotations).
No-flag and A binaries, SHA-256 hashes, and cycles match exactly in all four
workload/optimization pairs.

Whetstone uses `LOOP=10`, `II=1`, and `--math32` for every cell; its
transformed source captures volatile observations after modules 2, 3, 7, 8,
9, and 11 and integer state from modules 4, 6, and 9. The independent host
oracle rounds each floating-point operation to binary32 and computes the
transcendental modules separately; all emitted binary32 bit patterns and
integer observations passed at `0.0001 + 0.0001 * abs(expected)` tolerance.
Dhrystone runs 20,000 iterations and checks the published 2.1 final numeric
variables and strings. Its optional `PRINTF` route is excluded because it
does not link in this z88dk setup. Observer builds emit lossless values and
pass their oracle under ntvcm; each separate timed build emits only `PASS`
and passes both ntvcm and ticks completion checks.

The preliminary O2 Whetstone trials were invalid in two ways: the module-8
`_P3` call was optimized away even though its final value passed, and the
module-6 loop was folded to constant state because its array writes are
overwritten by module 9. Those scores are superseded here. The harness marks
`P3` `noinline` in every variant and builds module 6 as a separate translation
unit with no LTO and a fixed `z88dk_fastcall` helper ABI in every variant.
Its assembly checks require the module-6 call and a helper backedge whose loop
body retains arithmetic and indirect array stores; the seven nonzero module
loops in `main` must also remain. The checks additionally require the
module-8 `_P3` call to be enclosed in its repeated loop and the module-3
`_PA` call to remain. The C policy covers the original benchmark functions:
Whetstone `PA` is fastcall and `P3` is callee; Dhrystone `Proc_1/2/3` and
`Func_3` are fastcall, while `Proc_6/7/8` and `Func_1/2` are callee.
Dhrystone declarations and definitions are annotated consistently. The
benchmark sources in z88dk are not modified.

All builds use `zcc +cpm -compiler=llvmz80`, `-Cg-Os` or `-Cg-O2`,
`-m -no-cleanup -create-app`, no LTO, and the explicit
`-Cg-mllvm -Cg-z80-static-frames=false` opt-out (zcc otherwise enables static
frames by default). The harness rejects static-frame markers. The shared
63-T-state cycle control passed; the cap was 500,000,000 cycles, and no run
hit it. Commands use the shared runner's finite timeout. Each row below gives
absolute COM bytes and linker-map code+rodata+initialized-data bytes, with
size deltas in parentheses versus A; BSS is separate. Cycles cover the
complete CP/M executable and fixed console/BDOS shim, with deltas versus A.

| Workload | Opt | Variant | COM B (delta) | Code+rodata+data B (delta) | BSS B | Cycles (delta vs A) |
|---|---:|---|---:|---:|---:|---:|
| Whetstone | Os | A | 17,099 (0) | 16,037 (0) | 767 | 375,346,100 (0) |
| Whetstone | Os | B | 17,104 (+5) | 16,042 (+5) | 767 | 376,003,630 (+657,530; +0.175%) |
| Whetstone | Os | C | 17,107 (+8) | 16,045 (+8) | 767 | 375,984,390 (+638,290; +0.170%) |
| Whetstone | O2 | A | 19,603 (0) | 18,541 (0) | 767 | 375,247,540 (0) |
| Whetstone | O2 | B | 19,611 (+8) | 18,549 (+8) | 767 | 375,906,750 (+659,210; +0.176%) |
| Whetstone | O2 | C | 19,611 (+8) | 18,549 (+8) | 767 | 375,885,830 (+638,290; +0.170%) |
| Dhrystone | Os | A | 13,642 (0) | 7,486 (0) | 5,861 | 215,683,551 (0) |
| Dhrystone | Os | B | 13,746 (+104) | 7,590 (+104) | 5,861 | 228,743,551 (+13,060,000; +6.055%) |
| Dhrystone | Os | C | 13,706 (+64) | 7,550 (+64) | 5,861 | 232,443,551 (+16,760,000; +7.771%) |
| Dhrystone | O2 | A | 13,660 (0) | 7,504 (0) | 5,861 | 215,943,601 (0) |
| Dhrystone | O2 | B | 13,781 (+121) | 7,625 (+121) | 5,861 | 231,203,601 (+15,260,000; +7.067%) |
| Dhrystone | O2 | C | 13,742 (+82) | 7,586 (+82) | 5,861 | 234,903,601 (+18,960,000; +8.780%) |

Here, BSS is unchanged across variants within each workload/optimization
pair. The default convention and its explicit A equivalent are effectively
identical on Whetstone; B and C add about 0.17-0.18% cycles. On Dhrystone, B is
about 6.1-7.1% slower and C about 7.8-8.8% slower than A.

Reproduce from the workspace root with:

```sh
python3 llvm-z80/z80-utils/benchmarks/default-cc/run_whetstone_dhrystone.py \
    --output scratch/tmp/default-cc-whet-dhry-final-isolated.json
```

That JSON and `scratch/tmp/default-cc-whet-dhry-final-isolated/` retain every
cell's oracle observations, transformed sources, binaries, maps, assembly,
outputs, and section sizes.

## Original-compute Whetstone mode (2026-10-04)

This bounded rerun measures only Whetstone in the original-compute mode; it
does not repeat Dhrystone. It uses the same clang binary
(`42aabcfd84bd9caf931cbc9d9ebf66dc0b6b7565953cdb0f3ed4ddf86291681f`) and
z88dk revision `8979df43e6289313f0dc12d31a10c03c07944f4c` as the companion
run above. The source is z88dk's original `whetstone.c`, with `main(int
argc, char *argv[])` changed to `int main(void)` for fixed `LOOP=10`, `II=1`,
and a `PASS` marker after `TIMER_STOP`. Its arithmetic and benchmark loops
are not rewritten. `PRINTOUT`, `TIMEFUNC`, and `COMMAND` are not enabled, so
there is no benchmark printf/timer code in the timed build; `--math32`, no
LTO, and `-mllvm -z80-static-frames=false` apply to every cell.

The correctness observer is a separate build: it stores volatile snapshots
after modules 2, 3, 4, 6, 7, 8, 9 and 11, then emits lossless binary32 and
integer values after the computation. All eight observer builds passed the
independent Python binary32/integer oracle; float tolerance is
`0.0001 + 0.0001 * abs(expected)`. The observer adds no `noinline`, module-6
helper, or assembly-preservation gate, but its volatile observations can keep
work alive. Only the separate timed build is scored; it has no snapshots and
is checked for `PASS` completion under ntvcm and ticks. Thus the observer
proves the fixed source workload's results, not that the optimizer-free timed
binary computes and retains every nominal module.

The table gives absolute COM bytes, linker-map code+rodata+initialized-data
bytes, BSS, and full-program ticks cycles. Size deltas and cycle deltas are
relative to A (`sdcccall1`) within the same optimization level. The no-flag
control and A had identical COM SHA-256, section sizes, and cycles at both
optimization levels.

| Opt | Variant | COM B (delta vs A) | Code+rodata+data B (delta vs A) | BSS B (delta vs A) | Cycles (delta vs A) |
|---|---|---:|---:|---:|---:|
| Os | no flag | 15,983 (0) | 14,999 (0) | 689 (0) | 242,007,314 (0) |
| Os | A: sdcccall1 | 15,983 (0) | 14,999 (0) | 689 (0) | 242,007,314 (0) |
| Os | B: sdcccall0 | 15,982 (-1) | 14,998 (-1) | 689 (0) | 242,008,574 (+1,260; +0.001%) |
| Os | C: sdcccall0 + policy | 15,990 (+7) | 15,006 (+7) | 689 (0) | 242,007,314 (0; +0.000%) |
| O2 | no flag | 18,487 (0) | 17,503 (0) | 689 (0) | 241,908,754 (0) |
| O2 | A: sdcccall1 | 18,487 (0) | 17,503 (0) | 689 (0) | 241,908,754 (0) |
| O2 | B: sdcccall0 | 18,489 (+2) | 17,505 (+2) | 689 (0) | 241,911,694 (+2,940; +0.001%) |
| O2 | C: sdcccall0 + policy | 18,494 (+7) | 17,510 (+7) | 689 (0) | 241,908,754 (0; +0.000%) |

For C, the original benchmark policy is `PA` fastcall and `P3` callee. The
timed assembly is the evidence for optimizer freedom: both `-Os` and `-O2`
retain five loop backedges in `main` (modules 2, 3, 7, 9 and 11), a `PA` call
inside module 3, and a `P0` call inside module 9. In both modes the nonzero
module-4 conditional-jump loop (3,450 iterations) and module-6 integer loop
(2,100 iterations) are absent; the module-8 loop's 8,990 `P3` calls are also
absent from `main`. The externally visible `_P3` body is emitted, but is not
called from `main`. Modules 1 and 10 have zero iterations by the source's
fixed workload. No gate rejects these optimized-away operations.

For contrast, the preceding workload-preserving A results were 17,099 COM /
16,037 code+rodata+data / 767 BSS / 375,346,100 cycles at `-Os`, and 19,603 /
18,541 / 767 / 375,247,540 at `-O2`. Original-compute A is smaller by 1,116
COM bytes and 1,038 code+rodata+data bytes, with 78 fewer BSS bytes, and
completes 133,338,786 fewer cycles at either optimization level. This is not
a single-variable compiler speedup comparison: the workload-preserving
timed build deliberately keeps module 6 out of line, keeps `P3` non-inlined,
and includes volatile result snapshots, whereas original-compute removes
those preservation measures and allows the optimizer to eliminate unobserved
work. The assembly evidence above identifies the work absent from the
original-compute timed binary.

The shared 63-T-state cycle probe passed. Every subprocess has a 180-second
timeout, the cycle limit is 500,000,000, and no cell hit either limit.
Reproduce from the workspace root with:

```sh
python3 llvm-z80/z80-utils/benchmarks/default-cc/run_whetstone_dhrystone.py \
    --whetstone-mode original-compute \
    --output scratch/tmp/default-cc-whetstone-original-compute-20261004.json
```

The JSON and `scratch/tmp/default-cc-whetstone-original-compute-20261004/`
retain the oracle observations, observer and timed sources, COMs, maps,
assembly, runtime outputs, and section sizes.
