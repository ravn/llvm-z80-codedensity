#!/usr/bin/env python3
"""Run Whetstone and Dhrystone on the LLVM-Z80 default-CC experiment."""

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[3]
Z88DK = WORKSPACE / "z88dk"
CLANG = WORKSPACE / "llvm-z80/build-macos-asserts/bin/clang"
TMP = WORKSPACE / "scratch/tmp"

POLICY = {
    "whetstone": {
        "z88dk_fastcall": ("PA",),
        "z88dk_callee": ("P3",),
    },
    "dhrystone": {
        "z88dk_fastcall": ("Proc_1", "Proc_2", "Proc_3", "Func_3"),
        "z88dk_callee": ("Proc_6", "Proc_7", "Proc_8", "Func_1", "Func_2"),
    },
}

F32_FIELDS = (
    "module2.e1[1]", "module2.e1[2]", "module2.e1[3]", "module2.e1[4]",
    "module3.e1[1]", "module3.e1[2]", "module3.e1[3]", "module3.e1[4]",
    "module7.x", "module7.y", "module8.z",
    "module9.e1[1]", "module9.e1[2]", "module9.e1[3]", "module9.e1[4]",
    "module11.x",
)
I16_FIELDS = (
    "module4.j", "module6.j", "module6.k", "module6.l",
    "module9.j", "module9.k", "module9.l",
)
DHR_NUMERIC_FIELDS = (
    "Int_Glob", "Bool_Glob", "Ch_1_Glob", "Ch_2_Glob", "Arr_1_Glob[8]",
    "Arr_2_Glob[8][7]", "Ptr_Glob.Discr", "Ptr_Glob.Enum_Comp",
    "Ptr_Glob.Int_Comp", "Next_Ptr_Glob.Discr",
    "Next_Ptr_Glob.Enum_Comp", "Next_Ptr_Glob.Int_Comp", "Int_1_Loc",
    "Int_2_Loc", "Int_3_Loc", "Enum_Loc",
)
DHR_STRING_FIELDS = (
    "Ptr_Glob.Str_Comp", "Next_Ptr_Glob.Str_Comp", "Str_1_Loc", "Str_2_Loc",
)
DHR_STRINGS = (
    "DHRYSTONE PROGRAM, SOME STRING",
    "DHRYSTONE PROGRAM, SOME STRING",
    "DHRYSTONE PROGRAM, 1'ST STRING",
    "DHRYSTONE PROGRAM, 2'ND STRING",
)
DHR_EXPECTED = (5, 1, ord("A"), ord("B"), 7, 20010, 0, 2, 17, 0, 1, 18,
                5, 13, 7, 1)
DHR_RUNS = 20000
TICKS_LIMIT = 500_000_000

SPEC = importlib.util.spec_from_file_location("default_cc_run", HERE / "run.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load the shared default-CC harness helpers")
DEFAULT_CC = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEFAULT_CC
SPEC.loader.exec_module(DEFAULT_CC)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def i16(value):
    if not -32768 <= value <= 32767:
        raise RuntimeError(f"Whetstone integer reference overflows int16: {value}")
    return value


def whetstone_reference():
    """Independent Python implementation with binary32 rounding per operation."""
    add = lambda a, b: f32(a + b)
    sub = lambda a, b: f32(a - b)
    mul = lambda a, b: f32(a * b)
    div = lambda a, b: f32(a / b)
    t, t1, t2 = f32(0.499975), f32(0.50025), f32(2.0)
    loop = 10
    e = [f32(0.0)] * 5
    e[1:5] = [f32(1.0), f32(-1.0), f32(-1.0), f32(-1.0)]

    for _ in range(12 * loop):
        e[1] = mul(sub(add(add(e[1], e[2]), e[3]), e[4]), t)
        e[2] = mul(add(sub(add(e[1], e[2]), e[3]), e[4]), t)
        e[3] = mul(add(add(sub(e[1], e[2]), e[3]), e[4]), t)
        e[4] = mul(add(add(add(-e[1], e[2]), e[3]), e[4]), t)
    module2 = e[1:5]

    for _ in range(14 * loop):
        for _ in range(6):
            e[1] = mul(sub(add(add(e[1], e[2]), e[3]), e[4]), t)
            e[2] = mul(add(sub(add(e[1], e[2]), e[3]), e[4]), t)
            e[3] = mul(add(add(sub(e[1], e[2]), e[3]), e[4]), t)
            e[4] = div(add(add(add(-e[1], e[2]), e[3]), e[4]), t2)
    module3 = e[1:5]

    j = 1
    for _ in range(345 * loop):
        j = 2 if j == 1 else 3
        j = 0 if j > 2 else 1
        j = 1 if j < 1 else 0
    module4_j = j

    j, k, l = 1, 2, 3
    for _ in range(210 * loop):
        j = i16(i16(j * (k - j)) * (l - k))
        k = i16(i16(l * k) - i16(i16(l - j) * k))
        l = i16(i16(l - k) * i16(k + j))
        if not 1 <= l - 1 < len(e) or not 1 <= k - 1 < len(e):
            raise RuntimeError(f"Whetstone module 6 index out of range: {j},{k},{l}")
        e[l - 1] = f32(j + k + l)
        e[k - 1] = f32(j * k * l)
    module6 = (j, k, l)

    x, y = f32(0.5), f32(0.5)
    for _ in range(32 * loop):
        denominator = sub(sub(add(f32(math.cos(add(x, y))),
                                  f32(math.cos(sub(x, y)))), f32(1.0)), f32(0.0))
        numerator = mul(mul(t2, f32(math.sin(x))), f32(math.cos(x)))
        x = mul(t, f32(math.atan(div(numerator, denominator))))
        denominator = sub(sub(add(f32(math.cos(add(x, y))),
                                  f32(math.cos(sub(x, y)))), f32(1.0)), f32(0.0))
        numerator = mul(mul(t2, f32(math.sin(y))), f32(math.cos(y)))
        y = mul(t, f32(math.atan(div(numerator, denominator))))
    module7 = (x, y)

    x, y = f32(1.0), f32(1.0)
    for _ in range(899 * loop):
        x1 = mul(t, add(x, y))
        y1 = mul(t, add(x1, y))
        z = div(add(x1, y1), t2)
    module8_z = z

    j, k, l = 1, 2, 3
    e[1:4] = [f32(1.0), f32(2.0), f32(3.0)]
    for _ in range(616 * loop):
        e[j] = e[k]
        e[k] = e[l]
        e[l] = e[j]
    module9 = (j, k, l, *e[1:5])

    x = f32(0.75)
    for _ in range(93 * loop):
        x = f32(math.sqrt(f32(math.exp(div(f32(math.log(x)), t1)))))
    module11_x = x

    floats = (*module2, *module3, *module7, module8_z, *module9[3:], module11_x)
    integers = (module4_j, *module6, *module9[:3])
    if len(floats) != len(F32_FIELDS) or len(integers) != len(I16_FIELDS):
        raise RuntimeError("Whetstone reference field table is inconsistent")
    if not (0.49 < module7[0] < 0.50 and 0.49 < module7[1] < 0.50
            and 0.99 < module8_z < 1.01 and 0.83 < module11_x < 0.84):
        raise RuntimeError("Independent Whetstone reference failed its sanity bounds")
    return {"float32": dict(zip(F32_FIELDS, floats)),
            "int16": dict(zip(I16_FIELDS, integers))}


def replace_once(source, old, new, description):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{description}: expected one source match, found {count}")
    return source.replace(old, new, 1)


def annotate_functions(source, names, attribute, expected_count, file_label):
    for name, count_expected in expected_count.items():
        pattern = rf"^((?:void|Enumeration|Boolean)\s+)({name}\s*\()"
        source, count = re.subn(
            pattern, rf"\1__attribute__(({attribute})) \2",
            source, flags=re.MULTILINE)
        if count != count_expected:
            raise RuntimeError(
                f"Annotation policy {file_label}:{name} matched {count}, "
                f"expected {count_expected}")
    if set(expected_count) - set(names):
        raise RuntimeError(f"Unexpected annotation entry in {file_label}")
    return source


def verify_workload_assembly(benchmark, assemblies):
    sources = [path.read_text() for path in assemblies]
    if benchmark == "whetstone":
        main = next((text.split("_main:", 1)[1].split("; -- End function", 1)[0]
                     for text in sources if "_main:" in text), "")
        if not re.search(r"\bcall\s+_PA\b", main):
            raise RuntimeError("Whetstone module 3 PA call was optimized away")
        if not re.search(r"\bcall\s+_bench_module6\b", main):
            raise RuntimeError("Whetstone module 6 helper call was optimized away")
        main_labels = {
            match.group(1): match.start()
            for match in re.finditer(r"(?m)^\s*(LBB\d+_\d+):", main)
        }
        main_branches = list(re.finditer(
            r"\b(?:jr|jp)\s+(?:(?:nz|z|nc|c|po|pe|p|m)\s*,\s*)?"
            r"(LBB\d+_\d+)\b", main))
        main_backedges = {
            branch.group(1) for branch in main_branches
            if main_labels.get(branch.group(1), len(main)) < branch.start()
        }
        if len(main_backedges) < 7:
            raise RuntimeError("A repeated Whetstone module loop was optimized away")
        call = re.search(r"\bcall\s+_P3\b", main)
        if not call:
            raise RuntimeError("Whetstone module 8 P3 call was optimized away")
        before = main[:call.start()]
        after = main[call.end():]
        labels = re.findall(r"^\s*(LBB\d+_\d+):", before, re.MULTILINE)
        if not labels:
            raise RuntimeError("Whetstone P3 call has no enclosing loop block")
        branches = re.findall(
            r"\b(?:jr|jp)\s+(?:(?:nz|z|nc|c|po|pe|p|m)\s*,\s*)?"
            r"(LBB\d+_\d+)\b", after)
        if labels[-1] not in branches:
            raise RuntimeError("Whetstone P3 call is not inside a repeated loop")
        module6 = next((text.split("_bench_module6:", 1)[1]
                        .split("; -- End function", 1)[0]
                        for text in sources if "_bench_module6:" in text), "")
        block_labels = {
            match.group(1): match.start()
            for match in re.finditer(r"(?m)^\s*(LBB\d+_\d+):", module6)
        }
        for branch in re.finditer(
                r"\b(?:jr|jp)\s+(?:(?:nz|z|nc|c|po|pe|p|m)\s*,\s*)?"
                r"(LBB\d+_\d+)\b", module6):
            start = block_labels.get(branch.group(1), len(module6))
            if start < branch.start():
                loop = module6[start:branch.start()]
                stores = len(re.findall(r"\bld\s+\(hl\)\s*,", loop))
                arithmetic = len(re.findall(
                    r"\b(?:add|adc|sub|sbc|mul|xor|and|or)\b", loop))
                if stores >= 2 and arithmetic >= 2:
                    return
        raise RuntimeError("Whetstone module 6 integer loop was optimized away")
    combined = "\n".join(sources)
    for name in ("Func_2", "Proc_7", "Proc_8", "Proc_1", "Func_1", "Proc_6"):
        if not re.search(rf"\bcall\s+_{name}\b", combined):
            raise RuntimeError(f"Dhrystone {name} call was optimized away")


def whetstone_original_compute_source(original, variant, observe):
    source = replace_once(original, "int\nmain(int argc, char *argv[])\n{",
                          "int\nmain(void)\n{",
                          "fix Whetstone to its fixed, argument-free workload")
    declarations = ""
    if observe:
        declarations = """static volatile double_t bench_f[16];
static volatile int bench_i[7];

_Static_assert(sizeof(double_t) == sizeof(unsigned long),
               "Whetstone values must be IEEE binary32");

static void bench_emit_u32(unsigned long value)
{
   static const char hex[] = "0123456789ABCDEF";
   int shift;
   for (shift = 28; shift >= 0; shift -= 4)
      putchar(hex[(value >> shift) & 15]);
   putchar('\\n');
}

static void bench_emit_u16(unsigned int value)
{
   static const char hex[] = "0123456789ABCDEF";
   int shift;
   for (shift = 12; shift >= 0; shift -= 4)
      putchar(hex[(value >> shift) & 15]);
   putchar('\\n');
}

static void bench_emit_f32(double_t value)
{
   union {
      double_t f;
      unsigned long bits;
   } representation;
   representation.f = value;
   bench_emit_u32(representation.bits);
}
"""
        source = replace_once(
            source, "int J,K,L;\n",
            "int J,K,L;\n\n" + declarations,
            "add observer-only, lossless Whetstone reporting")
        snapshots = (
            ("POUT(N2,N3,N2,E1[1],E1[2],E1[3],E1[4]);",
             "bench_f[0] = E1[1]; bench_f[1] = E1[2]; "
             "bench_f[2] = E1[3]; bench_f[3] = E1[4];"),
            ("POUT(N3,N2,N2,E1[1],E1[2],E1[3],E1[4]);",
             "bench_f[4] = E1[1]; bench_f[5] = E1[2]; "
             "bench_f[6] = E1[3]; bench_f[7] = E1[4];"),
            ("POUT(N4,J,J,X1,X2,X3,X4);", "bench_i[0] = J;"),
            ("POUT(N6,J,K,E1[1],E1[2],E1[3],E1[4]);",
             "bench_i[1] = J; bench_i[2] = K; bench_i[3] = L;"),
            ("POUT(N7,J,K,X,X,Y,Y);", "bench_f[8] = X; bench_f[9] = Y;"),
            ("POUT(N8,J,K,X,Y,Z,Z);", "bench_f[10] = Z;"),
            ("POUT(N9,J,K,E1[1],E1[2],E1[3],E1[4]);",
             "bench_i[4] = J; bench_i[5] = K; bench_i[6] = L; "
             "bench_f[11] = E1[1]; bench_f[12] = E1[2]; "
             "bench_f[13] = E1[3]; bench_f[14] = E1[4];"),
            ("POUT(N11,J,K,X,X,X,X);", "bench_f[15] = X;"),
        )
        for call, code in snapshots:
            anchor = f"#ifdef PRINTOUT\n   IF (JJ==II) {call}\n#endif"
            source = replace_once(source, anchor, code + "\n\n" + anchor,
                                  f"record original-compute {call}")

    output = []
    if observe:
        output.extend(
            [f"   bench_emit_f32(bench_f[{index}]);"
             for index in range(len(F32_FIELDS))]
            + [f"   bench_emit_u16((unsigned int)bench_i[{index}]);"
               for index in range(len(I16_FIELDS))])
    output.extend(['   puts("PASS");', "   return 0;"])
    source = replace_once(source, "TIMER_STOP();\n\n#ifdef TIMEFUNC",
                          "TIMER_STOP();\n\n" + "\n".join(output)
                          + "\n\n#ifdef TIMEFUNC",
                          "emit original-compute completion marker")
    if variant == "C":
        source = annotate_functions(
            source, ("PA",), "z88dk_fastcall", {"PA": 2},
            "Whetstone fastcall")
        source = annotate_functions(
            source, ("P3",), "z88dk_callee", {"P3": 2},
            "Whetstone callee")
    return source


def whetstone_source(original, variant, observe, mode):
    if mode == "original-compute":
        return whetstone_original_compute_source(original, variant, observe)
    source = original
    source = replace_once(source, "int\nmain(int argc, char *argv[])\n{",
                          "int\nmain(void)\n{",
                          "fix Whetstone to its fixed, argument-free workload")
    source = replace_once(
        source, "void P3(double_t X, double_t Y, double_t *Z);",
        "void P3(double_t X, double_t Y, double_t *Z);\n"
        "void __attribute__((z88dk_fastcall)) bench_module6(long N6);",
        "declare the fixed-ABI module-6 benchmark helper")
    declarations = ("static volatile double_t bench_f[16];\n"
                    "static volatile int bench_i[7];\n")
    if observe:
        declarations += """_Static_assert(sizeof(double_t) == sizeof(unsigned long),
               "Whetstone values must be IEEE binary32");

static void bench_emit_u32(unsigned long value)
{
   static const char hex[] = "0123456789ABCDEF";
   int shift;
   for (shift = 28; shift >= 0; shift -= 4)
      putchar(hex[(value >> shift) & 15]);
   putchar('\\n');
}

static void bench_emit_u16(unsigned int value)
{
   static const char hex[] = "0123456789ABCDEF";
   int shift;
   for (shift = 12; shift >= 0; shift -= 4)
      putchar(hex[(value >> shift) & 15]);
   putchar('\\n');
}

static void bench_emit_f32(double_t value)
{
   union {
      double_t f;
      unsigned long bits;
   } representation;
   representation.f = value;
   bench_emit_u32(representation.bits);
}
"""
    source = replace_once(
        source, "int J,K,L;\n",
        "int J,K,L;\n\n_Static_assert(sizeof(double_t) == sizeof(unsigned long), "
        "\"Whetstone values must be IEEE binary32\");\n\n" + declarations,
        "add lossless Whetstone result reporting")
    source = replace_once(
        source, """   for (I = 1L; I <= N6; I++)
   {
       J = J * (K-J) * (L-K);
       K = L * K - (L-J) * K;
       L = (L-K) * (K+J);
       E1[L-1] = J + K + L;
       E1[K-1] = J * K * L;
   }""",
        "   bench_module6(N6);",
        "isolate the module-6 integer loop from caller constant folding")
    snapshots = (
        ("POUT(N2,N3,N2,E1[1],E1[2],E1[3],E1[4]);",
         "bench_f[0] = E1[1]; bench_f[1] = E1[2]; "
         "bench_f[2] = E1[3]; bench_f[3] = E1[4];"),
        ("POUT(N3,N2,N2,E1[1],E1[2],E1[3],E1[4]);",
         "bench_f[4] = E1[1]; bench_f[5] = E1[2]; "
         "bench_f[6] = E1[3]; bench_f[7] = E1[4];"),
        ("POUT(N4,J,J,X1,X2,X3,X4);", "bench_i[0] = J;"),
        ("POUT(N6,J,K,E1[1],E1[2],E1[3],E1[4]);",
         "bench_i[1] = J; bench_i[2] = K; bench_i[3] = L;"),
        ("POUT(N7,J,K,X,X,Y,Y);", "bench_f[8] = X; bench_f[9] = Y;"),
        ("POUT(N8,J,K,X,Y,Z,Z);", "bench_f[10] = Z;"),
        ("POUT(N9,J,K,E1[1],E1[2],E1[3],E1[4]);",
         "bench_i[4] = J; bench_i[5] = K; bench_i[6] = L; "
         "bench_f[11] = E1[1]; bench_f[12] = E1[2]; "
         "bench_f[13] = E1[3]; bench_f[14] = E1[4];"),
        ("POUT(N11,J,K,X,X,X,X);", "bench_f[15] = X;"),
    )
    for call, code in snapshots:
        anchor = f"#ifdef PRINTOUT\n   IF (JJ==II) {call}\n#endif"
        source = replace_once(source, anchor, code + "\n\n" + anchor,
                              f"record Whetstone {call}")
    output = []
    if observe:
        output.extend(
            [f"   bench_emit_f32(bench_f[{index}]);"
             for index in range(len(F32_FIELDS))]
            + [f"   bench_emit_u16((unsigned int)bench_i[{index}]);"
               for index in range(len(I16_FIELDS))])
    output.extend(['   puts("PASS");', "   return 0;"])
    source = replace_once(source, "TIMER_STOP();\n\n#ifdef TIMEFUNC",
                          "TIMER_STOP();\n\n" + "\n".join(output)
                          + "\n\n#ifdef TIMEFUNC",
                          "emit Whetstone completion marker and observations")
    source = annotate_functions(
        source, ("P3",),
        "z88dk_callee,noinline" if variant == "C" else "noinline",
        {"P3": 2}, "preserve the Whetstone module-8 call loop")
    if variant == "C":
        source = annotate_functions(
            source, ("PA",), "z88dk_fastcall", {"PA": 2},
            "Whetstone fastcall")
    return source


def whetstone_module6_source():
    return """#include <math.h>

extern double_t E1[5];
extern int J, K, L;

void __attribute__((z88dk_fastcall)) bench_module6(long N6)
{
   long I;
   for (I = 1L; I <= N6; I++)
   {
       J = J * (K-J) * (L-K);
       K = L * K - (L-J) * K;
       L = (L-K) * (K+J);
       E1[L-1] = J + K + L;
       E1[K-1] = J * K * L;
   }
}
"""


def dhrystone_sources(header, first, second, variant, observe):
    all_functions = ("Proc_1", "Proc_2", "Proc_3", "Proc_6", "Proc_7",
                     "Proc_8", "Func_1", "Func_2", "Func_3")
    if variant == "C":
        for attribute, names in POLICY["dhrystone"].items():
            header = annotate_functions(
                header, all_functions, attribute, {name: 1 for name in names},
                "dhry.h " + attribute)
            first_names = set(names) & {"Proc_1", "Proc_2", "Proc_3"}
            second_names = set(names) & {
                "Proc_6", "Proc_7", "Proc_8", "Func_1", "Func_2", "Func_3"}
            if first_names:
                expected = {name: (2 if name == "Proc_1" else 1)
                            for name in first_names}
                first = annotate_functions(first, all_functions, attribute,
                                           expected, "dhry_1.c " + attribute)
            if second_names:
                second = annotate_functions(second, all_functions, attribute,
                                            {name: 1 for name in second_names},
                                            "dhry_2.c " + attribute)
    helper = ""
    if observe:
        helper = """static void bench_emit_u16(unsigned int value)
{
   static const char hex[] = "0123456789ABCDEF";
   int shift;
   for (shift = 12; shift >= 0; shift -= 4)
      putchar(hex[(value >> shift) & 15]);
   putchar('\\n');
}
"""
    first = replace_once(first, "void main (void)\n",
                         helper + "\nint main (void)\n",
                         "modernize Dhrystone entry point and add result reporting")
    checks = """if (Int_Glob != 5 || Bool_Glob != 1 || Ch_1_Glob != 'A'
    || Ch_2_Glob != 'B' || Arr_1_Glob[8] != 7
    || Arr_2_Glob[8][7] != 20010
    || Ptr_Glob->Discr != Ident_1
    || Ptr_Glob->variant.var_1.Enum_Comp != Ident_3
    || Ptr_Glob->variant.var_1.Int_Comp != 17
    || strcmp(Ptr_Glob->variant.var_1.Str_Comp,
              "DHRYSTONE PROGRAM, SOME STRING") != 0
    || Next_Ptr_Glob->Discr != Ident_1
    || Next_Ptr_Glob->variant.var_1.Enum_Comp != Ident_2
    || Next_Ptr_Glob->variant.var_1.Int_Comp != 18
    || strcmp(Next_Ptr_Glob->variant.var_1.Str_Comp,
              "DHRYSTONE PROGRAM, SOME STRING") != 0
    || Int_1_Loc != 5 || Int_2_Loc != 13 || Int_3_Loc != 7
    || Enum_Loc != Ident_2
    || strcmp(Str_1_Loc, "DHRYSTONE PROGRAM, 1'ST STRING") != 0
    || strcmp(Str_2_Loc, "DHRYSTONE PROGRAM, 2'ND STRING") != 0)
  {
    puts("FAIL");
    return 1;
  }
"""
    values = (
        "Int_Glob", "Bool_Glob", "(unsigned char)Ch_1_Glob",
        "(unsigned char)Ch_2_Glob", "Arr_1_Glob[8]", "Arr_2_Glob[8][7]",
        "Ptr_Glob->Discr", "Ptr_Glob->variant.var_1.Enum_Comp",
        "Ptr_Glob->variant.var_1.Int_Comp", "Next_Ptr_Glob->Discr",
        "Next_Ptr_Glob->variant.var_1.Enum_Comp",
        "Next_Ptr_Glob->variant.var_1.Int_Comp", "Int_1_Loc", "Int_2_Loc",
        "Int_3_Loc", "Enum_Loc",
    )
    report = ""
    if observe:
        report = "".join(
            f"  bench_emit_u16((unsigned int)({expression}));\n"
            for expression in values)
        report += """  puts(Ptr_Glob->variant.var_1.Str_Comp);
  puts(Next_Ptr_Glob->variant.var_1.Str_Comp);
  puts(Str_1_Loc);
  puts(Str_2_Loc);
"""
    report += """  puts("PASS");
  return 0;
"""
    first = replace_once(first, "TIMER_STOP();\n\n#ifdef TIMEFUNC",
                         "TIMER_STOP();\n\n" + checks + report
                         + "\n#ifdef TIMEFUNC",
                         "check and report published Dhrystone 2.1 results")
    if f"Number_Of_Runs = {DHR_RUNS};" not in first:
        raise RuntimeError("Dhrystone source no longer has the fixed 20,000-run workload")
    return header, first, second


def normalized_lines(output):
    return output.replace("\r", "").splitlines()


def check_whetstone_output(output, reference):
    lines = normalized_lines(output)
    expected_count = len(F32_FIELDS) + len(I16_FIELDS) + 1
    if len(lines) != expected_count or lines[-1] != "PASS":
        raise RuntimeError(
            f"Whetstone did not complete with its PASS marker: {lines[-3:]}")
    floats = {}
    for name, line in zip(F32_FIELDS, lines):
        if not re.fullmatch(r"[0-9A-F]{8}", line):
            raise RuntimeError(f"Invalid binary32 result for {name}: {line!r}")
        actual = struct.unpack("<f", struct.pack("<I", int(line, 16)))[0]
        expected = reference["float32"][name]
        tolerance = 0.0001 + 0.0001 * abs(expected)
        if not math.isfinite(actual) or abs(actual - expected) > tolerance:
            raise RuntimeError(
                f"Whetstone {name}: target={actual:.9g}, host32={expected:.9g}, "
                f"tolerance={tolerance:.4g}")
        floats[name] = {"actual": actual, "expected": expected,
                        "tolerance": tolerance}
    integers = {}
    offset = len(F32_FIELDS)
    for name, line in zip(I16_FIELDS, lines[offset:offset + len(I16_FIELDS)]):
        if not re.fullmatch(r"[0-9A-F]{4}", line):
            raise RuntimeError(f"Invalid integer result for {name}: {line!r}")
        actual = int(line, 16)
        expected = reference["int16"][name] & 0xFFFF
        if actual != expected:
            raise RuntimeError(f"Whetstone {name}: target={actual}, host={expected}")
        integers[name] = {"actual": actual, "expected": expected}
    return {"float32": floats, "int16": integers}


def check_dhrystone_output(output):
    lines = normalized_lines(output)
    expected_lines = (len(DHR_NUMERIC_FIELDS) + len(DHR_STRINGS) + 1)
    if len(lines) != expected_lines or lines[-1] != "PASS":
        raise RuntimeError(f"Dhrystone failed or did not complete: {lines[-3:]}")
    numeric = {}
    for name, line, expected in zip(
            DHR_NUMERIC_FIELDS, lines[:len(DHR_NUMERIC_FIELDS)], DHR_EXPECTED):
        if not re.fullmatch(r"[0-9A-F]{4}", line):
            raise RuntimeError(f"Invalid Dhrystone value for {name}: {line!r}")
        actual = int(line, 16)
        if actual != (expected & 0xFFFF):
            raise RuntimeError(
                f"Dhrystone {name}: target={actual}, published={expected}")
        numeric[name] = actual
    strings = lines[len(DHR_NUMERIC_FIELDS):-1]
    if tuple(strings) != DHR_STRINGS:
        raise RuntimeError(f"Dhrystone published string values differ: {strings}")
    return {"numeric": numeric, "strings": dict(zip(DHR_STRING_FIELDS, strings))}


def check_output(benchmark, output, oracle):
    if benchmark == "whetstone":
        return check_whetstone_output(output, oracle)
    return check_dhrystone_output(output)


def check_pass_marker(output, benchmark):
    lines = normalized_lines(output)
    if lines != ["PASS"]:
        raise RuntimeError(f"{benchmark} completion marker missing: {lines[-3:]}")


def sources_for(benchmark):
    if benchmark == "whetstone":
        return (Z88DK / "support/benchmarks/whetstone/whetstone.c",)
    return (Z88DK / "support/benchmarks/dhrystone21/dhry.h",
            Z88DK / "support/benchmarks/dhrystone21/dhry_1.c",
            Z88DK / "support/benchmarks/dhrystone21/dhry_2.c")


def make_cell_sources(benchmark, variant, cell, observe, whetstone_mode):
    originals = [path.read_text() for path in sources_for(benchmark)]
    for path, text in zip(sources_for(benchmark), originals):
        (cell / path.name).write_text(text)
    if benchmark == "whetstone":
        transformed = whetstone_source(
            originals[0], variant, observe, whetstone_mode)
        main = cell / sources_for(benchmark)[0].name
        main.write_text(transformed)
        if whetstone_mode == "original-compute":
            return [main]
        helper = cell / "whetstone_module6.c"
        helper.write_text(whetstone_module6_source())
        return [main, helper]
    header, first, second = dhrystone_sources(*originals, variant, observe)
    paths = sources_for(benchmark)
    for path, text in zip(paths, (header, first, second)):
        (cell / path.name).write_text(text)
    return [cell / path.name for path in paths[1:]]


def build_and_run(benchmark, opt, variant, oracle, env0, artifacts, cycle_limit,
                  whetstone_mode):
    artifact = artifacts / f"{benchmark}-{opt}-{variant}"
    artifact.mkdir()
    with tempfile.TemporaryDirectory(
            prefix=f"default-cc-{benchmark}-{opt}-{variant}.", dir=TMP) as raw:
        work = Path(raw)
        flags = [] if variant == "baseline" else [
            "-Cg-fdefault-calling-conv=" +
            ("sdcccall1" if variant == "A" else "sdcccall0")]
        def compile_variant(directory, observe):
            directory.mkdir()
            env = {**env0, "TMPDIR": str(directory)}
            sources = make_cell_sources(
                benchmark, variant, directory, observe, whetstone_mode)
            saved_sources = [*sources, *directory.glob("*.h")]
            command = [
                str(Z88DK / "bin/zcc"), "+cpm", "-compiler=llvmz80",
                f"-Cg-{opt}", *flags, "-Cg-mllvm",
                "-Cg-z80-static-frames=false", "-m", "-no-cleanup",
                "-create-app",
                "-o", str(directory / "rt"),
            ]
            if benchmark == "whetstone":
                command.append("--math32")
            command.extend(str(path) for path in sources)
            DEFAULT_CC.checked(command, directory, env)
            assemblies = list(directory.glob("*.asm"))
            for assembly in assemblies:
                if "L___static_frames" in assembly.read_text():
                    raise RuntimeError(
                        f"Static-frame allocation remained enabled in {assembly}")
            if benchmark != "whetstone" or whetstone_mode != "original-compute":
                verify_workload_assembly(benchmark, assemblies)
            com = directory / "RT.COM"
            if not com.is_file():
                raise RuntimeError(f"{benchmark} did not produce RT.COM")
            return directory, env, sources, saved_sources, com

        observe_dir, _, observe_sources, observe_saved, observe_com = (
            compile_variant(work / "observe", True))
        observed = DEFAULT_CC.checked(
            [str(WORKSPACE / "ntvcm/ntvcm"), str(observe_com)], observe_dir)
        correctness = check_output(benchmark, observed.stdout, oracle)
        observe_artifact = artifact / "observer"
        observe_artifact.mkdir()
        for path in (*observe_saved, *observe_dir.glob("*.map"),
                     *observe_dir.glob("*.asm")):
            shutil.copy2(path, observe_artifact / path.name)
        shutil.copy2(observe_com, observe_artifact / observe_com.name)
        (observe_artifact / "ntvcm-output.txt").write_text(observed.stdout)

        timed_dir, env, timed_sources, timed_saved, com = compile_variant(
            work / "timed", False)
        native = DEFAULT_CC.checked(
            [str(WORKSPACE / "ntvcm/ntvcm"), str(com)], timed_dir)
        check_pass_marker(native.stdout, benchmark)
        ticks = DEFAULT_CC.checked([
            "python3", str(WORKSPACE / "scratch/dcc-clang-bench/ticks_cpm.py"),
            "--counter", str(cycle_limit), str(com),
        ], timed_dir, env)
        check_pass_marker(ticks.stdout, benchmark)
        match = re.search(r"^\[ticks\] (\d+) cycles$", ticks.stderr, re.MULTILINE)
        if not match:
            raise RuntimeError(f"Missing ticks cycle count: {ticks.stderr}")
        cycles = int(match[1])
        if cycles >= cycle_limit:
            raise RuntimeError(
                f"{benchmark} {opt} {variant} reached the {cycle_limit}-cycle cap")
        maps = list(timed_dir.glob("*.map"))
        if len(maps) != 1:
            raise RuntimeError(f"Expected one linker map, found {maps}")
        sizes, sections = DEFAULT_CC.section_sizes(maps[0].read_text())
        timed_artifact = artifact / "timed"
        timed_artifact.mkdir()
        shutil.copy2(com, timed_artifact / com.name)
        for path in (*timed_saved, *maps, *timed_dir.glob("*.asm")):
            shutil.copy2(path, timed_artifact / path.name)
        (timed_artifact / "ntvcm-output.txt").write_text(native.stdout)
        (timed_artifact / "ticks-output.txt").write_text(ticks.stdout)
        source_hashes = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in timed_saved
        }
        row = {
            "benchmark": benchmark,
            "opt": opt,
            "variant": variant,
            "default_calling_convention": {
                "baseline": "no option (sdcccall1 default)",
                "A": "sdcccall1",
                "B": "sdcccall0",
                "C": "sdcccall0 plus fixed annotations",
            }[variant],
            "com_bytes": com.stat().st_size,
            "cycles": cycles,
            "section_bytes": sizes,
            "sections": sections,
            "code_rodata_data": sum(sizes[key] for key in ("code", "rodata", "data")),
            "sha256": hashlib.sha256(com.read_bytes()).hexdigest(),
            "source_sha256": source_hashes,
            "correctness": correctness,
            "timed_program_completion": "PASS on ntvcm and ticks",
        }
        return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cycle-limit", type=int, default=TICKS_LIMIT)
    parser.add_argument(
        "--whetstone-mode", choices=("workload-preserving", "original-compute"),
        default="workload-preserving",
        help="original-compute measures the unguarded source and optimizer freedom")
    args = parser.parse_args()
    if args.cycle_limit <= 0:
        parser.error("--cycle-limit must be positive")
    oracles = {"whetstone": whetstone_reference(),
               "dhrystone": {
                   "runs": DHR_RUNS,
                   "numeric_fields": dict(zip(DHR_NUMERIC_FIELDS, DHR_EXPECTED)),
                   "string_fields": dict(zip(DHR_STRING_FIELDS, DHR_STRINGS)),
                   "basis": "published Dhrystone 2.1 final-variable checks",
               }}
    output = args.output if args.output.is_absolute() else WORKSPACE / args.output
    artifacts = output.with_suffix("")
    if output.exists() or artifacts.exists():
        raise SystemExit(f"Refusing to overwrite existing results: {output} / {artifacts}")
    output.parent.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True)
    TMP.mkdir(parents=True, exist_ok=True)
    compiler_hash = hashlib.sha256(CLANG.read_bytes()).hexdigest()
    compiler_version = DEFAULT_CC.checked([str(CLANG), "--version"], HERE).stdout
    z88dk_revision = DEFAULT_CC.checked(
        ["git", "-C", str(Z88DK), "rev-parse", "HEAD"], HERE).stdout.strip()
    env0 = {
        **os.environ,
        "ZCCCFG": str(Z88DK / "lib/config"),
        "LLVMZ80EXE": str(CLANG),
        "PATH": str(Z88DK / "bin") + ":" + os.environ["PATH"],
    }
    with tempfile.TemporaryDirectory(prefix="cycle-control.", dir=TMP) as raw:
        DEFAULT_CC.cycle_control(Path(raw))
    rows = []
    benchmarks = (("whetstone",) if args.whetstone_mode == "original-compute"
                  else ("whetstone", "dhrystone"))
    for benchmark in benchmarks:
        oracle = oracles[benchmark]
        for opt in ("Os", "O2"):
            pair = []
            for variant in ("baseline", "A"):
                row = build_and_run(
                    benchmark, opt, variant, oracle, env0, artifacts,
                    args.cycle_limit, args.whetstone_mode)
                rows.append(row)
                pair.append(row)
                print(json.dumps({key: value for key, value in row.items()
                                  if key not in ("sections", "correctness")},
                                 ), flush=True)
            if pair[0]["sha256"] != pair[1]["sha256"]:
                raise RuntimeError(
                    f"No-flag and explicit sdcccall1 binaries differ: {benchmark} {opt}")
            if pair[0]["cycles"] != pair[1]["cycles"]:
                raise RuntimeError(
                    f"No-flag and explicit sdcccall1 cycles differ: {benchmark} {opt}")
            for variant in ("B", "C"):
                row = build_and_run(
                    benchmark, opt, variant, oracle, env0, artifacts,
                    args.cycle_limit, args.whetstone_mode)
                rows.append(row)
                print(json.dumps({key: value for key, value in row.items()
                                  if key not in ("sections", "correctness")},
                                 ), flush=True)

    if hashlib.sha256(CLANG.read_bytes()).hexdigest() != compiler_hash:
        raise RuntimeError("Compiler binary changed during measurement")
    result = {
        "compiler": compiler_version,
        "compiler_sha256": compiler_hash,
        "z88dk_revision": z88dk_revision,
        "workloads": {
            "whetstone": {
                "source": "support/benchmarks/whetstone/whetstone.c",
                "mode": args.whetstone_mode,
                "loop": 10,
                "iterations": 1,
                "runtime": "--math32 for every cell",
                "transforms": (
                    [
                        "timed: fixed main(void), retaining LOOP=10 and II=1",
                        "timed: add PASS after TIMER_STOP; no workload observers",
                        "observer: volatile snapshots after modules for the oracle",
                    ]
                    if args.whetstone_mode == "original-compute" else [
                        "fixed main(void), retaining the default LOOP=10 and II=1",
                        "snapshot module results after their loops for lossless checks",
                        "compile the module-6 loop separately to prevent O2 folding",
                        "keep P3 out-of-line so the 8,990 module-8 calls survive O2",
                        "emit observer snapshots and PASS after TIMER_STOP",
                    ]),
                "optimizer_freedom": args.whetstone_mode == "original-compute",
            },
            "dhrystone": {
                "sources": [
                    "support/benchmarks/dhrystone21/dhry.h",
                    "support/benchmarks/dhrystone21/dhry_1.c",
                    "support/benchmarks/dhrystone21/dhry_2.c",
                ],
                "runs": DHR_RUNS,
                "transforms": [
                    "modernize void main(void) to int main(void)",
                    "check published 2.1 final variables and strings after TIMER_STOP",
                    "emit actual final values and PASS after the benchmark loop",
                    "do not enable PRINTF; that optional route links unresolved dtoa symbols",
                ],
            },
        },
        "annotation_policy": POLICY,
        "annotation_scope": (
            "Only benchmark-defined eligible direct-call functions are annotated. "
            "One-argument routines use z88dk_fastcall; multi-argument routines use "
            "z88dk_callee. Main, zero-argument functions, and library prototypes "
            "are untouched. Dhrystone declarations in dhry.h and definitions in "
            "both translation units receive matching attributes."
        ),
        "optimization": ["-Cg-Os", "-Cg-O2"],
        "lto": False,
        "static_frame": "disabled with -mllvm -z80-static-frames=false",
        "whetstone_float_tolerance": "0.0001 absolute + 0.0001 relative",
        "cycle_limit": args.cycle_limit,
        "cycle_control": 63,
        "independent_oracles": oracles,
        "rows": rows,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"RESULTS_SAVED {output}")


if __name__ == "__main__":
    main()
