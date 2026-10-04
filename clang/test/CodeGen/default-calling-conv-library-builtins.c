// RUN: %clang_cc1 -triple i686-windows-msvc -target-cpu pentium4 -fdefault-calling-conv=fastcall -emit-llvm -o - %s | FileCheck %s -DCC=x86_fastcallcc
// RUN: %clang_cc1 -triple i686-windows-msvc -target-cpu pentium4 -fdefault-calling-conv=stdcall -emit-llvm -o - %s | FileCheck %s -DCC=x86_stdcallcc
// RUN: %clang_cc1 -triple i686-windows-msvc -target-cpu pentium4 -fdefault-calling-conv=vectorcall -emit-llvm -o - %s | FileCheck %s -DCC=x86_vectorcallcc
// RUN: %clang_cc1 -triple i686-windows-msvc -target-cpu pentium4 -emit-llvm -o - %s | FileCheck %s -DCC=

extern int puts(const char *) __attribute__((cdecl));

unsigned int library_alias(const char *s) {
  return __builtin_strlen(s);
}

int variadic_alias(const char *s) {
  return __builtin_printf("%s", s);
}

int explicit_attribute(const char *s) {
  return puts(s);
}

void non_library_builtin(void) {
  __builtin_trap();
}

// CHECK-LABEL: define{{.*}}library_alias
// CHECK: call [[CC]]{{ ?}}i32 {{.*}}strlen
// Variadic library calls retain the convention's variadic fallback.
// CHECK-LABEL: define{{.*}}variadic_alias
// CHECK: call i32 (ptr, ...) @printf(
// Explicit declarations still override the command-line default.
// CHECK-LABEL: define{{.*}}explicit_attribute
// CHECK: call i32 @puts(
// Non-library builtins retain their intrinsic calling convention.
// CHECK-LABEL: define{{.*}}non_library_builtin
// CHECK: call void @llvm.trap()
