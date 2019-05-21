#!/bin/sh

# Die with an error message
die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

mkdir -p ${HOME}/Sources/toolchain/src
cd ${HOME}/Sources/toolchain/src
if [ ! -d llvm ]; then
    echo "Download LLVM"
    (curl -LO https://releases.llvm.org/7.0.0/llvm-7.0.0.src.tar.xz && \
        [ "8bc1f844e6cbde1b652c19c1edebc1864456fd9c78b8c1bea038e51b363fe222" = \
          "$(sha256sum llvm-7.0.0.src.tar.xz | cut -d' ' -f1)" ] && \
        tar xf llvm-7.0.0.src.tar.xz && \
        mv llvm-7.0.0.src llvm) || die "Cannot download LLVM"
fi
if [ ! -d clang ]; then
    echo "Download Clang"
    (curl -LO https://releases.llvm.org/7.0.0/cfe-7.0.0.src.tar.xz && \
        [ "550212711c752697d2f82c648714a7221b1207fd9441543ff4aa9e3be45bba55" = \
          "$(sha256sum cfe-7.0.0.src.tar.xz | cut -d' ' -f1)" ] && \
        tar xf cfe-7.0.0.src.tar.xz && \
        mv cfe-7.0.0.src clang) || die "Cannot download Clang"
fi
if [ ! -d clang-tools-extra ]; then
    echo "Download Clang tools extra"
    (curl -LO https://releases.llvm.org/7.0.0/clang-tools-extra-7.0.0.src.tar.xz && \
        [ "937c5a8c8c43bc185e4805144744799e524059cac877a44d9063926cd7a19dbe" = \
          "$(sha256sum clang-tools-extra-7.0.0.src.tar.xz | cut -d' ' -f1)" ] && \
        tar xf clang-tools-extra-7.0.0.src.tar.xz && \
        mv clang-tools-extra-7.0.0.src clang-tools-extra) || \
        die "Cannot download Clang tools extra"
fi
if [ ! -d lld ]; then
    echo "Download LLD"
    (curl -LO https://releases.llvm.org/7.0.0/lld-7.0.0.src.tar.xz && \
        [ "fbcf47c5e543f4cdac6bb9bbbc6327ff24217cd7eafc5571549ad6d237287f9c" = \
          "$(sha256sum lld-7.0.0.src.tar.xz | cut -d' ' -f1)" ] && \
        tar xf lld-7.0.0.src.tar.xz && \
        mv lld-7.0.0.src lld) || die "Cannot download LLD"
fi
if [ ! -d compiler-rt ]; then
    echo "Download Compiler RT"
    (curl -LO https://releases.llvm.org/7.0.0/compiler-rt-7.0.0.src.tar.xz && \
        [ "bdec7fe3cf2c85f55656c07dfb0bd93ae46f2b3dd8f33ff3ad6e7586f4c670d6" = \
          "$(sha256sum compiler-rt-7.0.0.src.tar.xz | cut -d' ' -f1)" ] && \
        tar xf compiler-rt-7.0.0.src.tar.xz && \
        mv compiler-rt-7.0.0.src compiler-rt) || die "Cannot download Compiler RT"
fi
if [ ! -d newlib ]; then
    echo "Download Newlib"
    (curl -LO ftp://sourceware.org/pub/newlib/newlib-3.0.0.tar.gz && \
         [ "c8566335ee74e5fcaeb8595b4ebd0400c4b043d6acb3263ecb1314f8f5501332" = \
           "$(sha256sum newlib-3.0.0.tar.gz | cut -d' ' -f1)" ] && \
         tar xf newlib-3.0.0.tar.gz && \
         mv newlib-3.0.0 newlib) || die "Cannot download newlib"
fi
if [ ! -f newlib-arm-eabi-3.0.0.patch ]; then
    echo "Download Newlib patch"
    (curl -LO https://gist.githubusercontent.com/eblot/135ad4fe89008d54fdea89cdadc420de/raw/6af6e6e4f94e3d08743a2155f1004b4bada4aea9/newlib-arm-eabi-3.0.0.patch && \
         [ "b3ca94fe603ad13daddd58cd2496b92e48b71c4a031643a67e20146bfb82341c" = \
           "$(sha256sum newlib-arm-eabi-3.0.0.patch | cut -d' ' -f1)" ] && \
           (cd newlib && patch -p1 < ../newlib-arm-eabi-3.0.0.patch)) || \
           die "Cannot patch newlib"
fi
if [ ! -d binutils ]; then
    echo "Download Binutils"
    (curl -LO http://ftp.gnu.org/gnu/binutils/binutils-2.31.1.tar.xz && \
        [ "5d20086ecf5752cc7d9134246e9588fa201740d540f7eb84d795b1f7a93bca86" = \
          "$(sha256sum binutils-2.31.1.tar.xz | cut -d' ' -f1)" ] && \
          tar xf binutils-2.31.1.tar.xz && \
          mv binutils-2.31.1 binutils) || die "Cannot download Binutils"
fi
(cd llvm/tools && ln -s ../../clang && ln -s ../../lld) && \
    (cd llvm/tools/clang/tools && ln -s ../../clang-tools-extra extra) || \
    die "Cannot prepare LLVM"

