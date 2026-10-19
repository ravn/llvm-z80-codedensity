; RUN: llc -verify-machineinstrs -mtriple=z80 -z80-asm-format=sdasz80 -O0 < %s | FileCheck %s

declare void @llvm.z80.halt()
declare void @llvm.z80.di()
declare void @llvm.z80.ei()
declare void @llvm.z80.nop()
declare void @llvm.z80.im2()
declare void @llvm.z80.set.i(i8)

; Test: HALT intrinsic
define void @test_halt() {
; CHECK-LABEL: _test_halt:
; CHECK:       halt
; CHECK:       ret
  call void @llvm.z80.halt()
  ret void
}

; Test: DI and EI intrinsics for interrupt control
define void @test_di_ei() {
; CHECK-LABEL: _test_di_ei:
; CHECK:       di{{$}}
; CHECK-NEXT:  ei
; CHECK-NEXT:  ret
  call void @llvm.z80.di()
  call void @llvm.z80.ei()
  ret void
}

; Test: NOP intrinsic
define void @test_nop() {
; CHECK-LABEL: _test_nop:
; CHECK:       nop
; CHECK:       ret
  call void @llvm.z80.nop()
  ret void
}

; Test: IM 2 intrinsic (select interrupt mode 2)
define void @test_im2() {
; CHECK-LABEL: _test_im2:
; CHECK:       im 2
; CHECK:       ret
  call void @llvm.z80.im2()
  ret void
}

; Test: LD I,A intrinsic (set interrupt vector register from a value)
define void @test_set_i(i8 %v) {
; CHECK-LABEL: _test_set_i:
; CHECK:       ld i,a
; CHECK:       ret
  call void @llvm.z80.set.i(i8 %v)
  ret void
}

declare i8 @llvm.z80.in(i8)
declare void @llvm.z80.out(i8, i8)

; Test: IN A,(n) with constant port
define i8 @test_in_const() {
; CHECK-LABEL: _test_in_const:
; CHECK:       in a,(4)
; CHECK:       ret
  %val = call i8 @llvm.z80.in(i8 4)
  ret i8 %val
}

; Test: OUT (n),A with constant port
define void @test_out_const(i8 %val) {
; CHECK-LABEL: _test_out_const:
; CHECK:       out (5),a
; CHECK:       ret
  call void @llvm.z80.out(i8 5, i8 %val)
  ret void
}

; Test: IN r,(C) with variable port
define i8 @test_in_var(i8 %p) {
; CHECK-LABEL: _test_in_var:
; CHECK:       in {{[a-z]+}},(c)
; CHECK:       ret
  %val = call i8 @llvm.z80.in(i8 %p)
  ret i8 %val
}

; Test: OUT (C),r with variable port
define void @test_out_var(i8 %p, i8 %val) {
; CHECK-LABEL: _test_out_var:
; CHECK:       out (c),
; CHECK:       ret
  call void @llvm.z80.out(i8 %p, i8 %val)
  ret void
}

