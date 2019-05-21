#!/bin/sh

# Generate GIT information as constant C definitions

DSTFILE="$1"
if [ -z "${DSTFILE}" ]; then
    echo "Missing output file argument"
    exit -1;
fi

COMPNAME="$2"
if [ -z "${COMPNAME}" ]; then
    echo "Missing component argument"
    exit -1;
fi
COMPNAME=$(echo "${COMPNAME}" | tr '-' '_')

REVDIR="$3"
if [ -z "${REVDIR}" ]; then
    REVDIR="${PWD}"
fi

VERSION="$4"
COMP_MAJOR=`echo "${VERSION}" | cut -d. -f1`
COMP_MINOR=`echo "${VERSION}" | cut -d. -f2`
COMP_PATCH=`echo "${VERSION}" | cut -d. -f3`
if [ -z "${COMP_MAJOR}" ]; then COMP_MAJOR="0"; fi
if [ -z "${COMP_MINOR}" ]; then COMP_MINOR="0"; fi
if [ -z "${COMP_PATCH}" ]; then COMP_PATCH="0"; fi

BUILDTYPE="${5:-U}"

DSTDIR=`dirname ${DSTFILE}`
if [ ! -d "${DSTDIR}" ]; then
    echo "Invalid destination location ${DSTFILE} ${DSTDIR}"
    exit -1
fi

# be sure to use non-localized strings
export LC_ALL=C

GIT=$(which git 2> /dev/null)
if [ $? -ne 0 ]; then
    echo "Error: Missing required git tool; incomplete GIT installation"
    exit 1
fi

# Get version and status
GITHASH=$(git log -n 1 --pretty=format:"%h" -- ${REVDIR})
GITVER=$(${GIT} describe ${GITHASH})
${GIT} status -s | grep -q '^ M'
if [ $? -eq 0 ]; then
    GITVER="${GITVER}-M"
fi

GITBRANCH=`git branch -q | cut -d' ' -f2`

# Get the current date as a second count since the Epoch (UTC)
BUILDDATE=`date -u "+%s"`
export TZ='UTC'
BUILDDATE_INFO=`date -u`

echo "Build: ${COMPNAME} ${GITVER} from ${GITBRANCH}"

EXTENSION=`echo "${DSTFILE}" | sed 's/^.*\.\(.*\)/\1/g'`
UCOMPNAME=`echo "${COMPNAME}" | tr [:lower:] [:upper:]`

if [ "${EXTENSION}" = "h" ]; then cat > ${DSTFILE} <<EOT

/**
 * This file has been automatically generated,
 * DO NOT EDIT IT, your changes would be overwritten
 */

/** Development version mask */
#ifdef __GNUC__
#pragma GCC diagnostic ignored "-Wunused-macros"
#endif // __GNUC__

#define ${UCOMPNAME}_GITVER "${GITVER}"

extern const char * git_${COMPNAME}_build_path(void);
extern const char * git_${COMPNAME}_build_version(void);
extern unsigned long git_${COMPNAME}_build_date(void);

EOT
else cat > ${DSTFILE} <<EOT

/**
 * This file has been automatically generated,
 * DO NOT EDIT IT, your changes would be overwritten
 */

#include <stdint.h>

/** Development version mask */
#ifdef __GNUC__
#pragma GCC diagnostic ignored "-Wunused-macros"
#endif // __GNUC__

const char * git_${COMPNAME}_build_path(void);
const char * git_${COMPNAME}_build_version(void);
unsigned long git_${COMPNAME}_build_date(void);

/**
 * Returns the component relative path as a string
 * @return the component path
 */
const char * git_${COMPNAME}_build_path(void)
{
    static const char _git_build_path[]="${GITBRANCH}";
    return _git_build_path;
}

/**
 * Returns the component build number as an unsigned integer
 * @return the component version
 */
const char * git_${COMPNAME}_build_version(void)
{
    static const char _git_build_version[]="${GITVER}";
    return _git_build_version;
}

/**
 * Returns the component build date as a second count since the Epoch UTC.
 * Build date: ${BUILDDATE_INFO}
 * @return the build date/time as a second count
 */
unsigned long git_${COMPNAME}_build_date(void)
{
    return (${BUILDDATE}U);
}

EOT
fi
