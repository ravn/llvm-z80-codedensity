; RUN: opt -mtriple=z80 -passes=inliner-wrapper -S < %s | FileCheck %s

target datalayout = "e-m:o-p:16:8-i8:8-i16:8-i32:8-i64:8-f32:8-f64:8-n8-a:8"
target triple = "z80"

@g = external global i8

; Shape (a): Single-use internal function with > 10 instructions.
; Must be inlined into its only caller.
define internal void @single_use_helper() minsize optsize {
  store volatile i8 1, ptr @g, align 1
  store volatile i8 2, ptr @g, align 1
  store volatile i8 3, ptr @g, align 1
  store volatile i8 4, ptr @g, align 1
  store volatile i8 5, ptr @g, align 1
  store volatile i8 6, ptr @g, align 1
  store volatile i8 7, ptr @g, align 1
  store volatile i8 8, ptr @g, align 1
  store volatile i8 9, ptr @g, align 1
  store volatile i8 10, ptr @g, align 1
  store volatile i8 11, ptr @g, align 1
  store volatile i8 12, ptr @g, align 1
  ret void
}

; CHECK-LABEL: define void @caller_single_use()
; CHECK-NOT: call void @single_use_helper()
; CHECK: store volatile i8 1, ptr @g
; CHECK: store volatile i8 12, ptr @g
; CHECK: ret void
define void @caller_single_use() minsize optsize {
  call void @single_use_helper()
  ret void
}

; Shape (b): Structural variation - chained single-use internal helpers (helper2 calls helper1).
define internal void @chained_helper1() minsize optsize {
  store volatile i8 20, ptr @g, align 1
  store volatile i8 21, ptr @g, align 1
  store volatile i8 22, ptr @g, align 1
  store volatile i8 23, ptr @g, align 1
  store volatile i8 24, ptr @g, align 1
  store volatile i8 25, ptr @g, align 1
  store volatile i8 26, ptr @g, align 1
  store volatile i8 27, ptr @g, align 1
  store volatile i8 28, ptr @g, align 1
  store volatile i8 29, ptr @g, align 1
  store volatile i8 30, ptr @g, align 1
  ret void
}

define internal void @chained_helper2() minsize optsize {
  call void @chained_helper1()
  store volatile i8 31, ptr @g, align 1
  store volatile i8 32, ptr @g, align 1
  store volatile i8 33, ptr @g, align 1
  store volatile i8 34, ptr @g, align 1
  store volatile i8 35, ptr @g, align 1
  store volatile i8 36, ptr @g, align 1
  store volatile i8 37, ptr @g, align 1
  store volatile i8 38, ptr @g, align 1
  store volatile i8 39, ptr @g, align 1
  store volatile i8 40, ptr @g, align 1
  store volatile i8 41, ptr @g, align 1
  ret void
}

; CHECK-LABEL: define void @caller_chained()
; CHECK-NOT: call void @chained_helper
; CHECK: store volatile i8 20, ptr @g
; CHECK: store volatile i8 41, ptr @g
; CHECK: ret void
define void @caller_chained() minsize optsize {
  call void @chained_helper2()
  ret void
}

; Shape (c): Positive control - small function (<= 10 instructions) is inlined.
define internal void @small_helper() minsize optsize {
  store volatile i8 50, ptr @g, align 1
  ret void
}

; CHECK-LABEL: define void @caller_small()
; CHECK-NOT: call void @small_helper()
; CHECK: store volatile i8 50, ptr @g
; CHECK: ret void
define void @caller_small() minsize optsize {
  call void @small_helper()
  ret void
}

; Shape (d): Negative control - multi-use function with > 10 instructions must NOT be inlined.
define internal void @multi_use_helper() minsize optsize {
  store volatile i8 60, ptr @g, align 1
  store volatile i8 61, ptr @g, align 1
  store volatile i8 62, ptr @g, align 1
  store volatile i8 63, ptr @g, align 1
  store volatile i8 64, ptr @g, align 1
  store volatile i8 65, ptr @g, align 1
  store volatile i8 66, ptr @g, align 1
  store volatile i8 67, ptr @g, align 1
  store volatile i8 68, ptr @g, align 1
  store volatile i8 69, ptr @g, align 1
  store volatile i8 70, ptr @g, align 1
  store volatile i8 71, ptr @g, align 1
  ret void
}

; CHECK-LABEL: define void @caller_multi_use1()
; CHECK: call void @multi_use_helper()
; CHECK: ret void
define void @caller_multi_use1() minsize optsize {
  call void @multi_use_helper()
  ret void
}

; CHECK-LABEL: define void @caller_multi_use2()
; CHECK: call void @multi_use_helper()
; CHECK: ret void
define void @caller_multi_use2() minsize optsize {
  call void @multi_use_helper()
  ret void
}
