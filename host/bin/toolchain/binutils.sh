#!/bin/sh

die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

rm -rf ${HOME}/Sources/toolchain/build/binutils
mkdir -p ${HOME}/Sources/toolchain/build/binutils
cd ${HOME}/Sources/toolchain/build/binutils
# light build: Assembler and Linker are not built, as provided wtith LLVM/Clang
${HOME}/Sources/toolchain/src/binutils/configure \
    --prefix=/usr/local/arm-none-eabi \
    --target=arm-none-eabi \
    --without-gnu-ld \
    --without-gnu-as \
    --disable-shared \
    --disable-nls \
    --with-gmp \
    --with-mpfr \
    --disable-cloog-version-check \
    --enable-multilibs \
    --enable-interwork \
    --enable-lto \
    --disable-werror \
    --disable-debug || die "Cannot configure binutils"
make || die "Cannot build binutils"
sudo make install
