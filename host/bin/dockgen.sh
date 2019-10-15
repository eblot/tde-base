#!/bin/sh

if [ $(docker images -q clang:v9 | wc -l) -eq 0 ]; then
    echo "Downloading LLVM suite"
    docker build -f host/docker/src/clang-v9.docker -t clang:v9 . || exit $?
fi
if [ $(docker images -q newlib:v3.1.0 | wc -l) -eq 0 ]; then
    echo "Downloading Newlib"
    docker build -f host/docker/src/newlib-v3.docker -t newlib:v3.1.0 . || exit $?
fi
if [ $(docker images -q llvm-aarch32:v9-10 | wc -l) -eq 0 ]; then
    echo "Building LLVM suite"
    docker build -f host/docker/src/llvm-aarch32-v9.docker -t llvm-aarch32:v9-10 . || exit $?
fi
if [ $(docker images -q clang-aarch32:v9-10 | wc -l) -eq 0 ]; then
    echo "Installating LLVM suite"
    docker build -f host/docker/src/clang-aarch32-v9.docker -t clang-aarch32:v9-10 . || exit $?
fi
if [ $(docker images -q clang-cortex-m4f:v9-10 | wc -l) -eq 0 ]; then
    echo "Building C/C++ libraries for Cortex-M4 Hard FPU"
    docker build -f host/docker/src/clang-cortex-m4f-v9.docker -t clang-cortex-m4f:v9-10 . || exit $?
fi
if [ $(docker images -q clang-cortex-m4:v9-10 | wc -l) -eq 0 ]; then
    echo "Building C/C++ libraries for Cortex-M4 Soft FPU"
    docker build -f host/docker/src/clang-cortex-m4-v9.docker -t clang-cortex-m4:v9-10 . || exit $?
fi
if [ $(docker images -q clang-cortex-m0plus:v9-10 | wc -l) -eq 0 ]; then
    echo "Building C/C++ libraries for Cortex-M0 Soft FPU"
    docker build -f host/docker/src/clang-cortex-m0plus-v9.docker -t clang-cortex-m0plus:v9-10 . || exit $?
fi
if [ $(docker images -q binutils-aarch32:v2.33-10 | wc -l) -eq 0 ]; then
    echo "Building Binutils"
    docker build -f host/docker/src/binutils-aarch32-v2.33.docker -t binutils-aarch32:v2.33-10 . || exit $?
fi
if [ $(docker images -q openocd-nrf52:v0.10.1-10 | wc -l) -eq 0 ]; then
    echo "Building OpenOCD"
    docker build -f host/docker/src/openocd-nrf52.docker -t openocd-nrf52:v0.10.1-10 . || exit $?
fi

if [ $(docker images -q lightdevenv:v9-10 | wc -l) -eq 0 ]; then
    echo "Creating Docker light developement environment"
    docker build -f host/docker/exec/lightdevenv.docker -t lightdevenv:tmp . || exit $?
    docker run --name lightdevenv_tmp -it lightdevenv:tmp /bin/sh -c "exit" || exit $?
    docker export lightdevenv_tmp | docker import - lightdevenv:v9-10 || exit $?
    docker rm lightdevenv_tmp || exit $?
    docker rmi lightdevenv:tmp || exit $?
fi

if [ $(docker images -q devenv:v9-10 | wc -l) -eq 0 ]; then
    echo "Creating Docker fulll developement environment"
    docker build -f host/docker/exec/devenv.docker -t devenv:tmp . || exit $?
    docker run -it --name devenv_tmp devenv:tmp /bin/sh -c "exit" || exit $?
    docker export devenv_tmp | docker import - devenv:v9-10 || exit $?
    docker rm devenv_tmp || exit $?
    docker rmi devenv:tmp || exit $?
fi

echo "Removing any temporary image(s)"
docker images --filter "dangling=true" -q | xargs docker rmi 2>  /dev/null

echo "Available Docker images"
docker images

if [ -n "${DOCKERHUB_USER}" -a "${DOCKERHUB_USER}" != "local" ]; then
    echo "Tagging Docker images"
    docker tag clang-aarch32:v9-10 ${DOCKERHUB_USER}/clang-aarch32:v9-10
    docker tag openocd-nrf52:v0.10.1-10 ${DOCKERHUB_USER}/openocd-nrf52:v0.10.1-10
    docker tag clang-cortex-m4f:v9-10 ${DOCKERHUB_USER}/clang-cortex-m4f:v9-10
    docker tag clang-cortex-m4:v9-10 ${DOCKERHUB_USER}/clang-cortex-m4:v9-10
    docker tag clang-cortex-m0plus:v9-10 ${DOCKERHUB_USER}/clang-cortex-m0plus:v9-10
    docker tag binutils-aarch32:v2.33-10 ${DOCKERHUB_USER}/binutils-aarch32:v2.33-10
    docker tag openocd-nrf52:v0.10.1-10 ${DOCKERHUB_USER}/openocd-nrf52:v0.10.1-10
    docker tag lightdevenv:v9-10 ${DOCKERHUB_USER}/lightdevenv:v9-10
    docker tag devenv:v9-10 ${DOCKERHUB_USER}/devenv:v9-10
fi
