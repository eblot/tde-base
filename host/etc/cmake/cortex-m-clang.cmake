#-----------------------------------------------------------------------------
# Definition file for Clang for all Cortex-M targets
#-----------------------------------------------------------------------------

CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

LIST (APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR})
SET (CMAKE_SYSTEM_NAME tde)

FIND_PROGRAM (xclang clang)
FIND_PROGRAM (ctidy NAMES clang-tidy)
SET (xcc ${xclang})

SET (EABI "none-eabi")
STRING (REGEX REPLACE "v[67][em]*" "" CPUKIND ${XTOOLCHAIN})
SET (XTOOLPREFIX ${XTOOLCHAIN}-${EABI})
SET (XTOOLGENERIC ${CPUKIND}-${EABI})

GET_FILENAME_COMPONENT (TOPDIR ${CMAKE_SOURCE_DIR} DIRECTORY)
SET (WRAPPERDIR "${TOPDIR}/host/bin/wrappers")

FIND_PROGRAM (xar llvm-ar)
FIND_PROGRAM (xranlib llvm-ranlib)
FIND_PROGRAM (xobjdump llvm-objdump)
FIND_PROGRAM (gnuxobjdump ${XTOOLGENERIC}-objdump)
FIND_PROGRAM (xsize llvm-size)
FIND_PROGRAM (xnm llvm-nm)
FIND_PROGRAM (xobjcopy "${XTOOLGENERIC}-objcopy")
FIND_PROGRAM (xstrip "${XTOOLGENERIC}-strip")
IF ( DEFINED XLD )
  FIND_PROGRAM (xld ${XTOOLGENERIC}-${XLD})
  SET (LDSTARTGROUP "-Wl,--start-group")
  SET (LDENDGROUP "-Wl,--end-group")
ELSE ()
  SET (LDSTARTGROUP)
  SET (LDENDGROUP)
ENDIF ()

FOREACH (xtool xar;xranlib;xobjdump;xsize;xnm;xobjcopy;xstrip)
  IF (NOT ${xtool})
    MESSAGE (FATAL_ERROR
      "Unable to locate a complete ${XTOOLCHAIN} C/C++ toolchain: ${xtool}")
  ENDIF ()
ENDFOREACH()

GET_FILENAME_COMPONENT (XTOOLCHAIN_BIN ${xclang} DIRECTORY)
GET_FILENAME_COMPONENT (XTOOLCHAIN_ROOT ${XTOOLCHAIN_BIN} DIRECTORY)

EXECUTE_PROCESS (COMMAND ${xclang} -print-resource-dir
                 OUTPUT_VARIABLE XTOOLCHAIN_RESOURCE)
STRING (STRIP ${XTOOLCHAIN_RESOURCE} XTOOLCHAIN_RESOURCE)

IF (XSYSROOT)
  SET (XCC_SYSROOT "${XSYSROOT}/${XTOOLPREFIX}/${TARGET}")
  SET (XXX_SYSROOT "${XSYSROOT}/${XTOOLPREFIX}/${TARGET}")
ELSE ()
  MESSAGE (FATAL_ERROR "Sysroot is not defined")
ENDIF ()

SET (CMAKE_C_STANDARD_INCLUDE_DIRECTORIES
     ${XCC_SYSROOT}/include ${XTOOLCHAIN_RESOURCE}/include)
SET (CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES
     ${XXX_SYSROOT}/include/c++/v1 ${XCC_SYSROOT}/include
     ${XTOOLCHAIN_RESOURCE}/include)

SET (CMAKE_ASM_COMPILER_ID Clang)
SET (CMAKE_C_COMPILER_ID Clang)
SET (CMAKE_CXX_COMPILER_ID Clang)
SET (CMAKE_C_COMPILER_FORCED TRUE)
SET (CMAKE_CXX_COMPILER_FORCED TRUE)
SET (CMAKE_C_COMPILER ${xcc})
SET (CMAKE_CXX_COMPILER ${xcc})
SET (CMAKE_ASM_COMPILER ${xcc})
SET (CMAKE_DEPFILE_FLAGS_C "-MD -MT <OBJECT> -MF <DEPFILE>")
SET (CMAKE_DEPFILE_FLAGS_CXX "-MD -MT <OBJECT> -MF <DEPFILE>")
IF ( DEFINED XLD )
  SET (CMAKE_C_LINK_EXECUTABLE
       "${xld} <CMAKE_C_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET> <LINK_LIBRARIES>")
  SET (CMAKE_CXX_LINK_EXECUTABLE
       "${xld} <CMAKE_C_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET> <LINK_LIBRARIES>")
ENDIF ()

SET (CMAKE_C_LINK_FLAGS "-nostdlib")
SET (CMAKE_C_LINK_FLAGS_RELEASE "-flto")
SET (CMAKE_CXX_LINK_FLAGS "-nostdlib")
SET (CMAKE_CXX_LINK_FLAGS_RELEASE "-flto")

SET (CMAKE_C_CREATE_STATIC_LIBRARY
     "<CMAKE_AR> rc <TARGET> <LINK_FLAGS> <OBJECTS>"
     "<CMAKE_RANLIB> <TARGET>")
SET (CMAKE_CXX_CREATE_STATIC_LIBRARY
     ${CMAKE_C_CREATE_STATIC_LIBRARY})

SET (CMAKE_NOT_USING_CONFIG_FLAGS 1) # allow custom DEBUG/RELEASE flags

IF ( gnuxobjdump AND NOT CMAKE_BUILD_TYPE STREQUAL "RELEASE" )
  # GNU version is far better than LLVM version when it comes to disassembly
  # however LTO mode used in RELEASE build makes GNU version crazy
  SET (xdisassemble
       ${gnuxobjdump} -dS)
ELSE ()
  SET (xdisassemble
       ${xobjdump} -disassemble -triple=thumb -g -line-numbers -source)
ENDIF ()

# Common tools
INCLUDE (tde-common)

#-----------------------------------------------------------------------------
# Use C standard library
#-----------------------------------------------------------------------------
MACRO (use_newlib)
  # libnosys should appear before libc as libc invoke symbols which are
  # defined as weak symbols in libnosys, but we want the linker to search
  # for SDK symbol first, which is achieved with a --start-group --end-group
  # sequence. In other words, a symbol defined in libnosys and used in libc
  # is first found in the next linker collect cycle from the SDK, then finally
  # found in libnosys if not found in the SDK. YMMV...
  SET (LINK_C_RUNTIME "${XCC_SYSROOT}/lib/crt0.o")
  LIST (INSERT PROJECT_LINK_LIBRARIES 0 c nosys)
ENDMACRO ()

#-----------------------------------------------------------------------------
# Usual cross-compiler warning settings
#-----------------------------------------------------------------------------
MACRO (use_default_xcc_warnings)
  SET (XCC_XTCHECK "${XCC_XTCHECK} -DW_DEPRECATED")
  SET (ALLOWED_STATIC_SIZE 16384)  # 16KiB
  SET (ALLOWED_FRAME_SIZE 256)
  SET (WARNINGS ${WARNINGS}
                  CL4
                  conversion
                  shadow-all
                  tautological-compare
                  unreachable-code-aggressive
                  deprecated
                  documentation
                  documentation-pedantic
                  implicit-fallthrough
                  loop-analysis
                  array-bounds-pointer-arithmetic
                  assign-enum
                  bad-function-cast
                  cast-align
                  # cast-qual
                  char-align
                  comma
                  complex-component-init
                  conditional-uninitialized
                  consumed
                  conversion-null
                  # covered-switch-default
                  cuda-compat
                  date-time
                  declaration-after-statement
                  deprecated-implementations
                  disabled-macro-expansion
                  documentation-pedantic
                  dollar-in-identifier-extension
                  double-promotion
                  duplicate-decl-specifier
                  duplicate-enum
                  embedded-directive
                  # empty-translation-unit
                  expansion-to-defined
                  flexible-array-extensions
                  float-equal
                  four-char-constants
                  header-hygiene
                  idiomatic-parentheses
                  implicit-atomic-properties
                  long-long
                  main
                  method-signatures
                  missing-noreturn
                  missing-prototypes
                  # missing-variable-declarations
                  nested-anon-types
                  newline-eof
                  nonportable-system-include-path
                  nullability-extension
                  nullable-to-nonnull-conversion
                  old-style-cast
                  over-aligned
                  overlength-strings
                  packed
                  # padded
                  pointer-arith
                  retained-language-linkage
                  shift-sign-overflow
                  signed-enum-bitfield
                  spir-compat
                  static-in-inline
                  strict-prototypes
                  switch-enum
                  unguarded-availability
                  unnamed-type-template-args
                  unneeded-member-function
                  unused-exception-parameter
                  # unused-macros
                  used-but-marked-unused
                  variadic-macros
                  vec-elem-size
                  vector-conversion
                  vla
                  vla-extension
                  zero-length-array)
  FOREACH (warning ${WARNINGS})
    SET (XCC_XTCHECK "${XCC_XTCHECK} -W${warning}")
  ENDFOREACH (warning ${WARNINGS})
  FOREACH (warning ${C_WARNINGS})
    SET (XCC_C_XTCHECK "${XCC_C_XTCHECK} -W${warning}")
  ENDFOREACH (warning ${C_WARNINGS})
  SET (XCC_WARN_DEFS "-Werror=implicit-function-declaration ${XCC_XTCHECK}")
  SET (XCC_WARN_DEFS "${XCC_WARN_DEFS} ${XCC_C_XTCHECK}")
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
  SET (XCC_FEAT_DEFS
        "-std=gnu99 -fshow-column -fgnu89-inline -fno-strict-aliasing")
  SET (XCC_FEAT_DEFS
        "${XCC_FEAT_DEFS} -ffunction-sections -fdata-sections")
  SET (XCC_FEAT_DEFS
        "${XCC_FEAT_DEFS} -fno-builtin") # --short-enums
  SET (XCC_FEAT_DEFS
        "${XCC_FEAT_DEFS} -fdiagnostics-color=always -fansi-escape-codes")
  SET (XCC_FEAT_DEFS
        "${XCC_FEAT_DEFS} -fdiagnostics-fixit-info")
  IF (XCC_VERBOSE)
    SET (XCC_FEAT_DEFS "${XCC_FEAT_DEFS} -v")
  ENDIF (XCC_VERBOSE)
  IF (NOT XTCHECK GREATER 0)
  SET (XCC_WARN_RELEASE "-Werror -Wfatal-errors")
  ENDIF (NOT XTCHECK GREATER 0)
  SET (XCC_FEAT_RELEASE "-fomit-frame-pointer")
  SET (XCC_OPTS_RELEASE "${XCC_WARN_RELEASE} ${XCC_FEAT_RELEASE}")
  SET (CMAKE_C_FLAGS
       "${ARCH} -g ${XCC_FEAT_DEFS} ${XCC_WARN_DEFS} ${EXTRA_DEFS}")
  SET (CMAKE_C_FLAGS_DEBUG "-O${XCC_DEBUG_OPT} -DDEBUG")
  SET (CMAKE_C_FLAGS_RELEASE
       "-O${XCC_RELEASE_OPT} -DNDEBUG -flto ${XCC_OPTS_RELEASE}")
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
  SET (CXX_WARN_DEFS "${XCC_XTCHECK} ${XCC_CXX_XTCHECK}")

  SET (CXX_FD_1 "-fshow-column -fno-strict-aliasing")
  SET (CXX_FD_2 "-fdiagnostics-color=always -fansi-escape-codes")
  SET (CXX_FD_3 "-fdiagnostics-fixit-info -fno-stack-protector")
  SET (CXX_FD_4 "-ffunction-sections -fdata-sections -fno-use-cxa-atexit")
  SET (CXX_FD_5 "-D_GNU_SOURCE=1 -D_POSIX_TIMERS=1")
  SET (CXX_FEAT_DEFS "${CXX_FD_1} ${CXX_FD_2} ${CXX_FD_3} ${CXX_FD_4} ${CXX_FD_5}")
  IF (XCC_VERBOSE)
    SET (CXX_FEAT_DEFS "${CXX_FEAT_DEFS} -v")
  ENDIF (XCC_VERBOSE)
  SET (CXX_FEAT_RELEASE "-fomit-frame-pointer")
  SET (CXX_OPTS_RELEASE "${XCC_WARN_RELEASE} ${CXX_FEAT_RELEASE}")
  SET (CMAKE_CXX_FLAGS "${ARCH} -g ${CXX_FEAT_DEFS} ${CXX_WARN_DEFS} ${EXTRA_DEFS}")
  SET (CMAKE_CXX_FLAGS_DEBUG "-O${XCC_DEBUG_OPT} -DDEBUG")
  SET (CMAKE_CXX_FLAGS_RELEASE
       "-O${XCC_RELEASE_OPT} -DNDEBUG -flto ${CXX_OPTS_RELEASE}")
  SET (EXTRA_DEFS_DISALLOWED 1)
  LIST (INSERT PROJECT_LINK_LIBRARIES 0 c++abi c++)

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

#-----------------------------------------------------------------------------
# Link the final application
#  :app: the application name
#  :dependencies: one or more static libraries to link with
#-----------------------------------------------------------------------------
MACRO (link_app app)
  SET (arguments ${ARGN})
  extract_parameter (link_script arguments "LINK_SCRIPT" ${arguments})
  extract_parameter (link_dir arguments "LINK_SCRIPT_DIR" ${arguments})
  SET (symbols)
  WHILE ("LINK_SYMBOL" IN_LIST arguments)
    extract_parameter (symboldef arguments "LINK_SYMBOL" ${arguments})
    LIST (APPEND symbols "-Wl,--defsym=${symboldef}")
  ENDWHILE ()
  IF (EXTRALIBS)
    SET (extraname ${app}_extras)
    SET (extrafile ${CMAKE_CURRENT_BINARY_DIR}/lib${extraname}.o)
    SET (extrapaths)
    # EXTRALIBS may have been created/updated from build_component_from
    FOREACH (xlib ${EXTRALIBS})
      LIST (APPEND extrapaths ${CMAKE_BINARY_DIR}/${xlib}/lib${xlib}_extra.a)
    ENDFOREACH ()
    ADD_CUSTOM_COMMAND (OUTPUT ${extrafile}
                        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
                        COMMAND ${xld}
                               -nostdlib -r -T /dev/null
                               --whole-archive -o ${extrafile}
                               ${extrapaths}
                        COMMENT "Building ${app} extra object")
    ADD_CUSTOM_TARGET (${extraname}-object
                       DEPENDS ${extrafile})
    ADD_DEPENDENCIES (${extraname}-object ${arguments})
    ADD_DEPENDENCIES (${app} ${extraname}-object)
  ELSE ()
    SET (extrafile)
  ENDIF ()
  IF (link_script)
    ADD_CUSTOM_TARGET (${app}-ld DEPENDS ${link_script})
    ADD_DEPENDENCIES (${app} ${app}-ld)
    GET_FILENAME_COMPONENT(link_script_dir ${link_script} DIRECTORY)
    IF (link_script_dir)
      IF (NOT link_dir STREQUAL link_script_dir)
        # avoid duplicates
        SET (link_script_opt "-Wl,-L${link_script_dir}")
      ENDIF ()
    ELSE ()
      SET (link_script_opt)
    ENDIF ()
  ENDIF ()
  IF (link_dir)
      SET (link_script_opt "-Wl,-L${link_dir} ${link_script_opt}")
  ENDIF ()
  # CMake complains about trailing spaces
  STRING (STRIP ${link_script_opt} link_script_opt)
  TARGET_LINK_LIBRARIES (${app} ${extrafile}
                         ${link_script_opt}
                         ${symbols}
                         -Wl,--warn-common
                         -Wl,--gc-sections
                         -Wl,--no-whole-archive
                         -Wl,-static
                         -Wl,-znorelro
                         -T ${link_script}
                         ${LDSTARTGROUP}
                         ${arguments}
                         ${LINK_SYSTEM_LIBS}
                         ${LINK_C_RUNTIME}
                         ${PROJECT_LINK_LIBRARIES}
                         ${LDENDGROUP})
  create_map_file (${app})
ENDMACRO ()
