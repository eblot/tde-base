#!/bin/sh
#----------------------------------------------------------------------------
# Front-end for building projects
#----------------------------------------------------------------------------

# Be sure that all tools do not emit localized strings
export LC_ALL="C"

#--- XTC (Cross ToolChain) recommended/enforced tool versions
SYS_PYTHON_VER="3.5.2"
SYS_CMAKE_VER="3.5.1"
SYS_XTCCC_VER="6.3.0"
SYS_XTCBU_VER="2.32"
SYS_XTCCL_VER="8.0.0"
SYS_MAKE_VER="3.81"
SYS_NINJA_VER="1.6.0"
SYS_DOXYGEN_VER="1.8.11"
SYS_SPHINX_VER="1.5.3"

# detects build tools
TOPDIR="$PWD"
TOOLCHAINS="gcc|clang"
TARGETS="host|cortex-m0plus|cortex-m4|cortex-m4f"

# Die with an error message
die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

PARSE_CONF=1
# Parse the command line and update configuration, if not disabled
for opt do
    case "$opt" in
      -B)
        PARSE_CONF=0
        ;;
      -*)
        ;;
      *)
        break
        ;;
    esac
done

# Read default configuration
if [ ${PARSE_CONF} -gt 0 ]; then
    if [ -f "config/build.conf" ]; then
        . config/build.conf
    fi
fi

# Find and order projects
if [ ! -x 'host/bin/calcdeps.py' ]; then
    die "calcdeps.py tool missing"
fi
for e in `ls -1d * 2> /dev/null`; do
   if [ -d "$e" ]; then
       if [ ! -f "$e/CMakeLists.txt" ]; then
            if [ -z "${EXCLUDE_DIRS}" ]; then
                EXCLUDE_DIRS="$e"
            else
                EXCLUDE_DIRS="${EXCLUDE_DIRS},$e"
            fi
       fi
   fi
done

# Find all build directories
BUILD_DIRS=`ls -d build* 2> /dev/null | tr '\012' ','`
if [ -z "${BUILD_DIRS}" ]; then
    BUILD_DIRS="build,"
fi
if [ -n "${EXCLUDE_DIRS}" ]; then
    DEPS_EXCLUDE="-x ${EXCLUDE_DIRS}"
else
    DEPS_EXCLUDE=""
fi
PROJECTS=`host/bin/calcdeps.py ${DEPS_EXCLUDE}`

# Default configuration
AUTO_PROJECTS=0
CLEAN=0
INSTALL=0
GENDOC=0
IGNORE_ERROR=0
VERBOSE=""
MAKEPRINTDIR="--no-print-directory"
VERIFY=1
XSACHECK=0
DOCCHECK=0
FORCEVER=0
FORCEBLD=0
BUILD=${BUILD:-"DEBUG"}
TAG_RELEASE=${TAG_RELEASE:-1}
COMPSELOPT=""
CMAKEOPT=""
PROJECTDESC=""
SKIPBUILD=0
JOBS=""
NINJAJOBS=""
DOCJOBS=""
DOCCOMPS=""
DOCFORMAT="html"
BUILD_RAMDISK_MSIZE=${BUILD_RAMDISK_MSIZE:-0}

SVNDOMAINS="github.com"

# If TAG_RELEASE should be detected automatically, attempts to guess whether
# the current directory is managed under SVN and if the SVN repository allows
# to tag an official version
if [ "${TAG_RELEASE}" = "auto" ]; then
    TAG_RELEASE=0
    SVN=`which svn`
    if [ -n ${SVN} -a -x "${SVN}" ]; then
        svnroot=`LC_ALL=C ${SVN} info . 2>/dev/null | grep "Repository Root:"`
        svndomain=`echo "$svnroot" | cut -d/ -f3 | \
                   sed -E 's/[^.]+\.//'` 2>/dev/null
        case "${svndomain}" in
          ${SVNDOMAINS})
            TAG_RELEASE=1
            ;;
          *)
            ;;
        esac
    fi
fi

# Build the default setting help messages
if [ ${BUILD} = "RELEASE" ]; then
    DEBUG_ENABLED="(defaut: disabled)"
    RELEASE_ENABLED="(default: enabled)"
else
    DEBUG_ENABLED="(default: enabled)"
    RELEASE_ENABLED="(default: disabled)"
fi
if [ ${TAG_RELEASE} -gt 0 ]; then
    SYS_ENABLED="(default: enabled)"
else
    SYS_ENABLED="(reserved)"
fi

# Show usage information
usage()
{
    DEFPROJS=`echo ${PROJECTS} | tr ',' ' '`
    NAME=`basename $0`
    cat <<EOT
$NAME [options] [projects]

  Build up embedded application projects

    -h            Print this help message
    -B            Ignore any build.conf configuration file
    -c            Clean up any build directory
    -C            Clean up all, including Python binaries & leave (no build)
    -d            Build in DEBUG mode ${DEBUG_ENABLED}, overriding project conf
    -D            Build all projects in DEBUG mode
    -F            Force exact tool versions and build modes (for production)
    -j nbproc     Spwan nbproc parallel builds at once (speed up build)
    -k            Keep going, ignore errors
    -K            Skip build stage, only create project build files (CMake)
    -l [prj:]comp Limit doc generation to this component (may be repeated)
    -n            Do no build, only generate Make/Ninja files
    -M MiB        Use a RAM disk of MiB megabytes as build directory
    -r            Build in RELEASE mode ${RELEASE_ENABLED}, overriding project conf
    -s            Run static checking of source code
    -S            Run static checking of source code w/o building
    -t            Tag application w/ SVN revision ${SYS_ENABLED}
    -V            Bypass tool verification (ignore missing tools)
    -v            Verbose build mode
    -y [format]   Generate documentation (default: html) [html,pdf]
    -Y [format]   Generate documentation w/o building (default: html) [html,pdf]
    -x feature    Define an extra feature

    projects      List of space-separated projects to build
                  projects: project[ project...] with project: name[:(d|r)[gcp]]
                  If -D or -R option is specified, all default projects are
                    built, and the 'projects' list defines the build
                    customization for each specified project.
                  Suffixes:
                    :d force the project in DEBUG build
                    :r force the project in RELEASE build
                    :g force GCC toolchain
                    :c force Clang toolchain
                    :l force Clang toolchain, w/ GNU linker
                    :p force provider toolchain

  Default projects:
    $DEFPROJS

EOT
}

# Parse the command line and update configuration
while [ $# -ge 0 ]; do
    case "$1" in
      -h)
        usage
        exit 0
        ;;
      -r)
        BUILD="RELEASE"
        FORCEBLD=1
        ;;
      -R)
        BUILD="RELEASE"
        AUTO_PROJECTS=1
        ;;
      -d)
        BUILD="DEBUG"
        FORCEBLD=1
        ;;
      -D)
        BUILD="DEBUG"
        AUTO_PROJECTS=1
        ;;
      -t)
        TAG_RELEASE=1
        ;;
      -c)
        if [ ${CLEAN} -eq 1 ]; then
            echo '  >> -c should only be invoked once.' >&2
        fi
        CLEAN=1
        ;;
      -C)
        CLEAN=2
        ;;
      -f)
        echo '  >> -f is a deprecated option. Flash file are always built.' >&2
        ;;
      -F)
        FORCEVER=1
        FORCEBLD=1
        ;;
      -z)
        DEFLATE_APP=1
        ;;
      -y)
        GENDOC=1
        case "$2" in
          pdf|html)
            shift
            DOCFORMAT="$1"
            ;;
        esac
        ;;
      -Y)
        GENDOC=1
        SKIPBUILD=1
        case "$2" in
          pdf|html)
            shift
            DOCFORMAT="$1"
            ;;
        esac
        ;;
      -k)
        IGNORE_ERROR=1
        ;;
      -K)
        SKIPBUILD=1
        ;;
      -l)
        shift
        LCOMP=`echo "$1" | tr [:upper:] [:lower:]`
        DOCCOMPS="${DOCCOMPS} ${LCOMP}"
        ;;
      -j)
        shift
        JOBS=$1
        if [ -z "${JOBS}" -o "`echo ${JOBS} | cut -c1`" = "-" ]; then
            die "Missing argument for -j"
        fi
        ;;
      -j*)
        JOBS=`echo "$1" | cut -c3-`
        ;;
      -M)
        shift
        BUILD_RAMDISK_MSIZE=$1
        ;;
      -n)
        MAKE="true"
        ;;
      -V)
        VERIFY=0
        ;;
      -B)
        ;;
      -s)
        XSACHECK=2
        ;;
      -x)
        shift
        EXTRA_DEFS="${EXTRA_DEFS} $1"
        ;;
      -v)
        VERBOSE="VERBOSE=1"
        MAKEPRINTDIR="-w"
        ;;
      -*)
        usage
        die "Unsupported option: $1"
        ;;
      '')
        break
        ;;
      *)
        projdesc="$1"
        proj=`echo "$projdesc" | cut -d: -f1`
        if [ ! -d "$proj" ]; then
            usage
            die "Invalid project name: $proj"
        fi
        PROJECTDESC="${PROJECTDESC},${projdesc}"
        ;;
    esac
    shift
done

# Fill up default CMake options
for def in ${EXTRA_DEFS}; do
    CMAKEOPT="-D${def}=1 ${CMAKEOPT}"
done

if [ -n "$PROJECTDESC" ]; then
    # If one or more projects are specified, override the default list with
    # the specified list
    if [ ${AUTO_PROJECTS} -eq 0 ]; then
        PROJECTS=`echo "$PROJECTDESC" | sed 's/^,//'`
    else
        # If auto project mode is specified, rebuild the list of all default
        # projects with specified build option for each specified project
        AUTOPROJECTS=""
        for prj in `echo ${PROJECTS} | tr ',' ' '`; do
            for prjdesc in `echo ${PROJECTDESC} | tr ',' ' '`; do
                prjdname=`echo "$prjdesc" | cut -d: -f1`
                if [ "${prjdname}" = "${prj}" ]; then
                    prj=${prjdesc}
                    break
                fi
            done
            AUTOPROJECTS="${AUTOPROJECTS},${prj}"
        done
        PROJECTS=`echo "$AUTOPROJECTS" | sed 's/^,//'`
    fi
fi

# Update the CMake flags and SVN detection based on TAG_RELEASE option
if [ "${TAG_RELEASE}" -gt 0 ]; then
    CMAKEOPT="-DTAG_RELEASE=1 $CMAKEOPT"
fi

# Perform some build-dependent sanity checks
for prjdesc in `echo ${PROJECTS} | tr ',' ' '`; do
    prj=`echo ${prjdesc} | cut -d: -f1 | sed 's^/$^^'`
    build=`echo ${prjdesc} | cut -d: -f2 -s | tr [:lower:] [:upper:]`
    prjbuild="${BUILD}"
    for b in `echo "${build}" | sed 's/\(.\)/\1 /g'`; do
        case "${b}" in
            R)
                prjbuild="RELEASE"
                ;;
            D)
                prjbuild="DEBUG"
                ;;
            *)
                ;;
        esac
    done
done

# Wrapper to quit the build sequence on error
cond_leave() {
    if [ ${IGNORE_ERROR} -eq 0 ]; then
        die "Compilation failed"
    else
        echo "Resuming compilation of remaining modules"
    fi
}

version_number() {
   verstr="$1"
   vermajstr=`echo ${verstr} | cut -d. -f1`
   verminstr=`echo ${verstr} | cut -d. -f2`
   verplvstr=`echo ${verstr} | cut -d. -f3`
   vermajnum=`expr ${vermajstr:-0} \* 10000`
   verminnum=`expr ${verminstr:-0} \* 100`
   verplvnum="${verplvstr:-0}"
   vernum=`expr ${vermajnum} + ${verminnum} + ${verplvnum}`
   # echo "VN: ${verstr} -> ${vernum}" >&2
   echo "${vernum}"
}

# Sanity checks, verify that the required tools are available
check_host_tools() {
    check_all="$1"

    # Verify the directory from which the script is launched
    if [ ! -d "${TOPDIR}/host/bin" ]; then
        die "Please start the script for the top-level source directory"
    fi

    # Verify GNU make
    MAKE=`which make 2> /dev/null`
    if [ -n "${MAKE}" ]; then
      MAKEVER_STR=`${MAKE} --version 2>&1 | head -1 | sed s'/^[^0-9\.]*//'`
      if [ "${check_all}" -gt 0 -a "${FORCEVER}" -gt 0 ]; then
          if [ "${MAKEVER_STR}" != "${SYS_MAKE_VER}" ]; then
              die "Make tool mismatch: v${SYS_MAKE_VER} required," \
                   "v${MAKEVER_STR} installed"
          fi
      fi

      if [ -n "${VERBOSE}" ]; then
          echo "make:           ${MAKE} (v${MAKEVER_STR})"
      fi
    fi

    # Verify CMake
    CMAKE=${CMAKE:-`which cmake 2> /dev/null`}
    if [ -z "${CMAKE}" -o ! -x "${CMAKE}" ]; then
        die "Missing or invalid CMake tool"
    fi
    if [ -n "${USER_CMAKE_VER}" ]; then
        if [ "${check_all}" -gt 0 ]; then
            if [ -z "${VERBOSE}" ]; then
                echo "Warning: Using a custom CMake tool:"\
                     "${USER_CMAKE_VER}" >&2
            fi
        fi
        if [ ${FORCEVER} -gt 0 ]; then
            die "Version enforcement active, bailing out"
        fi
        SYS_CMAKE_VER="${USER_CMAKE_VER}"
    fi
    SYS_CMAKE_VN=$(version_number ${SYS_CMAKE_VER})

    if [ "${check_all}" -gt 0 ]; then
        CMAKE=`which cmake 2> /dev/null`
        if [ -z "${CMAKE}" -o ! -x "${CMAKE}" -o ! -f "${CMAKE}" ]; then
            die "Missing CMake tool " \
                 "v${SYS_CMAKE_MAJ}.${SYS_CMAKE_MIN}"
        fi
        CMAKEVER_STR=`${CMAKE} --version 2>&1 | head -1 | sed s'/^[^0-9\.]*//'`
        CMAKE_VN=$(version_number ${CMAKEVER_STR})
        if [ ${CMAKE_VN} -lt ${SYS_CMAKE_VN} ]; then
            die "CMake version ${SYS_CMAKE_VER} or above is required"
        fi
        if [ "${FORCEVER}" -gt 0 ]; then
            if [ ${CMAKE_VN} -ne ${SYS_CMAKE_VN} ]; then
                die "CMake mismatch: v${SYS_CMAKE_VER} required," \
                     "v${CMAKEVER_STR} installed"
            fi
        fi
    fi

    # CMake changes the rules once again and print out stupid warnings starting
    # from release 2.8.4
    CMK_CLIWARN=`${CMAKE} --help | grep "no-warn-unused-cli"` 2> /dev/null
    if [ -n "${VERBOSE}" ]; then
        echo "cmake:          ${CMAKE} (v${CMAKEVER_STR})"
    fi

    # Verify Ninja
    NINJA_SUPPORT=`${CMAKE} --help | grep Ninja`
    if [ -z "${NINJA_SUPPORT}" ]; then
        die "CMake is not built with support for Ninja build system"
    fi
    NINJA=`which ninja`
    if [ -z "${NINJA}" -o ! -x "${NINJA}" ]; then
        die "Missing or invalid Ninja tool"
    fi
    NINJAVER_STR=`${NINJA} --version`
    if [ -n "${USER_NINJA_VER}" ]; then
        if [ "${check_all}" -gt 0 ]; then
            if [ -z "${VERBOSE}" ]; then
                echo "Warning: Using a custom Ninja tool:"\
                     "${USER_NINJA_VER}" >&2
            fi
        fi
        if [ ${FORCEVER} -gt 0 ]; then
            die "Version enforcement active, bailing out"
        fi
        SYS_NINJA_VER="${USER_NINJA_VER}"
    fi
    SYS_NINJA_VN=$(version_number ${SYS_NINJA_VER})
    NINJA_VN=$(version_number ${NINJAVER_STR})
    if [ ${NINJA_VN} -lt ${SYS_NINJA_VN} ]; then
        die "Ninja mismatch: v${SYS_NINJA_VER} required,"\
             "v${NINJAVER_STR} installed"
    fi
    if [ "${FORCEVER}" -gt 0 ]; then
        if [ ${NINJA_VN} -ne ${SYS_NINJA_VN} ]; then
            die "Ninja mismatch: v${SYS_NINJA_VER} required,"\
                 "v${NINJAVER_STR} installed"
        fi
    fi
    if [ -n "${VERBOSE}" ]; then
        echo "ninja:          ${NINJA} (v${NINJAVER_STR})"
    fi
    NINJAJOBS=`${NINJA} --help 2>&1 | grep CPU | \
               sed 's/^.*=\([0-9]*\).*$/\1/g'`

    # Verify the Python interpreter
    SYS_PYTHON_VN=$(version_number ${SYS_PYTHON_VER})
    SYS_PY_MAJ=`echo ${SYS_PYTHON_VER} | cut -d. -f1`
    PYTHON=`which "python${SYS_PY_MAJ}" 2> /dev/null`
    if [ "${check_all}" -gt 0 ]; then
        if [ -z "${PYTHON}" ]; then
            die "Python v${SYS_PY_MAJ} is missing"
        fi
        PYTHONVSTR=`${PYTHON} -V 2>/dev/null | head -1 | cut -d'(' -f1`
        PYTHONVER_STR=`echo ${PYTHONVSTR} | sed 's/^.* //'`
        PYTHON_VN=$(version_number ${PYTHONVER_STR})
        if [ ${PYTHON_VN} -lt ${SYS_PYTHON_VN} ]; then
            die "Python mismatch: v${SYS_PYTHON_VER} required,"\
                 "v${PYTHONVER_STR} installed"
        fi
        if [ "${FORCEVER}" -gt 0 ]; then
            if [ ${PYTHON_VN} -ne ${SYS_PYTHON_VN} ]; then
                die "Python mismatch: v${SYS_PYTHON_VER} required,"\
                     "v${PYTHONVER_STR} installed"
            fi
        fi
    fi
    if [ -n "${VERBOSE}" ]; then
        echo "python:         ${PYTHON} (v${PYTHONVER_STR})"
    fi

    # Documentation generation tools
    if [ ${GENDOC} -gt 0 ]; then
        # Verify Doxygen
        DOXYGEN=`which doxygen 2> /dev/null`
        if [ -z "${DOXYGEN}" ]; then
            die "Missing or invalid Doxygen tool"
        fi
        DOXYGENVER_STR=`${DOXYGEN} --version 2>&1 | head -1`
        DXYVER_MAJ=`echo ${DOXYGENVER_STR} | cut -d. -f1`
        DXYVER_MIN=`echo ${DOXYGENVER_STR} | cut -d. -f2`
        SYS_DXY_MAJ=`echo ${SYS_DOXYGEN_VER} | cut -d. -f1`
        SYS_DXY_MIN=`echo ${SYS_DOXYGEN_VER} | cut -d. -f2`
        if [ ${DXYVER_MAJ} -lt ${SYS_DXY_MAJ} -o \
             ${DXYVER_MIN} -lt ${SYS_DXY_MIN} ]; then
            die "Doxygen version too old: ${DOXYGENVER_STR},"\
                 "${SYS_DXY_MAJ}.${SYS_DXY_MIN}+ required"
        fi
        if [ -n "${VERBOSE}" ]; then
            echo "doxygen:        ${DOXYGEN} (v${DOXYGENVER_STR})"
        fi

        # Verify Sphinx
        SPHINX=`which sphinx-build 2> /dev/null`
        if [ -z "${SPHINX}" ]; then
            die "Missing or invalid Sphinx tool"
        fi
        (${SPHINX} --version >/dev/null 2>&1) || \
            die "Invalid Sphinx installation"
        SPHINXVER_STR=`${SPHINX} --version 2>&1 | head -1 | \
                       sed 's/\([^0-9\.]\)//g'`
        SPHXVER_MAJ=`echo ${SPHINXVER_STR} | cut -d. -f1`
        SPHXVER_MIN=`echo ${SPHINXVER_STR} | cut -d. -f2`
        SYS_SPHINX_MAJ=`echo ${SYS_SPHINX_VER} | cut -d. -f1`
        SYS_SPHINX_MIN=`echo ${SYS_SPHINX_VER} | cut -d. -f2`
        if [ ${SPHXVER_MAJ} -lt ${SYS_SPHINX_MAJ} -o \
             ${SPHXVER_MIN} -lt ${SYS_SPHINX_MIN} ]; then
            die "Sphinx version too old: ${SPHINXVER_STR},"\
                 "${SYS_SPHINX_MAJ}.${SYS_SPHINX_MIN}+ required"
        fi
        if [ -n "${VERBOSE}" ]; then
            echo "sphinx:         ${SPHINX} (v${SPHINXVER_STR})"
        fi
    fi
}

check_cross_gcc() {
    xtoolchain="$1"
    check_all="$2"

    # Verify GNU C compiler
    if [ -n "${USER_XTCCC_VER}" ]; then
        if [ "${check_all}" -gt 0 ]; then
            if [ -z "${VERBOSE}" ]; then
                echo "Warning: Using a custom GCC compiler:"\
                     "${USER_XTCCC_VER}" >&2
            fi
        fi
        if [ ${FORCEVER} -gt 0 ]; then
            die "Version enforcement active, bailing out"
        fi
        SYS_XTCCC_VER="${USER_XTCCC_VER}"
    fi
    XGCC=`which ${xtoolchain}-gcc-${SYS_XTCCC_VER} 2> /dev/null`
    if [ -z "${XGCC}" ]; then
        XGCC=`which ${xtoolchain}-gcc 2> /dev/null`
        if [ -z "${XGCC}" ]; then
            echo "Missing or invalid GNU C compiler for ${xtoolchain}" >&2
        else
            XGCCVER_STR=`${XGCC} --version 2>&1 | head -1 | \
                     sed 's/^.*[^0-9\.+]//'`
            echo "GNU C/C++ compiler mismatch:" \
                 "v${SYS_XTCCC_VER} required, v${XGCCVER_STR} installed" >&2
        fi
        exit 1
    else
        XGCCVER_STR=`${XGCC} --version 2>&1 | head -1 | \
                 sed s'/^[^0-9\.]*//' | cut -d' ' -f1`
    fi
    XGCCVER=`${XGCC} --version | head -1 | \
             sed 's/^.* \([0-9]\)\.\([0-9]\)\.[0-9].*$/\1\2/g'`
    if [ "${XGCCVER}" -lt 61 ]; then
        die "GCC for ${xtoolchain} too old, version 6.1 or above is required"
    fi
    if [ "${check_all}" -gt 0 ]; then
        # Verify the binutils suite
        if [ -n "${USER_XTCBU_VER}" ]; then
            if [ -z "${VERBOSE}" ]; then
                echo "Warning: Using custom GNU Binutils:"\
                     "${USER_XTCBU_VER}" >&2
            fi
            if [ ${FORCEVER} -gt 0 ]; then
                die "Version enforcement active, bailing out"
            fi
            SYS_XTCBU_VER="${USER_XTCBU_VER}"
        fi
        XTCAS=`${xtoolchain}-gcc-${SYS_XTCCC_VER} -v --help 2>&1 | \
               grep -i '/as' | head -1 | sed s'/^ //' | cut -d' ' -f1`
        if [ -z "${XTCAS}" ]; then
            die "Missing or invalid GNU assembler for ${xtoolchain}"
        fi
        # workaround to get the normalized XTC assembly path
        XTCASDIR=`dirname "${XTCAS}"`
        XTCASBASE=`basename "${XTCAS}"`
        XTCASDIR=`(cd "${XTCASDIR}" && pwd)`
        XTCAS="${XTCASDIR}/${XTCASBASE}"
        XTCASVER_STR=`${XTCAS} --version | head -1 |  sed s'/^[^0-9\.]*//'`
        if [ "${FORCEVER}" -gt 0 ]; then
            if [ "${XTCASVER_STR}" != "${SYS_XTCBU_VER}" ]; then
                die "GNU assembler mismatch: v${SYS_XTCBU_VER} required," \
                     "v${XTCASVER_STR} installed"
            fi
        fi
        XTCLD=`which ${xtoolchain}-ld 2> /dev/null`
        if [ -z "${XTCLD}" ]; then
            echo "Missing GNU linker for XTC"
        fi
        XTCLDVER_STR=`${XTCLD} --version | head -1 |  sed s'/^[^0-9\.]*//'`
        if [ "${FORCEVER}" -gt 0 ]; then
            if [ "${XTCLDVER_STR}" != "${SYS_XTCBU_VER}" ]; then
                die "GNU linker mismatch: v${SYS_XTCBU_VER} required," \
                     "v${XTCLDVER_STR} installed"
            fi
        fi
        if [ -n "${VERBOSE}" ]; then
            echo "xgcc:           ${XGCC} (v${XGCCVER_STR})"
            echo "xas:            ${XTCAS} (v${XTCASVER_STR})"
            echo "xld:            ${XTCLD} (v${XTCLDVER_STR})"
        fi
    else
        if [ -n "${VERBOSE}" ]; then
            echo "xgcc:           ${XGCC}"
        fi
    fi
}

check_cross_clang() {
    xtoolchain="$1"
    check_all="$2"

    # Verify Clang compiler
    if [ -n "${USER_XTCCL_VER}" ]; then
        echo "Warning: Using a custom clang toolchain: "\
             "${USER_XTCCL_VER}" >&2
        if [ ${FORCEVER} -gt 0 ]; then
            die "Version enforcement active, bailing out"
        fi
        SYS_XTCCL_VER="${USER_XTCCL_VER}"
    fi
    CLANG=`which clang 2> /dev/null`
    if [ -z "${CLANG}" ]; then
        die "Clang compiler not found"
    fi
    if [ "${check_all}" -gt 0 ]; then
        CLANG_STR=`${CLANG} --version 2>&1 | head -1`
        CLANG_NAME=`echo ${CLANG_STR} | cut -d' ' -f1`
        if [ "${CLANG_NAME}" != "clang" ]; then
            # likely Apple clang getting in the way
            die "Clang binary is not a pristine compiler: ${CLANG_NAME}"
        fi
        CLANGVER_STR=`echo ${CLANG_STR} | \
                      sed 's/^.* version \([0-9]\.[0-9]\).*$/\1/g'`
        SYS_CLANG_VN=$(version_number ${SYS_XTCCL_VER})
        CLANG_VN=$(version_number ${CLANGVER_STR})
        if [ ${CLANG_VN} -lt ${SYS_CLANG_VN} ]; then
            die "Clang compiler mismatch: v${SYS_XTCCL_VER} required,"\
                 "v${CLANGVER_STR} installed"
        fi
        if [ "${CLANG_VN}" -lt 50000 ]; then
            die "Clang too old, version 5.0 or above is required"
        fi
    fi

    XCC="${CLANG}"

    # Verify C toolchain
    if [ "${check_all}" -gt 0 ]; then
        # Verify the binutils suite
        if [ -n "${USER_XTCBU_VER}" ]; then
            echo "Warning: Using custom GNU Binutils: "\
                 "${USER_XTCBU_VER}" >&2
            if [ ${FORCEVER} -gt 0 ]; then
                die "Version enforcement active, bailing out"
            fi
            SYS_XTCBU_VER="${USER_XTCBU_VER}"
        fi
        XTCLD=`which ld.lld 2> /dev/null`
        if [ -z "${XTCLD}" ]; then
            die "Missing GNU linker for ${xtoolchain}"
        fi
        XTCLDVER_STR=`${XTCLD} --version | head -1 | sed s'/^[^0-9\.]*//' |\
                        cut -d'(' -f1 | tr -d [:space:]`
        if [ "${FORCEVER}" -gt 0 ]; then
            SYS_LD_VN=$(version_number ${SYS_XTCCL_VER})
            LD_VN=$(version_number ${XTCLDVER_STR})
            if [ ${CLANG_VN} -lt ${SYS_CLANG_VN} ]; then
                die "GNU linker mismatch: v${SYS_XTCBU_VER} required," \
                     "v${XTCLDVER_STR} installed"
            fi
        fi
        if [ -n "${VERBOSE}" ]; then
            echo "clang:          ${CLANG} (v${CLANGVER_STR})"
            echo "xld:            ${XTCLD} (v${XTCLDVER_STR})"
        fi
        XTCLD_PATH=`dirname ${XTCLD}`
        XTCBU_PATH="${XTCLD_PATH}"
    else
        if [ -n "${VERBOSE}" ]; then
            echo "clang:          ${CLANG}"
        fi
    fi

    # Verify sanity checker
    if [ ${XSACHECK} -gt 0 ]; then
        XTCTIDY=`which clang-tidy` 2> /dev/null
        if [ -z "${XTCTIDY}" ]; then
            die "clang-tidy not found"
        fi
    fi
}

check_cross_tools() {
    xtoolchain="$1"
    xtool="$2"
    check_all="$3"

    if [ "${xtool}" = "gcc" ]; then
        check_cross_gcc ${xtoolchain} ${check_all}
    elif [ "${xtool}" = "clang" ]; then
        check_cross_clang ${xtoolchain} ${check_all}
    else
        die "Unsupported toolchain ${xtoolchain}-${xtool}"
    fi
}

get_toolchain() {
    target="$1"
    case "${target}" in
        host)
            XTOOLCHAIN=""
            ;;
        msp430g2553)
            XTOOLCHAIN="msp430-elf"
            ;;
        cortex-a8)
            XTOOLCHAIN="arm32v7-linux"
            ;;
        cortex-m0plus)
            XTOOLCHAIN="armv6m"
            ;;
        cortex-m4|cortex-m4f)
            XTOOLCHAIN="armv7em"
            ;;
        *)
            die "Unsupported target ${target}"
            ;;
    esac
}

# Verify the availability of the selected projects
for prjdesc in `echo ${PROJECTS} | tr ',' ' '`; do
    prj=`echo ${prjdesc} | cut -d: -f1`
    if [ ! -d "${TOPDIR}/${prj}" ]; then
        echo "Project \"${prj}\" does not exist"
        exit 1
    fi
done

check_host_tools "${VERIFY}"

# Check -j parameter
if [ -n "${JOBS}" ]; then
    if [ "${JOBS}" -lt 1 ]; then
        die "Invalid number of parallel processes"
    fi
fi

# Default make option switch
if [ -n "${JOBS}" ]; then
    MAKEOPTS="-j ${JOBS}"
    DOCJOBS="${JOBS}"
else
    if [ -n "${NINJAJOBS}" ]; then
        # use the optimal ninja job value for Make, if make is used
        MAKEOPTS="-j ${NINJAJOBS}"
    else
        MAKEOPTS="${JOBS}"
    fi
    DOCJOBS=1
fi

# Add the target definitions
CMAKEOPT="${CMAKEOPT} -G Ninja -DPYTHON=${PYTHON}"

# Export Python version for Python script usage
export SYSPYVER="${SYS_PY_MAJ}.${SYS_PY_MIN}"

# Doc generation specifics
if [ ${GENDOC} -gt 0 ]; then
    if [ ${SKIPBUILD} -gt 0 ]; then
        CMAKEOPT="${CMAKEOPT} -DDOC_ONLY=1"
    fi
    if [ ${DOCCHECK} -gt 0 ]; then
        CMAKEOPT="${CMAKEOPT} -DDOC_WARN=1"
    fi
    CMAKEOPT="${CMAKEOPT} -DDOC_JOBS=${DOCJOBS} -DDOC_FORMAT=${DOCFORMAT}"
fi

# Clean up project build directories if requested
if [ ${CLEAN} -gt 0 ]; then
    if [ -d ./build ]; then
        for prjdesc in `echo ${PROJECTS} | tr ',' ' '`; do
            prj=`echo ${prjdesc} | cut -d: -f1 | sed 's^/$^^'`
            if [ -d build/${prj} ]; then
                if [ -f build/${prj}/Makefile ]; then
                    echo "Invoking clean target for project ${prj}"
                    (cd build/${prj} && make clean) 2> /dev/null
                fi
                if [ -f build/${prj}/build.ninja ]; then
                    echo "Invoking clean target for project ${prj}"
                    (cd build/${prj} && ninja -t clean) 2> /dev/null
                fi
            fi
            echo "Removing the build directory for project ${prj}"
            rm -rf ./build/${prj}
        done
    fi
    if [ -d ./host/bin/dist ]; then
        echo "Removing Python distribution directory"
        rm -rf ./host/bin/dist
    fi
    if [ -d ./build/doc ]; then
        echo "Removing generated documentation tree"
        rm -rf ./build/doc
    fi
fi

# Perform full clean up only (then leave)
if [ ${CLEAN} -gt 1 ]; then
    echo "Removing the build top-level directory"
    rm -rf ./build
    echo "Removing Python compiled modules"
    for prjdesc in `echo host,${PROJECTS} | tr ',' ' '`; do
        prj=`echo ${prjdesc} | cut -d: -f1 | sed 's^/$^^'`
        find "${prj}" -not -path "*.svn*" -name "*.py?" -exec rm -f {} \;
    done
    exit 0
fi

HOSTSYS=`uname -s`

# a previous RAMdisk-based build may have left a build symlink to a no-longer
# existing build directory
if [ -L ${PWD}/build ]; then
    if [ ! -e ${PWD}/build ]; then
        echo "Warning: Removing invalid build symlink dir" >&2
        rm -f ${PWD}/build
    fi
fi

if [ ${BUILD_RAMDISK_MSIZE} -gt 0 ]; then
    sbname=$(basename ${PWD})
    case ${HOSTSYS} in
        Darwin)
            RAMDISK_VOL="/Volumes/buildram"
            RAMDISK_SIZE=$(expr ${BUILD_RAMDISK_MSIZE} \* 2048)
            if [ -d ${RAMDISK_VOL} ]; then
                CUR_SIZE=$(df ${RAMDISK_VOL} | tail -n +2 | awk '{print $2;}')
                if [ ${CUR_SIZE} -ne ${RAMDISK_SIZE} ]; then
                    echo "Removing RAMdisk as size has been updated"
                    hdiutil detach ${RAMDISK_VOL} 2>&1 >/dev/null \
                        || die "Cannot change RAMdisk"
                fi
            fi
            if [ ! -d ${RAMDISK_VOL} ]; then
                echo "Creating a RAM disk of ${BUILD_RAMDISK_MSIZE} MiB"
                ramdisk=$(hdiutil attach -nomount ram://${RAMDISK_SIZE}) || \
                    die "Cannot create RAMdisk"
                diskutil erasevolume HFS+ 'buildram' ${ramdisk} || \
                    die "Cannot mount RAMdisk"
            fi
            mkdir -p ${RAMDISK_VOL}/${sbname}
            if [ ! -L ${PWD}/build ]; then
                if [ -d  ${PWD}/build ]; then
                    if [ ${CLEAN} -gt 0 ]; then
                        rm -rf ${PWD}/build
                    else
                        die "Build directory already exists, not a RAMdisk"
                    fi
                fi
                ln -s ${RAMDISK_VOL}/${sbname} ${PWD}/build || \
                    die "Cannot use RAMdisk"  # existing dir?
            fi
            ;;
        *)
            die "RAMdisk not yet supported on ${HOSTSYS}"
            ;;
    esac
else
    mkdir -p build
fi

# Create an environment file
cat > build/.environ <<EOT
# Building environment
PATH="${PATH}"
USER_PYTHON_VER="${USER_PYTHON_VER=}"
USER_CMAKE_VER="${USER_CMAKE_VER=}"
USER_XTCCC_VER="${USER_XTCCC_VER=}"
USER_XTCBU_VER="${USER_XTCBU_VER=}"
USER_XTCCL_VER="${USER_XTCCL_VER=}"
USER_MAKE_VER="${USER_MAKE_VER=}"
USER_NINJA_VER="${USER_NINJA_VER=}"
USER_DOXYGEN_VER="${USER_DOXYGEN_VER=}"
USER_SPHINX_VER="${USER_SPHINX_VER=}"
EOT

# Build a project
WARNCOUNT=0
for prjdesc in `echo ${PROJECTS} | tr ',' ' '`; do
    prj=`echo ${prjdesc} | cut -d: -f1 | sed 's^/$^^'`
    prj=`echo "${prj}" | sed s^/$^^`
    uprj=`echo "${prj}" | tr [:lower:] [:upper:]`
    # 1. use the global build mode
    PRJBUILD="${BUILD}"
    if [ ${FORCEBLD} -eq 0 ]; then
        # 2. check if there is a special build mode for the current project
        #    from the project configuration file
        build_name="BUILD_${uprj}"
        #   dash workaround as ${!...} indirect substitution is a bashism
        build_var=$(eval echo \$$build_name)
        build_var=`echo "${build_var}" | tr [:lower:] [:upper:]`
        if [ -n "${build_var}" ]; then
            case "${build_var}" in
                DEBUG|RELEASE)
                    PRJBUILD="${build_var}"
                    ;;
                *)
                    die "Invalid build mode for ${prj}: ${build_var}"
                    ;;
            esac
        fi
    fi
    srcprj=`(cd ${prj} && pwd)`
    if [ ! -r "${srcprj}/build.conf" ]; then
        die "Project '${prj}' has no configuration file"
    fi
    # Be sure to reset all project-specific variables
    TARGET=""
    XTOOL="gcc"
    XTOOLCHAIN=""
    XLD=""
    # 2. Get target information
    . "${srcprj}/build.conf"
    if [ -z "{TARGET}" ]; then
        die "Project '${prj}' target unknown"
    fi
    TARGET=`echo "${TARGET}" | tr [:upper:] [:lower:]`
    echo "${TARGET}" | grep -E "${TARGETS}" > /dev/null
    if [ $? -ne 0 ]; then
        targets=`echo ${TARGETS} | tr '|' ','`
        die "Invalid target \"${TARGET}\", should be one of ${targets}"
    fi
    # 3. check if the selected build mode has been specifically
    #    overriden with a project command line specifier
    build=`echo ${prjdesc} | cut -d: -f2 -s | tr [:lower:] [:upper:]`
    for b in `echo "${build}" | sed 's/\(.\)/\1 /g'`; do
        case "${b}" in
            R)
                PRJBUILD="RELEASE"
                ;;
            D)
                PRJBUILD="DEBUG"
                ;;
            G)
                XTOOL="gcc"
                ;;
            C)
                XTOOL="clang"
                ;;
            L)
                XTOOL="clang"
                XLD="gcc"
                ;;
            P)
                XTOOL="provider"
                ;;
            *)
                ;;
        esac
    done
    # 4. Obtain and verify toolchain
    get_toolchain ${TARGET}
    if [ -n "${XTOOLCHAIN}" ]; then
        # Do not perform verification of cross toolchains that have been
        # previously verified
        check_cross_name=`echo "XT_${TARGET}" | sed 's/\-/_/'`
        check_cross_var=$(eval echo \$$check_cross_name)
        if [ "x${check_cross_var}" = "x" ]; then
            if [ "${XTOOL}" = "provider" ]; then
                die "Unknown toolchain provider for project '${prj}'"
            fi
            check_cross_tools "${XTOOLCHAIN}" "${XTOOL}" "${VERIFY}"
            eval ${check_cross_name}=1
        fi
        XCC_BIN=`dirname "${XCC}"`
        XCC_ROOT=`dirname "${XCC_BIN}"`
        if [ "${HOSTSYS}" = "Darwin" ]; then
            # with homebrew, sysroot is not located within the compiler tree
            XCC_TOP=`dirname "${XCC_ROOT}"`
            if [ "${XCC_TOP}" = "/" -o ! -d "${XCC_TOP}" ]; then
                die "Invalid compiler path: ${XCC}"
            fi
            XSYSROOT="${XCC_TOP}/${XTOOLCHAIN}-${TARGET}"
        else
            # Compute sysroot from compiler installation
            XSYSROOT=`echo ${XCC_ROOT} | sed 's%/.+/%%'`
        fi
        CMAKEPRJOPT="${CMAKEOPT} -DTARGET=${TARGET}"
        CMAKEPRJOPT="${CMAKEPRJOPT} -DXTOOLCHAIN=${XTOOLCHAIN}"
        CMAKEPRJOPT="${CMAKEPRJOPT} -DXCC_VER=${SYS_XTCCC_VER}"
        CMAKEPRJOPT="${CMAKEPRJOPT} -DXSYSROOT=${XSYSROOT}"
        if [ -n "${XLD}" ]; then
            CMAKEPRJOPT="${CMAKEPRJOPT} -DXLD=${XLD}"
        fi
        if [ -n "${VERBOSE}" ]; then
            CMAKEPRJOPT="${CMAKEPRJOPT} -DXCC_VERBOSE=1"
        fi
    else
        CMAKEPRJOPT="${CMAKEOPT}"
    fi
    # 5. Build the project
    echo ""
    mkdir -p build/${prj}
    BUILD_CMD="${NINJA} ${MAKEOPTS}"
    if [ -n "${VERBOSE}" ]; then
        BUILD_CMD="${BUILD_CMD} -v"
    fi
    if [ ${IGNORE_ERROR} -gt 0 ]; then
        # do not stop on error (at least, wait for a lot of them)
        BUILD_CMD="${BUILD_CMD} -k 99"
    fi
    (cd build/${prj} && \
        echo "Configuring ${prj} in ${PRJBUILD}";
        if [ -n "${DOCCOMPS}" ]; then
            DOCIT=""
            for comp in ${DOCCOMPS}; do
                compprj=`echo ${comp} | cut -d: -f1`
                if [ "${compprj}" != "${comp}" ]; then
                    if [ "${compprj}" != "${prj}" ]; then
                        continue
                    fi
                    comp=`echo ${comp} | cut -d: -f2`
                fi
                if [ -z "${DOCIT}" ]; then
                    DOCIT="${comp}"
                else
                    DOCIT="${DOCIT}:${comp}"
                fi
            done
            CMAKEDOC="-DDOCUMENT_COMPONENTS=${DOCIT}"
        else
            CMAKEDOC=""
        fi
        if [ "${TARGET}" != "host" ]; then
            CMAKE_XTOOLCHAIN="${TARGET}-${XTOOL}"
        else
            CMAKE_XTOOLCHAIN="${XTOOL}"
        fi
        if [ ${XSACHECK} -gt 0 ]; then
            if [ "${XTOOL}" != "clang" ]; then
                die "Cannot run static analysis on project ${prj}"
            else
                CMAKEPRJOPT="${CMAKEPRJOPT} -DXTCHECK=1"
            fi
        fi
        CL="${CMAKE} \
            -DCMAKE_MODULE_PATH=${TOPDIR}/host/etc/cmake \
            -DCMAKE_TOOLCHAIN_FILE=${TOPDIR}/host/etc/cmake/${CMAKE_XTOOLCHAIN}.cmake \
            -DCMAKE_BUILD_TYPE="${PRJBUILD}" \
            -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
            ${CMAKEDOC} \
            ${CMAKEPRJOPT} \
            ${srcprj}"
        rm -rf logs && mkdir -p logs && \
        ([ -n "${VERBOSE}" ] && echo ${CL}; true) && \
        ${CL}) || cond_leave
        if [ ${SKIPBUILD} -eq 0 ]; then
            echo "Building ${prj} in ${PRJBUILD}"
            (cd build/${prj} && \
                ${BUILD_CMD} all && \
                ${BUILD_CMD} generate && \
                ${BUILD_CMD} finalize) || cond_leave
        fi
        if [ ${GENDOC} -gt 0 ]; then
            echo "Documenting ${prj}"
            (cd build/${prj} && \
                ${BUILD_CMD} document) || cond_leave
        fi
    done
