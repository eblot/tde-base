#-----------------------------------------------------------------------------
# Definition file for Clang Cortex-M4F toolchain
#-----------------------------------------------------------------------------

CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

# FPU and soft FP use the same toolchain, the TARGET variable is used to
# select the specific FP options
INCLUDE (cortex-m4-clang)
