#-----------------------------------------------------------------------------
# Common macros for all toolchains
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# CMake version required for these macros
#-----------------------------------------------------------------------------
CMAKE_MINIMUM_REQUIRED (VERSION 3.5)

# multiple inclusion flag
IF (NOT TDE_COMMON_CMAKE)
# not indented for readibility
SET (TDE_COMMON_CMAKE 1)

INCLUDE (AddFileDependencies)

#-----------------------------------------------------------------------------
# Default targets
#-----------------------------------------------------------------------------
ADD_CUSTOM_TARGET (generate)
ADD_CUSTOM_TARGET (finalize)
ADD_CUSTOM_TARGET (document)

#-----------------------------------------------------------------------------
# Use a launcher for building C/C++ source files
#-----------------------------------------------------------------------------
MACRO (log_warning_messages)
  SET_PROPERTY (GLOBAL PROPERTY RULE_LAUNCH_COMPILE ${cwrap})
ENDMACRO ()

#-----------------------------------------------------------------------------
# Assert a directory does exist
#  :name: directory name (for user information only)
#  :path: directory to test for presence
#-----------------------------------------------------------------------------
MACRO (assert_directory name path)
  IF (NOT IS_DIRECTORY ${path})
    GET_FILENAME_COMPONENT (TOPDIR ${CMAKE_SOURCE_DIR} DIRECTORY)
    FILE (RELATIVE_PATH mispath ${TOPDIR} ${path})
    FILE (RELATIVE_PATH comppath ${TOPDIR} ${CMAKE_CURRENT_SOURCE_DIR})
    SET (error "Missing ${name} dir \"${mispath}\"")
    MESSAGE (FATAL_ERROR "\n>> ${error}, \"${comppath}\" needs it\n")
  ENDIF (NOT IS_DIRECTORY ${path})
ENDMACRO ()

#-----------------------------------------------------------------------------
# Extract a parameter value from a list of argument.
# The parameter should be defined as key value pair: "PARAMETER value"
#  :outvar: output variable
#  :remargs: the input argument list w/o the removed argument
#  :parameter: the parameter name to look for
#  :*: list of arguments to parse
#-----------------------------------------------------------------------------
MACRO (extract_parameter outvar remargs parameter)
  SET (args ${ARGN})
  SET (${outvar})
  SET (${remargs})
  SET (match)
  SET (resume 1)
  FOREACH (arg ${args})
    IF (NOT resume)
      LIST (APPEND ${remargs} ${arg})
      CONTINUE ()
    ENDIF ()
    IF (match)
      # if the previous argument matched the seeked parameter
      # copy the current argument as the output value
      SET (${outvar} ${arg})
      # clear up the match flag
      SET (match)
      SET (resume)
    ELSE ()
      # the previous argument was not a match, try with the current one
      IF (${arg} STREQUAL ${parameter})
        # on match, flag a marker
        SET (match 1)
      ELSE ()
        LIST (APPEND ${remargs} ${arg})
      ENDIF ()
    # end of current argument loop
    ENDIF()
  ENDFOREACH ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Test if a parameter is defined in a list of argument.
#  :outvar: output variable
#  :remargs: the input argument list w/o the removed argument
#  :parameter: the parameter name to look for
#  :*: list of arguments to parse
# Note: do NOT use 'args' as the caller parameter variable name.
#-----------------------------------------------------------------------------
MACRO (test_parameter outvar remargs parameter)
  SET (args ${ARGN})
  SET (${outvar})
  SET (${remargs})
  FOREACH (arg ${args})
    STRING (COMPARE EQUAL ${arg} ${parameter} valdef)
    IF (valdef)
      SET (${outvar} ${valdef})
    ELSE ()
      LIST (APPEND ${remargs} ${arg})
    ENDIF ()
  ENDFOREACH ()
ENDMACRO ()

#------------------------------------------------------------------------------
# List all subdirectories
# :outvar: output variable
# :dir: where to start seeking from
#------------------------------------------------------------------------------
MACRO (subdirlist outvar seekdir)
  SET (sub_args ${ARGN})
  test_parameter (recursive sub_args RECURSIVE ${sub_args})
  test_parameter (relative sub_args RELATIVE ${sub_args})
  IF (NOT DEFINED recursive)
    SET (recursive 0)
  ENDIF ()
  IF (NOT DEFINED relative)
    SET (relative 0)
  ENDIF ()
  SET (dirlist)
  IF ( relative )
    FILE (GLOB_RECURSE children
          LIST_DIRECTORIES ${recursive}
          RELATIVE ${seekdir}
          ${seekdir}/*)
     FOREACH(child ${children})
       IF (IS_DIRECTORY ${seekdir}/${child})
         LIST (APPEND dirlist ${child})
       ENDIF()
     ENDFOREACH()
  ELSE ()
    FILE (GLOB_RECURSE children
          LIST_DIRECTORIES ${recursive}
          ${seekdir}/*)
     FOREACH(child ${children})
       IF (IS_DIRECTORY ${child})
         LIST (APPEND dirlist ${child})
       ENDIF()
     ENDFOREACH()
  ENDIF ()
  SET (${outvar} ${dirlist})
ENDMACRO ()

#------------------------------------------------------------------------------
# List all subprojects, that is directories that contain a CMakeLists.txt file
# :outvar: output variable
#------------------------------------------------------------------------------
MACRO (find_subprojects outvar)
  SET (${outvar})
  FILE (GLOB subfiles
        LIST_DIRECTORIES true
        RELATIVE ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/*/CMakeLists.txt)
  SET (args ${ARGN})
  FOREACH (prj ${subfiles})
    GET_FILENAME_COMPONENT (subprj ${prj} DIRECTORY)
    IF (args)
      IF (${subprj} IN_LIST args)
        CONTINUE ()
      ENDIF ()
    ENDIF ()
    LIST (APPEND ${outvar} ${subprj})
  ENDFOREACH ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Replicate a whole directory tree from one directory to another,
# filtering out files if needed.
# This macro is useful to get rid of hidden files (such as .git) for preparing
# a target image file, such as a CRAMFS image file
#  :task_name: the name of the task to create (useful for dependencies)
#  :_unused: not used, kept for compatibility purposes
#  :srcdir: root of the source directory
#  :dstdir: destination directory
#-----------------------------------------------------------------------------
MACRO (replicate_tree task_name _unused srcdir dstdir)
  SET (reptree_args ${ARGN})
  test_parameter (no_warn reptree_args NO_WARN ${reptree_args})
  STRING (LENGTH ${CMAKE_BINARY_DIR} cmake_bin_dir_len)
  STRING (SUBSTRING ${dstdir} 0 ${cmake_bin_dir_len} dstdir_prefix)
  STRING (COMPARE EQUAL ${CMAKE_BINARY_DIR} ${dstdir_prefix} dstdir_match)
  IF (NOT no_warn)
    MESSAGE (STATUS "You should not be using replicate_tree which is obsolete")
  ENDIF ()
  IF (NOT dstdir_match)
    MESSAGE (FATAL_ERROR "Destination dir outside CMake build dir")
  ELSE (NOT dstdir_match)
    ADD_CUSTOM_TARGET (${task_name})
    ADD_CUSTOM_COMMAND (TARGET ${task_name} POST_BUILD
                        COMMAND ${dupdir} cmake ${srcdir} ${dstdir}
                        COMMENT "Replicating files for task ${task_name}")
    GET_DIRECTORY_PROPERTY (extra_clean_files ADDITIONAL_MAKE_CLEAN_FILES)
    LIST (APPEND extra_clean_files ${dstdir})
    SET_DIRECTORY_PROPERTIES (PROPERTIES ADDITIONAL_MAKE_CLEAN_FILES
                              "${extra_clean_files}")
    SET_SOURCE_FILES_PROPERTIES ("${dstdir}" PROPERTIES GENERATED TRUE)
  ENDIF (NOT dstdir_match)
ENDMACRO (replicate_tree srcdir dstdir)

#-----------------------------------------------------------------------------
# Generate a source and header files containing GIT information.
#  :app_name: the name of the application, for naming the generated functions
#  :topdir:   the directory to 'tag' (usually the project root directory)
#             ${CMAKE_SOURCE_DIR} usually refers to the project root dir, and
#             ${CMAKE_CURRENT_SOURCE_DIR} usually refers to the component dir
#  VERSION "x.y.z" optional, specify application version
#  BUILD "build" optional, specify build type (DEBUG, RELEASE, ...)
#-----------------------------------------------------------------------------
MACRO (tag_application app_name topdir)
  SET (gen_args ${ARGN})
  extract_parameter (tag_app_version gen_args "VERSION" ${gen_args})
  extract_parameter (tag_app_build gen_args "BUILD" ${gen_args})
  SET (TAGFILE_HEADER ${app_name}_gitbldver.h)
  SET (TAGFILE_SRC gitbldver.c)
  SET (tag_header ${CMAKE_CURRENT_BINARY_DIR}/${TAGFILE_HEADER})
  SET (tag_src ${CMAKE_CURRENT_BINARY_DIR}/${TAGFILE_SRC})
  FOREACH (gitverfile ${tag_src} ${tag_header})
    ADD_CUSTOM_COMMAND (OUTPUT ${gitverfile}
                        COMMAND ${gitbldver}
                                ${gitverfile}
                                  ${app_name} ${topdir}
                                  ${tag_app_version} ${tag_app_build}
                        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
                        COMMENT "Retrieving GIT version" VERBATIM)
    GET_DIRECTORY_PROPERTY (extra_clean_files ADDITIONAL_MAKE_CLEAN_FILES)
    LIST (APPEND extra_clean_files ${gitverfile})
    SET_DIRECTORY_PROPERTIES (PROPERTIES ADDITIONAL_MAKE_CLEAN_FILES
                              "${extra_clean_files}")
    SET_SOURCE_FILES_PROPERTIES (${gitverfile} PROPERTIES GENERATED TRUE)
  ENDFOREACH ()
  ADD_FILE_DEPENDENCIES (${tag_src} ${tag_header})
ENDMACRO ()

#-----------------------------------------------------------------------------
# Define dependencies
# The macro expects a list of components.
#-----------------------------------------------------------------------------
MACRO (require)
  SET (inc_dirs)
  FOREACH (comp ${ARGV})
    assert_directory ("Component" ${CMAKE_SOURCE_DIR}/${comp}/include)
    LIST (APPEND inc_dirs ${CMAKE_SOURCE_DIR}/${comp}/include)
  ENDFOREACH (comp)
  INCLUDE_DIRECTORIES (${inc_dirs})
ENDMACRO ()

#-----------------------------------------------------------------------------
# Build a component (i.e. a static library) from the specified source files
# The component name is automatically extracted from the component directory
# The macro expects a list of source files to build, relative to the component
# directory.
# Some special keywords are reserved:
#   :NO_TAGSOURCE: do not define the Trace source
#   :NO_TAGNAME:   do not define the Trace name
#   :TAGSOURCE:    define an alternative Trace source, which should follow this
#                  keyword
#   :EXTRA:        any source file listed after this keyword is used to build
#                  a special <component>_extra archive
#-----------------------------------------------------------------------------
MACRO (build_component_from)
  SET (srcs)
  SET (extra_srcs)
  SET (src srcs)
  GET_FILENAME_COMPONENT (component ${CMAKE_CURRENT_SOURCE_DIR} NAME)
  STRING (TOUPPER ${component} ucomp)
  SET (tagsource "-DTAGSOURCE=TTM_${ucomp}")
  SET (tagname "-DTAGNAME=${component}")
  test_parameter (autoincdir arguments AUTO_INCLUDE ${ARGV})
  SET (INCDIRS)
  FOREACH (arg ${arguments})
    IF (arg STREQUAL "EXTRA")
      IF (NOT CMAKE_C_COMPILER_ID STREQUAL "TI")
        SET (src extra_srcs)
        # Emulate LIST syntax as LIST does not have a PARENT_SCOPE option
        SET (EXTRALIBS "${EXTRALIBS};${component}" PARENT_SCOPE)
      ENDIF ()
    ELSEIF (arg STREQUAL "NO_TAGSOURCE")
      SET (tagsource)
    ELSEIF (arg STREQUAL "NO_TAGNAME")
      SET (tagname)
    ELSEIF (arg STREQUAL "TAGSOURCE")
      SET (assign_tagsource 1)
    ELSEIF (assign_tagsource)
      STRING (TOUPPER ${arg} uarg)
      SET (tagsource "-DTAGSOURCE=TTM_${uarg}")
      SET (assign_tagsource)
    ELSE ()
      LIST (APPEND ${src} ${arg})
      IF (autoincdir)
        GET_FILENAME_COMPONENT (srcdir ${arg} DIRECTORY)
        SET (fpsrcdir ${CMAKE_CURRENT_SOURCE_DIR}/${srcdir})
        IF (IS_DIRECTORY ${fpsrcdir})
          IF (NOT ${fpsrcdir} IN_LIST INCDIRS)
            LIST (APPEND INCDIRS ${fpsrcdir})
          ENDIF ()
        ENDIF ()
      ENDIF ()
    ENDIF ()
  ENDFOREACH (arg)
  IF (tagsource)
    ADD_DEFINITIONS(${tagsource})
  ENDIF (tagsource)
  IF (tagname)
    ADD_DEFINITIONS(${tagname})
  ENDIF (tagname)
  IF (IS_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/include)
    INCLUDE_DIRECTORIES (${CMAKE_CURRENT_SOURCE_DIR}/include)
  ENDIF ()
  IF (INCDIRS)
    INCLUDE_DIRECTORIES (${INCDIRS})
  ENDIF ()
  IF (DEFINED LIBRARY_VARIANT)
    SET (library_name ${component}_${LIBRARY_VARIANT})
  ELSE ()
    SET (library_name ${component})
  ENDIF ()
  IF (srcs)
    ADD_LIBRARY (${library_name} ${srcs})
  ENDIF (srcs)
  IF (extra_srcs)
    ADD_LIBRARY (${library_name}_extra ${extra_srcs})
  ENDIF (extra_srcs)
  FOREACH (src ${srcs} ${extra_srcs})
    GET_FILENAME_COMPONENT (ext ${src} EXT)
    IF ("${ext}" STREQUAL ".S")
      # .S files should be preprocessed
      SET_SOURCE_FILES_PROPERTIES (${src} PROPERTIES LANGUAGE "C")
    ENDIF ()
  ENDFOREACH ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Create a MAP file from an ELF file to dump symbols
#  :app: the path to the input ELF file
#  output file is generated within the same directory as the ELF file
#-----------------------------------------------------------------------------
MACRO (create_map_file app)
  GET_TARGET_PROPERTY (old_link_flags ${app}
                       LINK_FLAGS)
  IF (NOT old_link_flags)
    SET (old_link_flags)
  ENDIF ()
  SET (mapfile "${CMAKE_CURRENT_BINARY_DIR}/${app}.map")
  IF (NOT CMAKE_C_COMPILER_ID STREQUAL "TI")
    SET_TARGET_PROPERTIES (${app} PROPERTIES LINK_FLAGS
      "${old_link_flags} ${LDCALL}--Map ${LDCALL}${mapfile}")
  ENDIF ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Work around for buggy FILE_FILE
#  :output: the output variable, updated with the file path if found
#  :filename: the name of the file to look for
#-----------------------------------------------------------------------------
MACRO (tde_find_file output filename)
  STRING (REPLACE ":" ";" CMPATH $ENV{PATH})
  SET (${output})
  FOREACH (pathname ${CMPATH})
     FILE (GLOB glob ${pathname}/${filename})
     IF (glob)
        SET (${output} ${glob})
        BREAK ()
     ENDIF ()
  ENDFOREACH ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Find a file within a wine emulated environment
#  :output: the output variable, updated with the file path if found
#  :filename: the name of the file to look for
#-----------------------------------------------------------------------------
MACRO (tde_find_winfile output filename)
  SET (${output})
  SET (prefix "$ENV{HOME}/.wine/drive_c")
  FILE (GLOB_RECURSE glob "${prefix}/${filename}")
  IF (glob)
    LIST (GET glob 0 pathname)
    STRING (REPLACE ${prefix} "C:" ${output} ${pathname})
  ENDIF ()
ENDMACRO ()

#-----------------------------------------------------------------------------
# Build a BlueGiga firmware, replacing placeholder with actual values
# Dependency management is quite complex and not handled by CMake:
# the bgbuild Python script takes care of managing dependencies, which explain
# why the CMake target is always called
#  :task_name: the name of the task to create (useful for dependencies)
#  :outdir: the destination directory
#  :bgproj: the path to the BG project file
#-----------------------------------------------------------------------------
MACRO (build_ble_fw task_name outdir bgproj)
  # bgbuild tool is a Windows-only executable
  # we need the wine emulator to run this executable (and the other tools it
  # relies on, such as a 8051 compiler...)
  IF (NOT wine)
    MESSAGE(FATAL_ERROR "wine is required to build BB script")
  ENDIF ()
  IF (CMAKE_BUILD_TYPE STREQUAL "DEBUG")
    SET (builddef "-DDEBUG=1")
  ELSE ()
    SET (builddef)
  ENDIF ()
  GET_FILENAME_COMPONENT (bgoutput ${bgproj} NAME)
  ADD_CUSTOM_COMMAND (OUTPUT ${outdir}/${bgoutput}
                      COMMAND ${bgbuild}
                        ${builddef}
                        -o ${outdir} ${bgproj}
                      WORKING_DIRECTORY ${outdir}
                      DEPENDS ${bgproj}
                      COMMENT "Building BLE firmware")
  ADD_CUSTOM_TARGET(${task_name} DEPENDS ${outdir}/${bgoutput})
ENDMACRO ()

#-----------------------------------------------------------------------------
# Bitmap font library generation
#   :target: target dependency to declare
#   :fontlib: path to the font library to create (archive file)
#   :fontdir: path to the directory that contains the font bitmap
#-----------------------------------------------------------------------------
MACRO (create_font_library target fontlib fontdir)
  FILE (GLOB FONT_SRCS
        RELATIVE ${fontdir}
        ${fontdir}/font*x*.bin)
  SET (FONT_OBJS)
  FOREACH (fontsrc ${FONT_SRCS})
    GET_FILENAME_COMPONENT (fontbase ${fontsrc} NAME_WE)
    SET (fontobj
         ${CMAKE_CURRENT_BINARY_DIR}/${fontbase}${CMAKE_C_OUTPUT_EXTENSION})
    ADD_CUSTOM_COMMAND (OUTPUT ${fontobj}
                        COMMAND ${xobjcopy}
                                  --binary-architecture armv5te
                                  -I binary
                                  -O elf32-littlearm
                                  ${fontsrc}
                                  ${fontobj}
                        # running from source directory is important for
                        # symbol name generation
                        WORKING_DIRECTORY ${fontdir})
    LIST (APPEND FONT_OBJS ${fontobj})
  ENDFOREACH ()
  ADD_CUSTOM_COMMAND (OUTPUT ${fontlib}
                      DEPENDS ${FONT_OBJS}
                      COMMAND ${xar} cru ${fontlib} ${FONT_OBJS})
  ADD_CUSTOM_TARGET(${target} ALL DEPENDS ${fontlib})
ENDMACRO()

#-----------------------------------------------------------------------------
# Documentation generation using Sphinx
# Requires Python module: Sphinx,Pygments,docutils,Jinja2,breathe
#  :task_name: the name of the task to create (useful for dependencies)
#  Optional parameters:
#    PROJECT: project directory for which to generate the documentation
#    CPATHS: a list of native source code paths to extract Doxygen doc from
#    PYPATHS: a list of extra Python paths to find documented Python modules
#    DEFINITIONS: all remaining arguments are forward to Sphinx as preprocessor
#                 definitions
#-----------------------------------------------------------------------------
MACRO (create_doc task_name)
  SET (doc_args ${ARGN})
  IF (DOC_FORMAT)
    IF (DOC_FORMAT STREQUAL "html")
      SET (format "html")
    ELSEIF (DOC_FORMAT STREQUAL "pdf")
      SET (format "latex")
    ELSE ()
      MESSAGE(FATAL_ERROR "Invalid documentation format: ${DOC_FORMAT}")
    ENDIF ()
    STRING (TOUPPER ${format} uformat)
    extract_parameter (prjdir doc_args "PROJECT" ${doc_args})
    extract_parameter (cpaths doc_args "CPATHS" ${doc_args})
    extract_parameter (pypaths doc_args "PYPATHS" ${doc_args})
    test_parameter (defs doc_args "DEFINITIONS" ${doc_args})
    IF (NOT prjdir)
      SET (prjdir ${CMAKE_CURRENT_SOURCE_DIR})
    ENDIF ()
    SET (SPHINX_TPL_DIR "${HOSTDIR}/etc/sphinx")
    SET (CFG_DIR "${CMAKE_CURRENT_SOURCE_DIR}/config")
    SET (SPHINX_SOURCES_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
    SET (BINARY_BUILD_DIR "${CMAKE_BINARY_DIR}")
    SET (DOC_CACHE_DIR "${CMAKE_CURRENT_BINARY_DIR}/cache")
    SET (DOXYGEN_OUTPUT_DIR "${DOC_CACHE_DIR}/doxygen")
    SET (SPHINX_CACHE_DIR "${DOC_CACHE_DIR}/sphinx")
    SET (SPHINX_CONFIG "${SPHINX_CACHE_DIR}/conf.py")
    SET (SPHINX_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/${format}")
    SET (SPHINX_CFG_DIR "${SPHINX_SOURCES_DIR}")
    SET (DOXYGEN_FLAGS)
    IF (defs)
      FOREACH (def ${doc_args})
        IF (DOXYGEN_FLAGS)
          SET (DOXYGEN_FLAGS ${DOXYGEN_FLAGS} -f ${def})
        ELSE ()
          SET (DOXYGEN_FLAGS -f ${def})
        ENDIF ()
     ENDFOREACH ()
    ENDIF()
    IF (CMAKE_BUILD_TYPE STREQUAL "RELEASE")
      SET (SPHINX_FLAGS ${SPHINX_FLAGS} "-W")
    ENDIF ()
    SET (SPHINX_FLAGS ${SPHINX_FLAGS} "-q")
    SET (SPHINX_DOCGEN_FLAGS)
    SET (limitopts)
    IF ( DOCUMENT_COMPONENTS )
      STRING (REPLACE ":" ";" DOCS ${DOCUMENT_COMPONENTS})
      FOREACH (comp ${DOCS})
        SET (limitopts ${limitopts} -l ${comp})
      ENDFOREACH ()
    ENDIF ()
    IF ( cpaths )
      IF (DOC_WARN)
        SET (DOXYGEN_FLAGS ${DOXYGEN_FLAGS} -w)
      ENDIF ()
      SET (CPATH_OPT)
      STRING (REPLACE ":" ";" cpaths ${cpaths})
      FOREACH (cpath ${cpaths})
        LIST (APPEND CPATH_OPT "-c" ${cpath})
      ENDFOREACH ()
      # Generate Doxygen XML documentation needed for Breathe
      ADD_CUSTOM_COMMAND (OUTPUT ${DOXYGEN_OUTPUT_DIR}/doxyfile
                          COMMAND mkdir -p ${DOXYGEN_OUTPUT_DIR}
                          COMMAND ${PYTHON} ${mkdoccfg}
                            -g "${SPHINX_TPL_DIR}/doxygen.tpl"
                            -j ${prjdir}
                            ${CPATH_OPT}
                            -o ${DOXYGEN_OUTPUT_DIR}/doxyfile
                            -a ${DOXYGEN_OUTPUT_DIR}
                            -b ${CMAKE_BUILD_TYPE}
                            ${DOXYGEN_FLAGS}
                            ${limitopts}
                          DEPENDS "${SPHINX_TPL_DIR}/doxygen.tpl"
                          COMMENT "Configuring XML API doc for Doxygen")
      ADD_CUSTOM_TARGET (${task_name}_xml_cfg
                         DEPENDS ${DOXYGEN_OUTPUT_DIR}/doxyfile)
      ADD_CUSTOM_COMMAND (OUTPUT ${DOXYGEN_OUTPUT_DIR}/xml/index.xml
                          COMMAND ${doxygen}
                            ${DOXYGEN_OUTPUT_DIR}/doxyfile
                          COMMENT "Building XML API doc with Doxygen")
      ADD_CUSTOM_TARGET (${task_name}_xml
                         DEPENDS ${DOXYGEN_OUTPUT_DIR}/xml/index.xml)
      ADD_DEPENDENCIES (${task_name}_xml ${task_name}_xml_cfg)
      SET (SPHINX_DOCGEN_FLAGS -a ${DOXYGEN_OUTPUT_DIR}/xml)
    ENDIF ()
    IF (DOC_JOBS)
      SET (SPHINX_FLAGS ${SPHINX_FLAGS} -j ${DOC_JOBS})
    ENDIF ()
    # This target builds HTML documentation using Sphinx.
    SET (EXTRA_OPTS)
    STRING (REPLACE ":" ";" pypaths ${pypaths})
    FOREACH (pypath ${pypaths})
      LIST (APPEND EXTRA_OPTS "-p" ${pypath})
    ENDFOREACH ()
    ADD_CUSTOM_COMMAND (OUTPUT ${SPHINX_CONFIG}
                        COMMAND mkdir -p ${SPHINX_CACHE_DIR}
                        COMMAND ${PYTHON} ${mkdoccfg}
                          -d
                          -s "${SPHINX_TPL_DIR}/sphinx.tpl"
                          -j ${prjdir}
                          -o ${SPHINX_CONFIG}
                          ${EXTRA_OPTS}
                          ${SPHINX_DOCGEN_FLAGS}
                          ${limitopts}
                        DEPENDS "${SPHINX_TPL_DIR}/sphinx.tpl"
                        COMMENT "Configuring documentation for Sphinx")
    ADD_CUSTOM_TARGET (${task_name}_${format}_cfg
                       DEPENDS ${SPHINX_CONFIG})
    ADD_CUSTOM_TARGET (${task_name}_${format}
                       COMMAND mkdir -p ${SPHINX_BINARY_DIR}
                       COMMAND ${PYTHON} ${sphinx}
                         -b ${format}
                         -d ${SPHINX_CACHE_DIR}
                         -c ${SPHINX_CACHE_DIR}
                         ${SPHINX_FLAGS}
                         ${SPHINX_SOURCES_DIR}
                         ${SPHINX_BINARY_DIR}
                       COMMENT "Building ${uformat} documentation with Sphinx")
    ADD_DEPENDENCIES (${task_name}_${format} ${task_name}_${format}_cfg)
    IF ( ${format} STREQUAL latex )
      IF (NOT pdflatex)
        MESSAGE (FATAL_ERROR "pdflatex tool not found ${pdflatex}")
      ENDIF ()
      # Note: pdflatex has to be run twice in order to generate indexes (see: #656)
      ADD_CUSTOM_TARGET (${task_name}_${format}_pdf
                         WORKING_DIRECTORY ${SPHINX_BINARY_DIR}
                         # remove first redirection to NULL for displaying errors
                         COMMAND ${pdflatex} ${task_name}.tex >/dev/null
                         COMMAND ${pdflatex} ${task_name}.tex >/dev/null
                         COMMENT "Building PDF documentation from LaTeX")
      ADD_DEPENDENCIES (${task_name}_${format}_pdf ${task_name}_${format})
      ADD_DEPENDENCIES (document ${task_name}_${format}_pdf)
    ENDIF ()
    IF ( cpaths )
      ADD_DEPENDENCIES (${task_name}_${format} ${task_name}_xml)
      ADD_DEPENDENCIES (${task_name}_${format}_cfg ${task_name}_xml)
    ENDIF ()
    ADD_DEPENDENCIES (document ${task_name}_${format})
  ENDIF ()
ENDMACRO (create_doc)

#-----------------------------------------------------------------------------
# Create byproducts from an application
#  :app: the application name
#  Optional parameters:
#    IHEX: Generate a Intel HEX output file
#    SREC: Generate a Motorola SREC output file
#    BIN: Generate a raw binary output file
#    ASM: Disassemble the application
#    SIZE: Report the size of the main application section
#-----------------------------------------------------------------------------
MACRO (post_gen_app app)
  SET (gen_args ${ARGN})
  test_parameter (gen_ihex doc_args "IHEX" ${gen_args})
  test_parameter (gen_srec doc_args "SREC" ${gen_args})
  test_parameter (gen_asm doc_args "ASM" ${gen_args})
  test_parameter (gen_bin doc_args "BIN" ${gen_args})
  test_parameter (gen_size doc_args "SIZE" ${gen_args})
  SET (appfile ${app}${CMAKE_EXECUTABLE_SUFFIX})
  IF (gen_asm)
    ADD_CUSTOM_COMMAND (TARGET ${app} POST_BUILD
                        COMMAND ${xdisassemble} ${DISASSEMBLE_OPTS}
                             ${appfile} > ${app}.S
                        COMMENT "Disassembling ELF file" VERBATIM)
  ENDIF ()
  IF (gen_size)
    ADD_CUSTOM_COMMAND (TARGET ${app} POST_BUILD
                        COMMAND ${xsize}
                             ${appfile})
  ENDIF ()
  IF (gen_ihex)
    ADD_CUSTOM_COMMAND (TARGET ${app} POST_BUILD
                        COMMAND ${xobjcopy}
                             -O ihex
                             ${appfile} ${app}.hex
                        COMMAND chmod -x ${app}.hex
                        COMMENT "Converting ELF to HEX" VERBATIM)
  ENDIF ()
  IF (gen_srec)
    ADD_CUSTOM_COMMAND (TARGET ${app} POST_BUILD
                        COMMAND ${xobjcopy}
                             -O srec
                             ${appfile} ${app}.srec
                        COMMAND chmod -x ${app}.srec
                        COMMENT "Converting ELF to SREC" VERBATIM)
  ENDIF ()
  IF (gen_bin)
    ADD_CUSTOM_COMMAND (TARGET ${app} POST_BUILD
                        COMMAND ${xobjcopy}
                             -O binary
                             ${appfile} ${app}.bin
                        COMMAND chmod -x ${app}.bin
                        COMMAND /bin/echo -n "   blob size: "
                        COMMAND ls -lh ${app}.bin | awk "{print \$5}"
                        COMMENT "Converting ELF to BIN" VERBATIM)
  ENDIF ()
ENDMACRO ()

#-----------------------------------------------------------------------------

# For some reason, CMAKE_C_COMPILER_ID gets cleared out
# preserve a copy of this important definition
SET (XCC_COMPILER_ID ${CMAKE_C_COMPILER_ID})

# Get rid of a stupid, with no disable method available that makes CMake
# always complain about command-line variables not actually used within the
# CMake project files. So, let use them for no other purpose than workaround
# this useless "feature"
STRING (TOLOWER "${XCC_VER}" _XCC_VER)
STRING (TOLOWER "${XCC_VERBOSE}" _XCC_VERBOSE)
STRING (TOLOWER "${XTOOLCHAIN}" _XTOOLCHAIN)
STRING (TOLOWER "${TAG_RELEASE}" _TAG_RELEASE)
STRING (TOLOWER "${TARGET}" _TARGET)
STRING (TOLOWER "${PYTHON}" _PYTHON)
STRING (TOLOWER "${DOC_ONLY}" _DOC_ONLY)
STRING (TOLOWER "${DOC_FORMAT}" _DOC_FORMAT)
STRING (TOLOWER "${DOC_JOBS}" _DOC_JOBS)
STRING (TOLOWER "${CMAKE_TOOLCHAIN_FILE}" _CMAKE_TOOLCHAIN_FILE)
STRING (TOLOWER "${XSYSROOT}" _XSYSROOT)

# multiple inclusion flag
ENDIF (NOT TDE_COMMON_CMAKE)
