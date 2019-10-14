#-----------------------------------------------------------------------------
# Definition file for Clang Cortex-M4 toolchain
#-----------------------------------------------------------------------------

CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

# Use common Cortex-M definitions
INCLUDE (cortex-m-clang)

#-----------------------------------------------------------------------------
# Define the SoC flags
#-----------------------------------------------------------------------------
MACRO (use_target)
  # for some awkward CMake reason, AR and RANLIB cannot be defined before
  # PROJECT() is set, as they are clear-out on this call
  SET (CMAKE_AR ${xar})
  SET (CMAKE_RANLIB ${xranlib})
  LINK_DIRECTORIES (${XCC_SYSROOT}/lib ${XXX_SYSROOT}/lib)
  LIST (APPEND PROJECT_LINK_LIBRARIES clang_rt.builtins-armv7em)
  SET (cpu ${TARGET})
  SET (XCC_FPOPT "-mfloat-abi=soft")
  SET (XISA "thumb")
  SET (XCC_ISA "-m${XISA} -mabi=aapcs -fshort-enums")
  SET (ARCH "-target ${XTOOLPREFIX} -mcpu=${cpu} ${XCC_FPOPT} -fshort-enums")
  SET (XCC_MIN_OPTIMIZATION_LEVEL "0")
  SET (XCC_MAX_OPTIMIZATION_LEVEL "z")
  STRING (TOLOWER ${TARGET} LCTARGET)
ENDMACRO ()
