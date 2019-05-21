#-----------------------------------------------------------------------------
# Tools for all projects
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# CMake version required for these macros
#-----------------------------------------------------------------------------
CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

#-----------------------------------------------------------------------------
# Find useful tools and host applications
#-----------------------------------------------------------------------------
IF (NOT PYTHON)
  MESSAGE (FATAL_ERROR "Python interpreter is missing")
ENDIF (NOT PYTHON)
# Define the global host tool directory
GET_FILENAME_COMPONENT (TOPDIR ${CMAKE_CURRENT_SOURCE_DIR} DIRECTORY)
SET (HOSTDIR ${TOPDIR}/host)
# Convert the BUILD type
STRING (TOLOWER ${CMAKE_BUILD_TYPE} BLD_TYPE)
# Find the various compilation and helper tools
FIND_PROGRAM (lsh sh)
FIND_PROGRAM (cat cat)
FIND_PROGRAM (rm rm)
FIND_PROGRAM (cppcheck cppcheck.sh PATHS ${HOSTDIR}/bin)
FIND_PROGRAM (cwrap cwrapper.sh PATHS ${HOSTDIR}/bin)
FIND_PROGRAM (dupdir dupdir.sh PATHS ${HOSTDIR}/bin)
FIND_PROGRAM (gitbldver gitbldver.sh PATHS ${HOSTDIR}/bin)
FIND_PROGRAM (tellnewer tellnewer.sh PATHS ${HOSTDIR}/bin)
FIND_PROGRAM (nrfhex nrfhex.sh PATHS ${HOSTDIR}/bin)
FIND_PROGRAM (xz xz)
FIND_PROGRAM (protoc protoc)
FIND_PROGRAM (doxygen doxygen PATH_SUFFIXES bin)
FIND_PROGRAM (sphinx sphinx-build PATH_SUFFIXES bin)
FIND_PROGRAM (wine wine PATH_SUFFIXES bin)
FIND_PROGRAM (pdflatex pdflatex)

#-----------------------------------------------------------------------------
# Host tool abstraction (option switches may differ)
#-----------------------------------------------------------------------------
SET (XARGS_OPT "-r")
IF (CMAKE_HOST_UNIX)
  FIND_PROGRAM (CMAKE_UNAME uname /bin /usr/bin)
  IF (CMAKE_UNAME)
    EXEC_PROGRAM (uname ARGS -s OUTPUT_VARIABLE CMAKE_HOST_SYSTEM_NAME)
    IF (CMAKE_HOST_SYSTEM_NAME MATCHES "Darwin")
      SET (XARGS_OPT "")
    ENDIF ()
  ENDIF ()
ENDIF ()
