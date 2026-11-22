# llvm-z80 Handoff & Parkeringsstatus (2026-11-22)

Dette dokument samler og afslutter arbejdet på `llvm-z80` forud for fokusskift til RC700 PIO CP/NOS.
Alle videre ændringer er bevaret i vort eget repository:
**`git@github.com:ravn/llvm-z80-codedensity.git`** (upstream-PRs er opgivet).

---

## 1. Nuværende status & Parkeringspunkt
* **Primær parkeringsgren:** `park/2026-11-22` (tag `park-2026-11-22`).
* **Basis-commit:** `58bce35ae06e` ("[Z80] Hoist preheader reloads and ADD HL, rr to predecessor to coalesce frame accesses").
* **Forfader:** Bygger på `upstream/main` (`0331c1c`) med 40 egne commits:
  - Samtlige 17 reimpl-trin: memory-folds CP/OR/AND/XOR/ADD/SUB/INC/DEC (HL), LD A,(nn), DEC (HL)+nul-sammenligning, HL-add, TTI/LSR, NonReentrant inline-asm, #74 no-callback i alle tre lag, umulhi3 m.fl.
  - Packet-parser-codegen optimeringer: IX-allokering, store-phi-sink, SP-reload coalescing, DJNZ-split, loop-rotation, SET/RES (HL).
* **Toolchain build:** Bygges og verificeres via `make toolchain` / `scripts/ccache-wrapper` i rodprojektet. Binærer anvendes bl.a. af `rc700-gensmedet/autoload-in-c` og `cpnos-in-c`.

---

## 2. Grenoversigt (Hvor er hvad?)

### A. Primær udviklingslinje & parkering
- `park/2026-11-22` / `main`: Den konsoliderede parkeringslinje (nyeste funktioner + reimpl).
- `work/packet-parser-codegen`: Oprindelig arbejdsgren for de 40 codegen-commits (forfader til park-grenen).
- `reimpl`: Den rene re-implementering af samtlige 17 forbedringer (forfader til packet-parser).

### B. Intrinsics & Firmware-specifikke funktioner
- `s1/…`, `s2/…`, `s3/…`, `s4/z80-clang-builtins`: Stak af commits oven på `main` (`a2fb43fe`), som implementerer nocallback, konstant-port IN/OUT, im0/1/2+set.i, clang builtins (`__builtin_z80_*`) og LTO null-streamer.
- `fix/cpnos-lto-null-streamer` (`adca219`): Den ældre firmware-linje (baseret på `da06bcd` + intrinsics + LTO streamer).

### C. z88dk integration
- `z88dk-wip`: z88dk target environment og libcall bindings.
- `cleanroom-z88dk-mul-libcalls-420`: Renrumsimplementering af mul-family libcalls.
- `z88dk-native-libcalls`: Native runtime libcalls.
- `z88dk-symbol-encoding`: Symbol encoding tilpasninger.
- `work/zcc-z88dk-env-20261014`: zcc-wrapper miljøopsætning.

### D. Gemte stashes & arbejdstræer (park/*)
- `park/stash-20261016-inline-compat-tti`: Tidligere `stash@{0}` (Z80TargetTransformInfo.h).
- `park/stash-20261009-no-recurse-attr`: Tidligere `stash@{1}` (Z80NonReentrant no-recurse).
- `park/stash-20261004-general-abi-default-cc`: Tidligere `stash@{2}` + `run_whetstone_dhrystone.py` (ABI og benchmarks).
- `park/z88dk-target-abi-test-20261004`: Tidligere u-tracket test i target-abi worktree.
- `test-runner-hardening-20261004`: Hærdning af Rust test-runner.

### E. Arkiverede milepæle & historik
- `archive/main-a2fb43fe`: Tag for den tidligere `main` branch.
- `archive/root-pin-da06bcd`: Tag for den tidligere pinned commit i rodrepoet.
- `archive/fw-intrinsics-adca219`: Tag for firmware-intrinsics linjen.
- `origin/ravn-main`: Indeholder den historiske `z80-utils/` pakke og gamle tasks/.

---

## 3. Hvad er IKKE på parkeringsgrenen (og hvorfor)
1. **Intrinsics / Builtins (`__builtin_z80_*`)**: Ligger på `s4/z80-clang-builtins`. RC700 firmware-headere har `__has_builtin`-fallback til inline asm, så CP/NOS kan bygge uden.
2. **LTO Null Streamer**: Ligger på `s4` og `fix/cpnos-lto-null-streamer`.
3. **z88dk-env passagerer**: Ligger på `z88dk-wip`.
4. **Static-frame spill->push/pop folds (`42d09a9`, `a9c0a69`)**: Ligger kun på den ældre `da06bcd`-linje.

---

## 4. Byg, test & verifikation

### Byg toolchain
Fra rodkataloget `/Users/ravn/z80`:
```bash
./rebuild-llvmz80.sh
# eller
ninja -C llvm-z80/build-macos-asserts clang llc
```

### Kør lit-tests
```bash
llvm-z80/build-macos-asserts/bin/llvm-lit llvm-z80/llvm/test/CodeGen/Z80 -q
LIT_FILTER=z80-e2e ninja -C llvm-z80/build-macos-asserts check-z80
```

### Verificer mod CP/NOS & RC700
```bash
cd rc700-gensmedet/cpnos-in-c && make clean && make
```

---

## 5. Hvor arbejdet slap & Genoptagelse
- **Packet-parser codegen**: Se analyse og planer i rodens `tasks/plan-packet-parser-codegen-full-2026-11-15.md`, `tasks/draft-issues-packet-parser-codegen.md` samt `tasks/packet-parser-*.txt`.
- **Re-implementeringsdetaljer**: Se `tasks/plan-ravn-commits-reimplementation.md` i dette katalog.
- **Første skridt ved genoptagelse**:
  1. Hent nyeste `park/2026-11-22`.
  2. Hvis intrinsics ønskes integreret, cherry-pickes commits fra `s1`–`s4` oven på park-grenen.
