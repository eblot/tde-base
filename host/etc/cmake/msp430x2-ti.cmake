#-----------------------------------------------------------------------------
# Definition file for TI MSP430x2xx toolchain
#-----------------------------------------------------------------------------

CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

LIST (APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR})

SET (CMAKE_SYSTEM_NAME tde)
SET (CMAKE_SYSTEM_VERSION ${XCC_VER})

FIND_PROGRAM (xcc "cl430")
FIND_PROGRAM (xld "lnk430")
FIND_PROGRAM (xar "ar430")
FIND_PROGRAM (xobjcopy "${XTOOLCHAIN}-objcopy")
FIND_PROGRAM (xobjdump "${XTOOLCHAIN}-objdump")
FIND_PROGRAM (xsize "${XTOOLCHAIN}-size")
FIND_PROGRAM (xstrip "${XTOOLCHAIN}-strip")
FIND_PROGRAM (xnm "${XTOOLCHAIN}-nm")

SET (_CMAKE_TOOLCHAIN_PREFIX ${XTOOLCHAIN}-)

# INCLUDE (CMakeForceCompiler)
SET (CMAKE_C_COMPILER ${xcc})
SET (CMAKE_ASM_COMPILER ${xcc})
# Prevent the compiler test sequence from CMakeTestCCompiler.cmake
# a cleaner solution should be to give the compiler the proper flags
SET (CMAKE_C_COMPILER_FORCED TRUE)
# SET (CMAKE_DEPFILE_FLAGS_C "-ppd=<DEPFILE>")

GET_FILENAME_COMPONENT(xccpath "${xcc}" DIRECTORY)
GET_FILENAME_COMPONENT(CMAKE_SYSROOT "${xccpath}/.." REALPATH)

INCLUDE_DIRECTORIES (${CMAKE_SYSROOT}/include
                   ${CMAKE_SYSROOT}/msp430/include)

SET (LINKER_FLAGS "--reread_libs --warn_sections --rom_model ")
SET (LINKER_FLAGS "${LINKER_FLAGS} --heap_size=80 --stack_size=80")
SET (LIB_PATH "-i${CMAKE_SYSROOT}/msp430/include -i${CMAKE_SYSROOT}/lib")
SET (LINKER_SCRIPT "${CMAKE_SYSROOT}/msp430/include/lnk_msp430g2533.cmd")
SET (CMAKE_C_LINK_FLAGS "${LINKER_FLAGS} ${LIB_PATH} ${LINKER_SCRIPT}")

IF (NOT xar OR NOT xld)
  MESSAGE (FATAL_ERROR
    "Unable to locate a complete ${XTOOLCHAIN} C/C++ toolchain: ${xar},${xld}")
ENDIF ()

SET (CMAKE_NOT_USING_CONFIG_FLAGS 1) # allow custom DEBUG/RELEASE flags

SET (xdisassemble ${xobjdump} -dS)

#-----------------------------------------------------------------------------
# Link the final application
#  :app: the application name
#  :dependencies: one or more static libraries to link with
#-----------------------------------------------------------------------------
MACRO (link_app app)
  TARGET_LINK_LIBRARIES (${app}
                         ${ARGN})
  create_map_file (${app})
ENDMACRO ()

