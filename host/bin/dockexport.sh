#!/bin/sh

if [ $# -ne 2 ]; then
   echo "Usage: `basename $0` <out> <project>" >&2
   exit 1
fi

DEST="$1"
PROJECT=`echo "$2" | sed s^/$^^`

if [ -z "${PROJECT}" ]; then
   echo "Project not specified" >&2
   exit 1
fi

if [ ! -f "${PROJECT}/CMakeLists.txt" ]; then
   echo "Invalid CMake Project" >&2
   exit 1
fi

if [ ! -d ${DEST} ]; then
   mkdir -p ${DEST}
fi

SVNREV=`svn info --show-item last-changed-revision ${PROJECT} | tr -d [:space:]`
for src in `find build/${PROJECT} -name "*.elf" -o -name "*.srec"`; do
   name=`basename ${src} | sed 's/\.[^.]*$//'`
   ext=`echo "${src}" |  sed 's/^.*\.//'`
   dst="${DEST}/${PROJECT}-${name}_r${SVNREV}.${ext}"
   cp "${src}" "${dst}"
   echo "Generated file: ${dst}"
done
