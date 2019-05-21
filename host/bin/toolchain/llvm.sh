#!/bin/sh

die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

export CLANG7PATH=/usr/local/clang7

rm -rf ${HOME}/Sources/toolchain/build/llvm
mkdir -p ${HOME}/Sources/toolchain/build/llvm
cd ${HOME}/Sources/toolchain/build/llvm
cmake -G Ninja ${HOME}/Sources/toolchain/src/llvm -DCMAKE_BUILD_TYPE=Release \
   -DCMAKE_INSTALL_PREFIX=${CLANG7PATH} -DLLVM_ENABLE_SPHINX=False \
   -DLLVM_INCLUDE_TESTS=False -DLLVM_TARGETS_TO_BUILD="ARM" || \
   die "Cannot configure LLVM"
ninja || die "Cannot build LLVM"
sudo cmake --build . --target install || die "Cannot install LLVM"
export PATH=${PATH}:${CLANG7PATH}/bin
file /usr/local/clang7/bin/* | grep ELF | cut -d: -f1 | xargs strip
rm /usr/local/clang7/lib/*.a
