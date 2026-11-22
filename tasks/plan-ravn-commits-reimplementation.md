# Plan: Reimplementering af ravn-unikke commits på `upstream/main`

**Dato:** 2026-11-14 (opdateret samme dag)
**Base:** `upstream/main` (llvm-z80/llvm-z80 `0331c1cabf81` "Tail call when the stack arguments are passed through (#139)")
**Mål:** Reimplementere ravn-unikke commits fra `main` oven på `upstream/main` i upstream-klar kvalitet (atomare commits, lit + C e2e tests, upstream-koordineret).

**Aktuel branch-situation:**
- `main`: 22 commits oven på upstream/main — indeholder zlfn's z88dk-WIP commits som passagerer (se Note C)
- `z88dk-wip`: oprettet 2026-11-14 fra upstream/main, indeholder de 4 zlfn z88dk-commits cherry-picked
- `s1`–`s4`: intrinsics-stack oven på main (uberørt)

## Startprocedure (gør dette FØR alt andet)

```bash
# 1. Opret arbejdsbranch fra ren upstream/main
git -C llvm-z80 fetch upstream
git -C llvm-z80 checkout -b reimpl upstream/main

# 2. Byg toolchain (clang+lld+llc+llvm-nm+llvm-objcopy+llvm-objdump)
#    på macOS: build-macos-asserts/, på Linux: build-linux/
make toolchain   # fra workspace-root /Users/ravn/z80/ eller /home/ravn/z80/

# 3. Kør baseline-snapshot (gem til fil — sammenlign efter hver commit)
BUILD_DIR=build-macos-asserts  # eller build-linux på Linux
$BUILD_DIR/bin/llvm-lit llvm/test/CodeGen/Z80/ -q 2>&1 \
    | tee scratch/tmp/lit-baseline.txt

# E2E på upstream/main = lit-suiten z80-e2e (IKKE cargo/z80-utils).
# SDCC slået fra (sdasz80-shim kan ikke køre i sandbox):
#   cmake -DSDAS_z80=SDAS_z80-NOTFOUND -DZ80_E2E_FORMATS=elf -B build-macos-asserts llvm
env CCACHE_BASEDIR=$PWD LIT_FILTER=z80-e2e ninja -C build-macos-asserts check-z80 \
    2>&1 | tee ../scratch/tmp/e2e-baseline.txt
```

**Baseline 2026-11-14 (ren upstream/main `0331c1cabf81`, build-macos-asserts, SDCC fra):**
lit CodeGen/Z80: 169 PASS + 1 UNRESOLVED (`icmp-canonical.s`, utracket rest uden RUN-linje, ikke upstream).
check-z80 (`LIT_FILTER=z80-e2e`): 4286 fundet, 2731 Passed, 0 Failed, 1349 Unsupported, 206 Excluded; torture-suiten tom (gcc-torture submodule ikke checked out).
Filer: `scratch/tmp/lit-baseline-full.txt`, `scratch/tmp/e2e-baseline.txt`.

**Vigtigt:** s1–s4 branches (`s1/z80-nocallback` … `s4/z80-clang-builtins`) røres IKKE. De er intrinsics-arbejde der er separat fra reimplementeringen.

**Firmware-test blokeret på reimpl-branch:** `autoload-in-c` og `rcbios-in-c` headers bruger `__builtin_z80_*` og `llvm.z80.*` intrinsics der KUN findes på s4-branchen, ikke på `upstream/main`. Firmware boot-test i kvalitetstjeklisten springes over for commits der ikke rører NonReentrant/frames. Når Fase 7 (#74) er implementeret, genaktiveres firmware-test.

**E2e-sti:** `z80-test/e2e/c/` (eksisterer i upstream/main). Kør med `LIT_FILTER=z80-e2e ninja -C build-macos-asserts check-z80` (en enkelt test: `build-macos-asserts/bin/llvm-lit build-macos-asserts/tools/z80-test/e2e/z80-Os-elf --filter <navn>`). `cargo run -- clang` i z80-utils gælder IKKE længere på upstream-grenen.

## Metodik / forudsætninger

- **Én ting pr. commit.** `f5f9f5` splittes i 2 (se Note A). Commits der ikke kan beskrives i én sætning er for store.
- **Test-dobbeltlag:** hver codegen-ændring skal have (a) `llvm/test/CodeGen/Z80/<navn>.ll` med FileCheck der pinner instruktionssekvensen og (b) et C e2e testcase i `z80-test/e2e/c/test_<N>_<navn>.c` med `/* expect 0xNNNN */`. Lit beskytter mod strukturel regression; e2e mod runtime.
- **Rute:** generelle LLVM-bugs → llvm/llvm-project; Z80-specifikke forbedringer → llvm-z80/llvm-z80 (per `feedback_upstream_routing_two_targets`).
- **Per-filing go-ahead:** hvert PR skal godkendes eksplicit af brugeren (`feedback_explain_before_filing`). Ingen `gh pr create` uden eksplicit "ja".
- **CI skal være grøn** per PR: check `gh run list --repo llvm-z80/llvm-z80` efter push.

## Regressionsregler

Når en ny fold ændrer eksisterende lit-tests (f.eks. `ld a,(hl)` + `or a` → `or (hl)`):

1. **Opdatér berørte `CHECK`-linjer i samme commit** som selve folden — ikke et separat commit.
2. **Sammenlign med baseline-snapshot** (`scratch/tmp/lit-baseline.txt`) for at finde alle berørte tests.
3. Hvis en test fejler og det IKKE er forventet (dvs. en fold bryder noget den ikke burde røre): **stop, revert, undersøg** — kør `llvm-lit -v <den fejlende test>` og bisect om nødvendigt. Fortsæt ikke til næste commit.
4. **Firmwarestørrelsesregression:** autoload er hard-capped 2048 B. Enhver ændring der øger `clang/text_compressed.zx0` over 2048 B blokerer merge.

## Note A: `f5f9f5` er IKKE 3-i-1 — den er 2-i-1

Commitbeskeden på `f5f9f5` nævner tre ting (CP(HL) fold, COMPARE8_IND pseudo, NonReentrant SCC fix), men diff'et rører KUN:
- `Z80InstrInfo.cpp` (+14/-2)
- `Z80InstrInfo.td` (+6)
- `Z80InstructionSelector.cpp` (+40/-7)
- `Z80RegisterInfo.td` (+14)

Commitbeskeden nævner en NonReentrant SCC-fix, men diff'et rører IKKE `Z80NonReentrant.cpp`. Den beskrevne SCC-fix eksisterer ikke som separat kode — den var enten aldrig implementeret eller foldet ind i `c8b0951` (inline-asm edge-filter). Ignorér SCC-fix-beskrivelsen; implementér kun de to ting diff'et faktisk viser. **Beslutning:** `f5f9f5` splittes i to logiske stykker når den reimplementeres:

1. **COMPARE8_IND pseudo + GR16_HL register class** (TableGen: `Z80InstrInfo.td`, `Z80RegisterInfo.td`, size-case og post-RA-expansion i `Z80InstrInfo.cpp`).
2. **CP (HL) folding i instruction selector** (`Z80InstructionSelector.cpp` `emitCP`/`emitEqualityTest`).

Hver del får sin egen lit + e2e. Det er også den naturlige review-rækkefølge: man kan ikke folde til en pseudo der ikke findes endnu.

## Note C: z88dk-commits er zlfn's WIP — IKKE ravn-arbejde

Cherry-pick 2026-11-14 afslørede at **alle fire** z88dk-relaterede commits har `zlfn <ung@zlfn.space>` som forfatter:
- `855189fb` — fused 16-bit division
- `a3c890e4` — z88dk assembly print default
- `ad41303b` — z88dk runtime calls
- `b3802478` — z88dk byte divide

De kom med som passagerer fordi vi rebasede oven på zlfn's z88dk-udviklingsgren (ikke ren `upstream/main`). De er **ikke** i `upstream/main` endnu.

**`z88dk-wip` branch** er oprettet fra `upstream/main` med disse fire commits cherry-picked. Main forbliver urørt fordi en direkte rebase fejlede: `a2fb43fe` er entangled med z88dk-infrastruktur (se Note D).

**Konsekvens for kategorioversigten:** `a3c890e4`, `ad41303b`, `b3802478` opdateres til DROP (zlfn's kode) — de lever på `z88dk-wip`.

Derudover er `4e93072b` (CMake z88dk HINTS) og `e0cbd3fa` (libcalls mul-family under z88dk) også z88dk-specifik infrastruktur der hører til på `z88dk-wip`, ikke `main`.

## Note D: `a2fb43fe` skal splittes under reimplementering

`a2fb43fe` ("Rebase fixes") mixer to ting:
1. **CallingConv renummerering + Triple::Z88DK** — generel upstream-tilpasning, nødvendig for al Z80-kode
2. **z88dk SystemLibrary API** — z88dk-specifik `RuntimeLibcalls.td` tilpasning

Under reimplementering splittes dette i to commits:
- CallingConv/Triple-commit → `main` (prereq for alle andre commits)
- z88dk SystemLibrary-commit → `z88dk-wip`

## Note E: Åbne spørgsmål — besvarede

1. **`c8b0951` (NonReentrant inline-asm):** Vi implementerer selv alle tre lag af #74 som et PR til llvm-z80/llvm-z80. Lag (1) er `c8b0951`. Se Fase 7.
2. **z88dk-stakken:** Lever på `z88dk-wip` branch. Sendes koordineret med zlfn når #86/#87 lander.
3. **`855189fb`:** Er zlfn's WIP, ikke i `upstream/main`. Fjernes fra `main` via reimplementering fra bunden (ikke trivielt nu pga. `a2fb43fe`-entanglement).
4. **E2e for NonReentrant:** Lit-only er acceptabelt.

## Note B: Upstream koordination FØR implementering

Disse punkter SKAL diskuteres med zlfn (owner llvm-z80/llvm-z80) før kode sendes:

- **#74 `+static-frame` for CP/M main** — zlfn's planlagte løsning (2026-11-13) består af tre lag: (1) inline asm = non-reentrant default, (2) `__attribute__((target("no-callback")))`, (3) `-fz80-assume-no-callbacks`. Vores `c8b0951` (inline-asm edge-filter) overlapper med zlfn's lag (1). **Spørg zlfn** om vores filter er en acceptabel hurtig-rettelse eller om vi skal vente på hans fulde løsning.
- **#86/#87 z88dk-integration** — vores z88dk-commits (`a3c890e4`, `ad41303b`, `b3802478`) kræver zlfn's arkitektoniske fundament. **Spørg** om vores stykker kan sendes nu eller skal ligge klar.
- **CallingConv / Triple::Z88DK** — infrastruktur allerede i upstream delvist; `a2fb43fe` er lokal tilpasning. **Spørg** om nummereringen er stabiliseret upstream.

---

## Kategoriseret oversigt (ældst → yngst)

| # | Commit  | Emne                                        | Kategori         | Prio |
|---|---------|---------------------------------------------|------------------|------|
| 1 | `bafc8358` | trunc-global-address-byte reloc names        | REIMPLEMENT-TEST | lav  |
| 2 | `855189fb` | Fused 16-bit division (zlfn's commit!)       | DROP             | —    |
| 3 | `a3c890e4` | z88dk assembly print default (zlfn's!)       | DROP → z88dk-wip | —    |
| 4 | `ad41303b` | z88dk runtime calls (zlfn's!)                | DROP → z88dk-wip | —    |
| 5 | `b3802478` | z88dk byte divide (zlfn's!)                  | DROP → z88dk-wip | —    |
| 6 | `d54e6464` | Failing lit test for #413                    | REIMPLEMENT      | høj  |
| 7 | `c8b0951f` | NonReentrant inline-asm edge-filter          | UPSTREAM-ALIGN   | høj  |
| 8 | `f5f9f573` | **SPLIT**: COMPARE8_IND + CP(HL) fold        | REIMPLEMENT (×2) | høj  |
| 9 | `05ea8cb3` | LD A,(nn) / LD (nn),A fold                   | REIMPLEMENT      | høj  |
| 10 | `52da8d9b` | OR (HL) fold test (pre-landing)              | REIMPLEMENT-TEST | med  |
| 11 | `d44f26a8` | OR (HL) fold                                 | REIMPLEMENT      | høj  |
| 12 | `2814590b` | Memory-fold family: INC/DEC/AND/XOR/ADD/SUB  | REIMPLEMENT      | høj  |
| 13 | `eb8b6653` | CP (HL) pointer-loop lit test                | REIMPLEMENT-TEST | lav  |
| 14 | `ceaa4997` | TTI LSR cost-model hooks                     | REIMPLEMENT      | med  |
| 15 | `f3584d08` | Reloc name alignment test                    | DROP (dup af #1) | —    |
| 16 | `dc3e2a6e` | Prefer HL for commutative 16-bit add         | REIMPLEMENT      | med  |
| 17 | `f3998339` | inc/dec mem zero-compare test                | REIMPLEMENT-TEST | med  |
| 18 | `cb2c9261` | Fold compare-zero + memory DEC/INC (HL)      | REIMPLEMENT      | høj  |
| 19 | `4e93072b` | CMake: z88dk-z80asm HINTS                    | DROP → z88dk-wip | —    |
| 20 | `fe31d750` | compiler-rt: `.globl ___umulhi3`             | REIMPLEMENT      | med  |
| 21 | `e0cbd3fa` | libcalls: mul-family under z88dk env         | DROP → z88dk-wip | —    |
| 22 | `a2fb43fe` | Rebase-fixes: **SPLIT** (CC+Triple → main, z88dk API → z88dk-wip) | SPLIT | høj |

---

## Anbefalet implementeringsrækkefølge (med afhængigheder)

### Fase 1 — Memory-fold familien (størst firmware-impact)

Direkte adresserer BSS load/store-trafikken (30–48 % af store funktioner). Hver fold reducerer `LD A,(HL)` + `<OP> r` → `<OP> (HL)` (2 B → 1 B pr. fold).

#### 1.1 — COMPARE8_IND pseudo + GR16_HL (del 1 af `f5f9f5`)

**Filer:** `Z80InstrInfo.td`, `Z80RegisterInfo.td`, `Z80InstrInfo.cpp`.
**Skeleton:**
```tablegen
// Z80RegisterInfo.td
def GR16_HL : RegisterClass<"Z80", [i16], 16, (add HL)>;

// Z80InstrInfo.td
def COMPARE8_IND : Z80Pseudo<(outs), (ins Ac:$lhs, GR16_HL:$addr)> {
  let Defs = [F];
  let mayLoad = true;
}
```
Post-RA expansion: `CP (HL)` (opcode `BE`).
**Lit:** `llvm/test/CodeGen/Z80/compare8-ind-pseudo.mir` — MIR-niveau test der viser expansion.
**E2e:** ikke nødvendig alene (dækkes af 1.2).

#### 1.2 — CP (HL) folding i instruction selector (del 2 af `f5f9f5`)

**Filer:** `Z80InstructionSelector.cpp` (`emitCP`, `emitEqualityTest`).
**Pattern:**
```cpp
if (FlagsOnly && RHSDef->getOpcode() == G_LOAD && hasOneNonDBGUse(RHS)) {
  Register AddrReg = RHSDef->getOperand(1).getReg();
  if (constrainGenericRegister(AddrReg, Z80::GR16_HLRegClass, MRI)) {
    // Build COMPARE8_IND, erase G_LOAD
  }
}
```
**Lit:** `llvm/test/CodeGen/Z80/cp-hl-fold.ll` — `CHECK: cp (hl)` og `CHECK-NOT: ld a, (hl)` for både `==` og `<`.
**E2e:** `z80-test/e2e/c/test_74_cp_hl_fold.c` — scan en pointer efter sentinel-byte, returnér antal matches.
**Afhænger af:** 1.1.

#### 1.3 — LD A,(nn) / LD (nn),A fold (`05ea8cb3`)

**Filer:** `Z80InstrInfo.td` (nye pseudo'er `LOAD8_ABS`/`STORE8_ABS` eller direkte pattern med `tglobaladdr`), `Z80InstrInfo.cpp`, `Z80InstructionSelector.cpp`.
**Motivation:** Volatile `uint8_t *` på fast adresse → 3-byte `LD A,(nn)` i stedet for `LD HL,nn` + `LD A,(HL)` (5 B).
**Lit:** `llvm/test/CodeGen/Z80/load-store-abs.ll` — `CHECK: ld a, (0x8000)` for `*(volatile uint8_t*)0x8000`.
**E2e:** `test_75_abs8_load_store.c` med statisk `uint8_t` på fast adresse (via linker script eller `__attribute__((section))`).
**Afhænger af:** ingen.

#### 1.4 — OR (HL) fold (`d44f26a8` + test `52da8d9b`)

**Filer:** `Z80InstructionSelector.cpp` — udvid `emitAluOp8` til at folde single-use G_LOAD af RHS.
**Pattern:** samme som CP(HL), men for `G_OR`.
**Lit:** `llvm/test/CodeGen/Z80/or-hl-fold.ll` — `CHECK: or (hl)`.
**E2e:** `test_72_or_hl_indirect.c` findes allerede (behold som-er).

#### 1.5 — Memory-fold family (AND/XOR/ADD/SUB + INC/DEC (HL)) (`2814590b`)

Generaliser 1.4 til alle fem binære 8-bit ops + de to unære memory-ops. INC/DEC (HL) skal fanges fra `G_LOAD → G_ADD +1/-1 → G_STORE`-mønsteret (read-modify-write) hvor adressen er single-use.
**Lit:** én fil pr. op: `and-hl-fold.ll`, `xor-hl-fold.ll`, `add-hl-fold.ll`, `sub-hl-fold.ll`, `inc-hl-fold.ll`, `dec-hl-fold.ll`.
**E2e:** `test_73_incdec_hl_indirect.c` findes allerede. Tilføj `test_76_binop_hl_indirect.c` der dækker AND/XOR/ADD/SUB.
**Commits:** 6 separate commits (én pr. op) — upstream review tåler ikke én stor fold-dump.

#### 1.6 — Fold compare-against-zero + memory DEC/INC (HL) (`cb2c9261` + test `f3998339`)

Specialisering: `if (--*p == 0)` → ét enkelt `DEC (HL)` sætter Z-flaget direkte.
**Filer:** `Z80InstructionSelector.cpp` (eller `Z80LateOptimization.cpp` peephole).
**Lit:** `llvm/test/CodeGen/Z80/dec-hl-zero-compare.ll` — skal matche `dec (hl)` + `jr z, ...` uden mellemliggende `cp 0`.
**E2e:** `test_77_dec_hl_zero_loop.c` — countdown-loop på pointer.
**Afhænger af:** 1.5.

### Fase 2 — NonReentrant / static-frames korrekthed

#### 2.1 — Failing lit test for #413 (`d54e6464`)

Behold som "canary"-test, men i den reimplementerede version behøver den ikke være failing — den skal være positiv-check der passerer efter 2.2.
**Fil:** `llvm/test/CodeGen/Z80/static-frames-isr-inline-asm.ll` (eksisterer).
**Afhænger af:** 2.2.

#### 2.2 — NonReentrant inline-asm edge-filter (`c8b0951f`)

**UPSTREAM-ALIGN:** koordinér med zlfn (#74). Hvis zlfn's "inline asm = non-reentrant default" accepteres som løsning, er vores filter overflødigt. Hvis han vil se et PR allerede, send dette som forberedelse.
**Fil:** `Z80NonReentrant.cpp` — skriv edges fra inline-asm call-sites til `CallsExternalNode` fra, kør SCC-walk, gendan.
**Lit:** 2.1-testen.
**E2e:** `test_78_isr_inline_asm_static_frame.c` — ISR med `__asm__("ei")` + foreground main; verificér via symbol-size at `.frame`-symbolerne mangler for ikke-delte funktioner. (Dette er svært at e2e-teste rent runtime; accepter lit-only her og note det i commit-beskeden.)

### Fase 3 — Codegen-kvalitet (ikke-fold)

#### 3.1 — Prefer HL for commutative 16-bit add (`dc3e2a6e`)

Kig på diff for `dc3e2a6e` i den eksisterende `main`-branch som reference:
`git show dc3e2a6e -- llvm/lib/Target/Z80/Z80InstructionSelector.cpp`

Ændringen er i `Z80InstructionSelector.cpp` — ved selektion af `G_ADD` (16-bit) tjekker den om én operand allerede er i HL (via registerklasse-info) og bytter operandrækkefølgen så HL-operanden forbliver i HL. Undgår en `EX DE,HL`.
**Lit:** `ptr-add-hl-swap.ll` (eksisterer i main — kopier som reference, opdatér CHECK-linjer til ny baseline).
**E2e:** `test_79_commutative_add_hl.c` — beregning der folder pointer + offset; verificér korrekt resultat.

#### 3.2 — TTI LSR cost-model hooks (`ceaa4997`)

**Fil:** `Z80TargetTransformInfo.{h,cpp}` — implementér `getArithmeticInstrCost`, `getAddressComputationCost`.
**Lit:** `indexiv-narrow.ll` findes (behold).
**E2e:** `test_80_lsr_djnz.c` — simpel for-loop; forventer `djnz`.

### Fase 4 — Lit-test-vedligehold

#### 4.1 — Trunc-global-address-byte reloc names (`bafc8358`)

Rens: dette er ren test-opdatering fordi Z80.def reloc-navnene ændrede. `f3584d08` er en duplikat — DROP.
**Fil:** `llvm/test/CodeGen/Z80/trunc-global-address-byte.ll`.

#### 4.2 — CP (HL) pointer-loop test (`eb8b6653`)

Behold filen `cp-hl-pointer-loop.ll` — pinner at 1.2-folden overlever loop-strukturen.
**Afhænger af:** 1.1, 1.2.

### Fase 5 — z88dk-integration (z88dk-wip branch)

Branch `z88dk-wip` er oprettet fra `upstream/main` med zlfn's fire z88dk-commits. Ravn-specifikt z88dk-arbejde (`e0cbd3fa` libcalls, `4e93072b` CMake, z88dk-delen af `a2fb43fe`) cherry-pickes hertil under reimplementeringen.

Sendes koordineret med zlfn når #86/#87 lander. Ikke upstream før da.

### Fase 7 — Implementer #74 (alle tre lag)

**STOP: Få arkitektur-godkendelse fra zlfn FØR kode skrives.** Beskriv de tre lag i en kommentar på issue #74 og afvent bekræftelse. Kode skrives KUN efter "ja" fra zlfn.

**7.1 — Lag 1: Inline asm = non-reentrant**
Reference: `c8b0951` på `main`-branch (`git show c8b0951 -- llvm/lib/Target/Z80/Z80NonReentrant.cpp`).
Implementering: `Z80NonReentrant.cpp` — iterer `CallGraph`, find kanter til `CallsExternalNode` hvor `dyn_cast<CallBase>(*I->first)->isInlineAsm()`, gem i `SmallVector<pair<CGN*,CallBase*>>`, fjern med `removeCallEdge`. Kør SCC-walk. Gendan med `addCalledFunction`.
Lit: `static-frames-isr-inline-asm.ll` (kopier fra `main`, CHECK-linjer skal vise `CHECK-NOT: push` for foreground main).

**7.2 — Lag 2: `__attribute__((target("no-callback")))`**
Mekanisme: identisk med eksisterende `no-static-frame`-attribut i `Z80.td` (`FeatureNoStaticFrame` som model).
1. `Z80.td`: tilføj `def FeatureNoCallback : SubtargetFeature<"no-callback", "NoCallback", "true", "...">`.
2. `Z80Subtarget.h`: bool `NoCallback = false`.
3. `Z80NonReentrant.cpp`: ved opbygning af CallsExternal→ExternalCalling-kanten, skip call sites hvor `TM.getSubtargetImpl(*Callee)->getFeatureBits()[Z80::FeatureNoCallback]` er sand.
Lit: `no-callback-attr.ll` — `declare void @ext() #0` med `attributes #0 = { "target-features"="+no-callback" }`; `CHECK-NOT: push` i kaldende funktion.

**7.3 — Lag 3: `+no-callbacks` global flag**
1. `Z80.td`: `def FeatureAssumeNoCallbacks : SubtargetFeature<"no-callbacks", "AssumeNoCallbacks", "true", "...">`.
2. `Z80Subtarget.h`: bool `AssumeNoCallbacks = false`.
3. `Z80NonReentrant.cpp`: hvis `STI.assumeNoCallbacks()`, spring hele tilføjelsen af `CallsExternal→ExternalCalling`-kanten over.
Lit: `assume-no-callbacks.ll` — `call void @putchar(i8 65)` i main med `+no-callbacks`; `CHECK-NOT: push` i main.
E2e: `test_81_assume_no_callbacks.c` — main kalder extern funktion, bekræft korrekt output kompileret med `-mattr=+no-callbacks`.

### Fase 6 — Infrastruktur

#### 6.1 — compiler-rt `.globl ___umulhi3` (`fe31d750`)

Lille fix; let at forklare. Send som isoleret PR.
**Fil:** `compiler-rt/lib/builtins/z80/umulhisi3.asm`.
**Test:** eksisterende multiplikationstests skal linke uden workaround.

#### 6.2 — CMake HINTS + source-eksklusion (`4e93072b`)

Byggeinfrastruktur — koordinér med zlfn før upstream-send; sandsynligvis for specifikt til at være upstream-interessant. Behold som ravn-lokal patch.

#### 6.3 — Rebase-fixes (`a2fb43fe`)

Udelukkende konsekvens af upstream-ændringer; reimplementeres ikke som eget commit. Smelt ind i de relevante feature-commits efter behov.

---

## Dropped commits (begrundelse)

- **`855189fb`** — forfatter er `zlfn <ung@zlfn.space>`. Er IKKE i `upstream/main` — er zlfn's z88dk-WIP. Fjernes fra `main` automatisk via reimplementering fra bunden på `reimpl`-branch. Lever på `z88dk-wip`.
- **`f3584d08`** — duplikerer `bafc8358`. Fjernes på samme måde.
- **`a2fb43fe`** — pure rebase-noise. Indholdet smeltets ind i de relevante feature-commits under reimplementeringen.

---

## Autoritativ implementeringsrækkefølge (ét PR pr. punkt)

Implementér i denne rækkefølge på `reimpl`-branch. Hvert punkt = ét commit + ét PR til llvm-z80/llvm-z80 (efter bruger-godkendelse).

| Trin | Fase | Hvad | Prereq | Status / Commit |
|------|------|------|--------|-----------------|
| 0 | start | Opret `reimpl` fra `upstream/main`, byg toolchain, tag baseline | — | ✅ Udført |
| 1 | 6.1 | compiler-rt `.globl ___umulhi3` | — | ✅ `a259d40c6c70` |
| 2 | 4.1 | Trunc-global-address reloc test-opdatering | — | ✅ Allerede grøn i upstream |
| 3 | 1.1 | COMPARE8_IND pseudo + GR16_HL | — | ✅ `625e3f46ce65` |
| 4 | 1.2 | CP (HL) fold i instruction selector | trin 3 | ✅ `69254b033824` |
| 5 | 1.3 | LD A,(nn) / LD (nn),A fold | — | ✅ `4525c2473626` |
| 6 | 1.4 | OR (HL) fold | — | ✅ `f42f03c1a223` |
| 7 | 1.5a | AND (HL) fold | — | ✅ `7c4b7d23bdb8` |
| 8 | 1.5b | XOR (HL) fold | — | ✅ `7c4b7d23bdb8` |
| 9 | 1.5c | ADD (HL) fold | — | ✅ `7c4b7d23bdb8` |
| 10 | 1.5d | SUB (HL) fold | — | ✅ `7c4b7d23bdb8` |
| 11 | 1.5e | INC (HL) fold | — | ✅ `104c1f9d2e77` |
| 12 | 1.5f | DEC (HL) fold | — | ✅ `104c1f9d2e77` |
| 13 | 1.6 | DEC/INC (HL) + zero-compare | trin 11-12 | ✅ `e68dc200d0a6` |
| 14 | 3.1 | Prefer HL for commutative 16-bit add | — | ✅ `ff46cfc1bead` |
| 15 | 3.2 | TTI LSR cost-model hooks (+ CP pointer loop test 4.2) | — | ✅ `d6d20f71e8ee` |
| 16 | 2.1+2.2 | NonReentrant inline-asm filter + lit test | — | ✅ `e00a88aa5550` |
| 17 | 7.1-7.3 | #74 alle tre lag | — | ✅ Lag 1: `e00a88aa5550`, Lag 2-3: `b22ded7f1194` |

z88dk-stakken (Fase 5) venter på `z88dk-wip` branch.

---

## Kvalitetstjekliste pr. commit

- [ ] Ét problem / én logisk ændring
- [ ] FileCheck-lit test i `llvm/test/CodeGen/Z80/` der fejler uden ændringen
- [ ] C e2e i `z80-test/e2e/c/` med `/* expect 0xNNNN */` (hvis runtime-observerbart)
- [ ] Berørte eksisterende `CHECK`-linjer opdateret i samme commit (kør baseline-diff)
- [ ] `llvm-lit llvm/test/CodeGen/Z80/ -q` grøn — ingen uventede fejl
- [ ] `cd z80-utils && BUILD_DIR=../build-macos-asserts cargo run -- clang` grøn
- [ ] Firmware boot-test (`make -C autoload-in-c mame` + `make -C rcbios-in-c mame-test`) — KUN relevant fra Fase 7, se "Firmware-test blokeret"-note
- [ ] CI grøn: `gh run list --repo llvm-z80/llvm-z80` efter push
- [ ] Commit message forklarer **hvorfor** (ikke bare hvad), peger på issue-nummer hvis relevant
- [ ] Per-filing go-ahead fra bruger før `gh pr create`

## Åbne spørgsmål (alle besvaret 2026-11-14)

1. ✅ `c8b0951`: Vi implementerer selv alle tre lag af #74 som PR (Fase 7).
2. ✅ z88dk-stakken: `z88dk-wip` branch oprettet; venter på zlfn's #86/#87.
3. ✅ `855189fb`: zlfn's WIP, ikke i upstream/main. Fjernes via reimplementering fra bunden.
4. ✅ NonReentrant e2e: Lit-only accepteret.
