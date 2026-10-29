; Mul-family compiler-rt libcalls in the z88dk environment.
; Companion to ravn/llvm-z80#420: pins that legalizeMul32 picks the
; __mulhisi3 / __umulhisi3 helpers for sign/zero-extended i16*i16, the
; Z80_UMULH_I16 helper (__umulhi3) for the high half of a u16*u16, and
; __muldi3 for 64-bit multiply, under isZ80Z88dkEnv.
;
; XFAIL: *
;
; Currently fails with "unable to legalize G_MUL (s32)" because z88dk-env's
; __sdcccall(0) default puts both i16 args on the stack, the prelegalizer
; folds G_LOAD + G_SEXT into G_SEXTLOAD, and GISelValueTracking has no case
; for G_SEXTLOAD/G_ZEXTLOAD -- so legalizeMul32 (from PR #114) sees 0
; leading-zeros / 0 sign-bits on the s32 operand and falls through to
; Helper.libcall(MUL_I32) -> __mulsi3, which is in Z80Z88dkOptOut.
;
; End-to-end runtime verification through the zcc +cpm -compiler=llvmz80
; pathway (z88dk's test/llvmz80/runtime_mul_libcalls.c) PASSES across
; -O0/-O2/-Os -- that pathway's calling convention does not expose the
; G_SEXTLOAD gap.  So this XFAIL tracks the orthogonal GISel bug, not a
; defect in the issue #420 cleanroom patch itself.
;
; RUN: llc -mtriple=z80-unknown-none-z88dk -O2 -verify-machineinstrs < %s | FileCheck %s

; CHECK-LABEL: _smul32:
; CHECK:       call ___mulhisi3
define i32 @smul32(i16 %a, i16 %b) {
  %x = sext i16 %a to i32
  %y = sext i16 %b to i32
  %m = mul nsw i32 %x, %y
  ret i32 %m
}

; CHECK-LABEL: _umul32:
; CHECK:       call ___umulhisi3
define i32 @umul32(i16 %a, i16 %b) {
  %x = zext i16 %a to i32
  %y = zext i16 %b to i32
  %m = mul nuw i32 %x, %y
  ret i32 %m
}

; CHECK-LABEL: _umulh16:
; CHECK:       call ___umulhi3
define i16 @umulh16(i16 %a, i16 %b) {
  %x = zext i16 %a to i32
  %y = zext i16 %b to i32
  %m = mul nuw i32 %x, %y
  %s = lshr i32 %m, 16
  %t = trunc i32 %s to i16
  ret i16 %t
}

; CHECK-LABEL: _mul64:
; CHECK:       call ___muldi3
define i64 @mul64(i64 %a, i64 %b) {
  %m = mul i64 %a, %b
  ret i64 %m
}
