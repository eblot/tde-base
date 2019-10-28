#!/bin/sh

LLVMVER=v10-dev
ALPINEVER=10

if [ $(docker images -q clang:${LLVMVER} | wc -l) -eq 0 ]; then
    echo "Downloading LLVM suite"
    docker build -f host/docker/src/clang-${LLVMVER}.docker -t clang:${LLVMVER} . || exit $?
fi
if [ $(docker images -q newlib:v3.1.0 | wc -l) -eq 0 ]; then
    echo "Downloading Newlib"
    docker build -f host/docker/src/newlib-v3.docker -t newlib:v3.1.0 . || exit $?
fi
if [ $(docker images -q llvm-aarch32:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Building LLVM suite"
    docker build -f host/docker/src/llvm-aarch32-${LLVMVER}.docker -t llvm-aarch32:${LLVMVER}-${ALPINEVER} . || exit $?
fi
if [ $(docker images -q clang-aarch32:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Installating LLVM suite"
    docker build -f host/docker/src/clang-aarch32-${LLVMVER}.docker -t clang-aarch32:${LLVMVER}-${ALPINEVER} . || exit $?
fi
if [ $(docker images -q clang-cortex-m4f:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Building C/C++ libraries for Cortex-M4 Hard FPU"
    docker build -f host/docker/src/clang-cortex-m4f-${LLVMVER}.docker -t clang-cortex-m4f:${LLVMVER}-${ALPINEVER} . || exit $?
fi
if [ $(docker images -q clang-cortex-m4:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Building C/C++ libraries for Cortex-M4 Soft FPU"
    docker build -f host/docker/src/clang-cortex-m4-${LLVMVER}.docker -t clang-cortex-m4:${LLVMVER}-${ALPINEVER} . || exit $?
fi
if [ $(docker images -q clang-cortex-m0plus:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Building C/C++ libraries for Cortex-M0 Soft FPU"
    docker build -f host/docker/src/clang-cortex-m0plus-${LLVMVER}.docker -t clang-cortex-m0plus:${LLVMVER}-${ALPINEVER} . || exit $?
fi
if [ $(docker images -q binutils-aarch32:v2.33-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Building Binutils"
    docker build -f host/docker/src/binutils-aarch32-v2.33.docker -t binutils-aarch32:v2.33-${ALPINEVER} . || exit $?
fi
if [ $(docker images -q openocd-nrf52:v0.10.1-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Building OpenOCD"
    docker build -f host/docker/src/openocd-nrf52.docker -t openocd-nrf52:v0.10.1-${ALPINEVER} . || exit $?
fi

if [ $(docker images -q lightdevenv:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Creating Docker light developement environment"
    docker build -f host/docker/exec/lightdevenv.docker -t lightdevenv:tmp . || exit $?
    docker run --name lightdevenv_tmp -it lightdevenv:tmp /bin/sh -c "exit" || exit $?
    docker export lightdevenv_tmp | docker import - lightdevenv:${LLVMVER}-${ALPINEVER} || exit $?
    docker rm lightdevenv_tmp || exit $?
    docker rmi lightdevenv:tmp || exit $?
fi

if [ $(docker images -q devenv:${LLVMVER}-${ALPINEVER} | wc -l) -eq 0 ]; then
    echo "Creating Docker fulll developement environment"
    docker build -f host/docker/exec/devenv.docker -t devenv:tmp . || exit $?
    docker run -it --name devenv_tmp devenv:tmp /bin/sh -c "exit" || exit $?
    docker export devenv_tmp | docker import - devenv:${LLVMVER}-${ALPINEVER} || exit $?
    docker rm devenv_tmp || exit $?
    docker rmi devenv:tmp || exit $?
fi

echo "Removing any temporary image(s)"
docker images --filter "dangling=true" -q | xargs docker rmi 2>  /dev/null

if [ -n "${DOCKERHUB_USER}" -a "${DOCKERHUB_USER}" != "local" ]; then
    echo "Tagging Docker images"
    docker tag clang-aarch32:${LLVMVER}-${ALPINEVER} ${DOCKERHUB_USER}/clang-aarch32:${LLVMVER}-${ALPINEVER}
    docker tag openocd-nrf52:v0.10.1-${ALPINEVER} ${DOCKERHUB_USER}/openocd-nrf52:v0.10.1-${ALPINEVER}
    docker tag clang-cortex-m4f:${LLVMVER}-${ALPINEVER} ${DOCKERHUB_USER}/clang-cortex-m4f:${LLVMVER}-${ALPINEVER}
    docker tag clang-cortex-m4:${LLVMVER}-${ALPINEVER} ${DOCKERHUB_USER}/clang-cortex-m4:${LLVMVER}-${ALPINEVER}
    docker tag clang-cortex-m0plus:${LLVMVER}-${ALPINEVER} ${DOCKERHUB_USER}/clang-cortex-m0plus:${LLVMVER}-${ALPINEVER}
    docker tag binutils-aarch32:v2.33-${ALPINEVER} ${DOCKERHUB_USER}/binutils-aarch32:v2.33-${ALPINEVER}
    docker tag openocd-nrf52:v0.10.1-${ALPINEVER} ${DOCKERHUB_USER}/openocd-nrf52:v0.10.1-${ALPINEVER}
    docker tag lightdevenv:${LLVMVER}-${ALPINEVER} ${DOCKERHUB_USER}/lightdevenv:v${LLVMVER}-${ALPINEVER}
    docker tag devenv:${LLVMVER}-${ALPINEVER} ${DOCKERHUB_USER}/devenv:v${LLVMVER}-${ALPINEVER}

    echo "Available Docker images"
    docker images --filter=reference="${DOCKERHUB_USER}/*"
else
    echo "Available Docker images"
    docker images
fi

