# Tiny development environment

This project includes a limited build environment to build projects for
embedded baremetal cross-platform targets, on macOS and Linux hosts.

## Overview

It focuses on using:

 * [CMake](https://cmake.org) to generate the build scripts/files,
   *i.e.* autoconf-free
 * [Ninja](https://ninja-build.org) as the small build system,
   *i.e.* Make-free
 * [LLVM](https://llvm.org) as the compiler infrastructure,
   *i.e.* no GCC, and restricted use of binutils:
     - [clang](http://clang.llvm.org) as the C and C++ front-end compiler
     - LLVM integrated assembler
     - [lld](http://lld.llvm.org) as the linker
     - [compiler-rt](https://compiler-rt.llvm.org) as the runtime library
     - [LLVM](https://llvm.org) as the target backend and binutils replacement
     - [libc++](http://libcxx.llvm.org) and
       [libc++abi](http://libcxxabi.llvm.org) as the C++ Standard Library
 * [Newlib](http://www.sourceware.org/newlib/) as the C library for embedded
   baremetal targets
 * [Python3](https://www.python.org/) as the main language for tools,
 * [Dash](https://git.kernel.org/pub/scm/utils/dash/dash.git) as the POSIX
    shell interpreter.
 * [Docker](https://www.docker.com/products/container-runtime) community
   edition to run pre-build toolchain binaries

## Goal

The environment is dedicated to demonstrate the use of clang/LLVM to build
projects for baremetal targets such as ARM Cortex-M series.

Replacing the pervasive GNU GCC/Binutils toolchain with clang/LLVM is not
always straightforward for non-mainstream targets - which are x86_64/ARM for
Linux/macOS/iOS/Windows.

This repository shows that clang/LLVM can be used as a drop-in replacement of
GNU tools even for small embedded baremetal targets.

It builds on top of the [armeabi](https://github.com/eblot/homebrew-armeabi)
Homebrew repository, which has been used for over 3 years to build real
products.

It also shows that GNU Make is not the only option to efficiently build
embedded applications for small targets from the command line.

## Supported targets

 * ARMv7em Cortex-M4 (with or without FPU)
 * ARMv6m Cortex-M0+

 Adding other 32-bit Cortex-M cores would be quite straightforward.

## File organization

 * `host/` directory contains tools and configuration that run on the host
 * `library/` contains libraries and Python modules required by host tools
 * other top-level directories contain target specific projects, named after
   the actual target device.

Projects directories are managed as Git submodules.

The projects are organized as one top-level directory for each target type.
Applications are located within the `app/` directory, which may also be
managed as Git submodules.

## Main tools

All tools should be started from the top-level directory

 * `host/bin/build.sh` is the main script from which all projects are built,
    whatever the actual target. Neither CMake or Ninja are directly invoked
    from the command line, `build.sh` acts as a wrapper to perform builds.
 * `host/bin/dockbuild.sh` is a wrapper script that invoke `build.sh` from a
    Dockerized environment. When a toolchain is not available on the host, this
    script should be used rather than `host/bin/build.sh`. It takes care of
    downloading/installating the proper toolchain images required to build
    the project for the selected targets.
 * `host/bin/pyterm.py` is a small Python terminal client to retrieve, format
    and optionally logs debug traces from a remote target, using a serial line
    interface. It is recommended but not mandatory to install `pyftdi` Python
    module to use with a USB-Serial FTDI adapter.

## Installation

## Prerequisites

There are two ways to use Tiny Development Environment:

  1. Install all the required tools on the host, and use `host/bin/build.sh` to
     build projects. See the following sections for details
  2. Install [Docker](https://www.docker.com/products/container-runtime)
     engine, and use `host/bin/dockbuild.sh` to build projects. This method is
     simpler and work on Linux and macOS.

### Docker installation

#### Install and download

[Docker Engine Community Edition](https://hub.docker.com/search/?type=edition&offering=community)
that matches your host environment.

### macOS native toolchain installation

#### Install brew package manager

From [Homebrew](https://brew.sh)

````sh
/usr/bin/ruby -e \
  "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
````

#### Load custom taps

````sh
brew tap eblot/armeabi
brew tap eblot/devtools
````

#### Install native packages

````sh
brew install cmake coreutils curl dash dos2unix doxygen gawk gettext git
brew install m4 makedepend mspdebug ninja openssl pkg-config python
brew install sqlite subversion wget xz
brew install arm-none-eabi-llvm arm-none-eabi-gdb arm-none-eabi-binutils
brew install armv6m-cortex-m0plus armv7em-cortex-m4 armv7em-cortex-m4f
brew install --HEAD openocd-nrf52
````

#### Install Python packages

````sh
# be sure no brew tool get the priority to build native Python extensions
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin
pip3 install six crcmod bpython sphinx pyusb pyserial gnureadline \
   netifaces ruamel.yaml protobuf sphinx_rtd_theme tabulate \
   sphinx_autodoc_typehints paramiko breathe
exit
````

### Linux native toolchain installation

To be documented.

Is is recommended to use the Docker-based build, or follow Dockerfile recipes
from `host/docker/src` to install from source.

## Projects

### Checking out all projects

From top-level directory, run

````sh
git submodules init
git submodules update
````

### Available demo projects

 [stm32l432](https://github.com/eblot/tde-stm32l432.git)
 : ChibiOS-based projects for STM32L432 (Cortex-M4)

  * This project contains a demo application: USB-CDC-ACM (USB-Serial) bridge

 [nrf52](https://github.com/eblot/tde-nrf52.git)
 : nRF52 OS-less SDK (Cortex-M4)

  * This project contains no application, only the nRF5 SDK w/ S132 and S140
    SoftDevices.

  * [bleadv](https://github.com/eblot/tde-nrf52-bleadv.git) is an application
    submodules for nRF52, it implements a BLE advertiser application demo.