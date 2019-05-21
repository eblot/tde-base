#!/bin/sh

die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

cd ${HOME}/Sources/toolchain

export CLANG7PATH=/usr/local/clang7
export XTARGET=armv6m-none-eabi
export XCPU=cortex-m0+
export XCPUDIR=cortex-m0plus
export PATH=$PATH:${CLANG7PATH}/bin

cd ${HOME}/Sources/toolchain/src/compiler-rt
curl https://gist.githubusercontent.com/eblot/5aa9d7e283e84d72442449669ad71580/raw/bec95b92e470377ac374c63a9609b83785768da8/compiler_rt-cortex-m.diff | patch -p1

cd ${HOME}/Sources/toolchain/src/newlib
curl https://github.com/eblot/newlib-cygwin/commit/ef7efeb7ec8ca067d07d00c2c8aabb3fdb124440.diff | patch -p1

rm -rf ${HOME}/Sources/toolchain/build/newlib
mkdir -p ${HOME}/Sources/toolchain/build/newlib
cd ${HOME}/Sources/toolchain/build/newlib
export CC_FOR_TARGET=${CLANG7PATH}/bin/clang
export AR_FOR_TARGET=${CLANG7PATH}/bin/llvm-ar
export NM_FOR_TARGET=${CLANG7PATH}/bin/llvm-nm
export RANLIB_FOR_TARGET=${CLANG7PATH}/bin/llvm-ranlib
export READELF_FOR_TARGET=${CLANG7PATH}/bin/llvm-readelf
export CFLAGS_FOR_TARGET="-target ${XTARGET} -mcpu=${XCPU} -mthumb -mabi=aapcs -g -O3 -ffunction-sections -fdata-sections -Wno-unused-command-line-argument"
export AS_FOR_TARGET="${CLANG7PATH}/bin/clang"
${HOME}/Sources/toolchain/src/newlib/configure\
    --host=`cc -dumpmachine`\
    --build=`cc -dumpmachine`\
    --target=${XTARGET}\
    --prefix=${CLANG7PATH}/${XTARGET}/${XCPUDIR}\
    --disable-newlib-supplied-syscalls\
    --enable-newlib-reent-small\
    --disable-newlib-fvwrite-in-streamio\
    --disable-newlib-fseek-optimization\
    --disable-newlib-wide-orient\
    --enable-newlib-nano-malloc\
    --disable-newlib-unbuf-stream-opt\
    --enable-lite-exit\
    --enable-newlib-global-atexit\
    --disable-newlib-nano-formatted-io \
    --disable-newlib-fvwrite-in-streamio \
    --enable-newlib-io-c99-formats \
    --disable-newlib-io-float \
    --disable-nls
make
sudo make install
sudo mv ${CLANG7PATH}/${XTARGET}/${XCPUDIR}/${XTARGET}/* \
        ${CLANG7PATH}/${XTARGET}/${XCPUDIR}/
sudo rmdir ${CLANG7PATH}/${XTARGET}/${XCPUDIR}/${XTARGET}

rm -rf ${HOME}/Sources/toolchain/build/compiler_rt
mkdir -p ${HOME}/Sources/toolchain/build/compiler_rt
cd ${HOME}/Sources/toolchain/build/compiler_rt
cmake -G Ninja \
    -DXTARGET=${XTARGET} -DXCPU=${XCPU} -DXCPUDIR=${XCPUDIR} \
    ${HOME}/Sources/toolchain/src/compiler-rt/cortex-m
ninja
sudo cp libcompiler_rt.a ${CLANG7PATH}/${XTARGET}/${XCPUDIR}/lib/

cd ${HOME}/Sources/toolchain/src/compiler-rt
curl https://gist.githubusercontent.com/eblot/5aa9d7e283e84d72442449669ad71580/raw/bec95b92e470377ac374c63a9609b83785768da8/compiler_rt-cortex-m.diff | patch -p1 -R

cd ${HOME}/Sources/toolchain/src/newlib
curl https://github.com/eblot/newlib-cygwin/commit/ef7efeb7ec8ca067d07d00c2c8aabb3fdb124440.diff | patch -p1 -R
