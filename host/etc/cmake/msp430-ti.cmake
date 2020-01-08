#-----------------------------------------------------------------------------
# Macros for MSP430 with TI compiler
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# CMake version required for these macros
#-----------------------------------------------------------------------------
CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

# Common tools
INCLUDE(tde-common)

#-----------------------------------------------------------------------------
# Define the SoC target
#-----------------------------------------------------------------------------
MACRO (use_target target)
  SET (ARCH "-vmsp --abi=eabi --advice:power=all --define=__${target}__")
  SET (XCC_MIN_OPTIMIZATION_LEVEL "0")
  SET (XCC_MAX_OPTIMIZATION_LEVEL "2")
  STRING (TOLOWER ${TARGET} LCTARGET)
ENDMACRO ()

#-----------------------------------------------------------------------------
# Usual cross-compiler warning settings
#-----------------------------------------------------------------------------
MACRO (use_default_xcc_warnings)
  IF (CMAKE_C_COMPILER_ID STREQUAL "TI")
  ENDIF ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Usual cross-compiler configuration for C language
#-----------------------------------------------------------------------------
MACRO (use_default_xcc_settings)
  IF (NOT ARCH)
    MESSAGE (FATAL_ERROR
             "Target architecture not defined, use use_target() macro\n")
  ENDIF (NOT ARCH)
  SET (XCC_DEBUG_OPT ${XCC_MIN_OPTIMIZATION_LEVEL})
  SET (XCC_RELEASE_OPT ${XCC_MAX_OPTIMIZATION_LEVEL})
  IF (NOT CMAKE_C_COMPILER_ID STREQUAL "TI")
    SET (XCC_FEAT_DEFS "-std=gnu99 -fshow-column -fgnu89-inline -fno-strict-aliasing")
    SET (XCC_EXTRAS "-fdiagnostics-color=always")
  ELSE ()
    SET (XCC_FEAT_DEFS "--c99 --preproc_with_compile")
    SET (XCC_EXTRAS "--diag_warning=225 --diag_wrap=off --display_error_number")
  ENDIF ()
  SET (XCC_FEAT_DEFS "${XCC_FEAT_DEFS} ${XCC_BLD_DEFS} ${XCC_EXTRAS}")
  IF (NOT XTCHECK GREATER 0)
  IF (NOT CMAKE_C_COMPILER_ID STREQUAL "TI")
    IF (XCC_VERBOSE)
      SET (XCC_FEAT_DEFS "${XCC_FEAT_DEFS} -v")
    ENDIF (XCC_VERBOSE)
    SET (XCC_WARN_RELEASE "-Werror -Wfatal-errors")
  ELSE ()
    SET (XCC_WARN_RELEASE "--emit_warnings_as_errors")
  ENDIF ()
  ENDIF (NOT XTCHECK GREATER 0)
  SET (XCC_FEAT_RELEASE "")
  SET (XCC_OPTS_RELEASE "${XCC_WARN_RELEASE} ${XCC_FEAT_RELEASE}")
  SET (CMAKE_C_FLAGS "${ARCH} ${XCC_FEAT_DEFS} ${XCC_WARN_DEFS} ${EXTRA_DEFS}")
  SET (CMAKE_C_FLAGS_DEBUG "-O${XCC_DEBUG_OPT} -DDEBUG")
  SET (CMAKE_C_FLAGS_RELEASE "-O${XCC_RELEASE_OPT} -DNDEBUG ${XCC_OPTS_RELEASE}")
  SET (EXTRA_DEFS_DISALLOWED 1)
ENDMACRO ()

#-----------------------------------------------------------------------------
# Usual cross-compiler configuration for C++ language
#-----------------------------------------------------------------------------
MACRO (use_default_xxx_settings)
  IF (NOT ARCH)
    MESSAGE (FATAL_ERROR
             "Target architecture not defined, use use_target() macro\n")
  ENDIF (NOT ARCH)
  IF (XTCHECK GREATER 0)
    SET (CXX_WARNINGS ${CXX_WARNINGS}
                      conversion-null
                      invalid-offsetof
                      pmf-conversions
                      sign-promo
                      strict-null-sentinel)
  ENDIF (XTCHECK GREATER 0)
  FOREACH (warning ${CXX_WARNINGS})
    SET (XCC_CXX_XTCHECK "${XCC_CXX_XTCHECK} -W${warning}")
  ENDFOREACH (warning ${CXX_WARNINGS})
  SET (GXX_WARN_DEFS "${XCC_XTCHECK} ${XCC_CXX_XTCHECK}")
  SET (GXX_FEAT_DEFS "-fshow-column -fno-strict-aliasing")
  SET (GXX_FEAT_RELEASE "-fomit-frame-pointer")
  SET (GXX_OPTS_RELEASE "${XCC_WARN_RELEASE} ${GXX_FEAT_RELEASE}")
  SET (CMAKE_CXX_FLAGS "${ARCH} ${GXX_FEAT_DEFS} ${GXX_WARN_DEFS} ${EXTRA_DEFS}")
  SET (CMAKE_CXX_FLAGS_DEBUG "-O${XCC_DEBUG_OPT} -DDEBUG")
  SET (CMAKE_CXX_FLAGS_RELEASE "-O${XCC_RELEASE_OPT} -DNDEBUG ${GXX_OPTS_RELEASE}")
  SET (EXTRA_DEFS_DISALLOWED 1)
ENDMACRO ()

#-----------------------------------------------------------------------------
# Usual cross-assembler configuration for ASM language
#-----------------------------------------------------------------------------
MACRO (use_default_xas_settings)
  IF (NOT ARCH)
    MESSAGE (FATAL_ERROR
             "Target architecture not defined, use use_target() macro\n")
  ENDIF (NOT ARCH)
  SET (CMAKE_ASM_FLAGS "${ARCH} -fshow-column -fmessage-length=0 -c -Wall")
  SET (CMAKE_ASM_FLAGS_DEBUG "-DDEBUG")
  SET (CMAKE_ASM_FLAGS_RELEASE "-DNDEBUG")
ENDMACRO ()

# Include generic definition for any toolchain
INCLUDE(tde-tools)

