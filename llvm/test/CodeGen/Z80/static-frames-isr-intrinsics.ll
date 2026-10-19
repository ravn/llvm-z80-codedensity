; RUN: llc -mtriple=z80 -O1 -z80-static-frames -verify-machineinstrs < %s | FileCheck %s

; Intrinsics in an interrupt handler (such as 'llvm.z80.in', 'llvm.z80.out',
; 'llvm.z80.ei', 'llvm.z80.di') must have the nocallback attribute (provided by
; DefaultAttrsIntrinsic) so that LLVM CallGraph does not add an edge to CallsExternalNode.
; Otherwise, Z80NonReentrant falsely marks foreground functions as reachable from the ISR.

@sink = global ptr null

; Shape (c) positive control: genuinely shared function called by both ISR
; and foreground code must keep its stack frame.
; CHECK-LABEL: shared:
; CHECK-NOT: L_shared.frame
define internal i16 @shared(i16 %x) {
  %buf = alloca i16, align 1
  store volatile i16 %x, ptr %buf, align 1
  %v = load volatile i16, ptr %buf, align 1
  ret i16 %v
}

; Shape (b) structural variation: helper called only by ISR, containing intrinsic in.
; CHECK-LABEL: isr_helper:
; CHECK: L_isr_helper.frame
define internal void @isr_helper() {
  %buf = alloca i16, align 1
  store volatile i16 42, ptr %buf, align 1
  %val = call i8 @llvm.z80.in(i8 4)
  ret void
}

; Shape (a) exact pattern: ISR containing intrinsic out and ei.
; CHECK-LABEL: isr:
; CHECK: L_isr.frame
define void @isr() #0 {
  %buf = alloca i16, align 1
  store volatile i16 7, ptr %buf, align 1
  call void @isr_helper()
  %r = call i16 @shared(i16 3)
  call void @llvm.z80.out(i8 4, i8 1)
  call void @llvm.z80.ei()
  ret void
}

; Shape (b) structural variation: foreground helper containing intrinsic nop.
; CHECK-LABEL: foreground_intrinsic_helper:
; CHECK: L_foreground_intrinsic_helper.frame
define internal i16 @foreground_intrinsic_helper(i16 %x) {
  %buf = alloca i16, align 1
  store volatile i16 %x, ptr %buf, align 1
  call void @llvm.z80.nop()
  %v = load volatile i16, ptr %buf, align 1
  ret i16 %v
}

; Shape (a) foreground main function: must receive a static frame despite the ISR using intrinsics.
; CHECK-LABEL: main:
; CHECK: L_main.frame
define i16 @main() {
  %buf = alloca [4 x i16], align 1
  store volatile i16 1, ptr %buf, align 1
  %a = call i16 @foreground_intrinsic_helper(i16 2)
  %b = call i16 @shared(i16 5)
  %r = add i16 %a, %b
  ret i16 %r
}

; Shape (d) safety check: frames are consolidated into L___static_frames.
; CHECK: L___static_frames
; CHECK-DAG: L_main.frame = L___static_frames
; CHECK-DAG: L_isr.frame = L___static_frames
; CHECK-DAG: L_isr_helper.frame = L___static_frames
; CHECK-DAG: L_foreground_intrinsic_helper.frame = L___static_frames

declare i8 @llvm.z80.in(i8)
declare void @llvm.z80.out(i8, i8)
declare void @llvm.z80.ei()
declare void @llvm.z80.nop()

attributes #0 = { "interrupt" }
