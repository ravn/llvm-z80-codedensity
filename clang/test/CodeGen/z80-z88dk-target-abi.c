// RUN: %clang_cc1 -triple z80-unknown-none-z88dk -emit-llvm -o - %s | FileCheck %s --check-prefix=STACK
// RUN: %clang_cc1 -triple z80-unknown-none-z88dk -fdefault-calling-conv=sdcccall0 -emit-llvm -o - %s | FileCheck %s --check-prefix=STACK
// RUN: %clang_cc1 -triple z80-unknown-none-z88dk -fdefault-calling-conv=sdcccall1 -emit-llvm -o - %s | FileCheck %s --check-prefix=REGISTER
// RUN: %clang_cc1 -triple z80 -emit-llvm -o - %s | FileCheck %s --check-prefix=BARE

typedef int (*callback)(int);

int ordinary(int value) { return value; }

int indirect(callback f, int value) { return f(value); }

int variadic(int value, ...) { return value; }

int explicit_register(int value) __attribute__((sdcccall(1)));
int explicit_stack(int value) __attribute__((sdcccall(0)));

int explicit_calls(int value) {
  return explicit_register(value) + explicit_stack(value);
}

int main(void) { return ordinary(7); }

// STACK: define{{.*}}z80_sdcccall0 i16 @ordinary(
// STACK-LABEL: define{{.*}} @indirect(
// STACK: call z80_sdcccall0 i16 %
// STACK: define{{.*}}z80_sdcccall0 i16 @variadic(
// STACK-LABEL: define{{.*}} @explicit_calls(
// STACK: call i16 @explicit_register(
// STACK: call z80_sdcccall0 i16 @explicit_stack(
// main retains clang's existing entry-point convention.
// STACK: define dso_local i16 @main(
// STACK: call z80_sdcccall0 i16 @ordinary(

// REGISTER: define dso_local i16 @ordinary(
// REGISTER-LABEL: define{{.*}} @indirect(
// REGISTER: call i16 %
// REGISTER: define dso_local i16 @variadic(
// REGISTER-LABEL: define{{.*}} @explicit_calls(
// REGISTER: call i16 @explicit_register(
// REGISTER: call z80_sdcccall0 i16 @explicit_stack(
// REGISTER: define dso_local i16 @main(
// REGISTER: call i16 @ordinary(

// BARE: define dso_local i16 @ordinary(
// BARE-LABEL: define{{.*}} @indirect(
// BARE: call i16 %
// BARE: define dso_local i16 @variadic(
// BARE: define dso_local i16 @main(
