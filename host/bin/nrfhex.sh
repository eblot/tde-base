#!/bin/sh

# Create a versioned Intel HEX application file
# This is a simple wrapper script as once again, CMake instruction set
# is far too limited

# Die with an error message
die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

# Show usage information
usage()
{
    NAME=`basename $0`
    cat <<EOT
$NAME <args>

  Generate a nRF52 flashable fle

    -h            Print this help message
    -s dir        Path to SoftDevice hex directory
    -e file       Path to the nRF52 application ELF file
    -o dir        Path to the output directory
EOT
}

SDDIR=""
OUTDIR=`pwd`
ELFFILE=""
PREFIX="arm-none-eabi-"

# Parse the command line and update configuration
while [ $# -ge 0 ]; do
    case "$1" in
      -h)
        usage
        exit 0
        ;;
      -s)
        shift
        SDDIR=$1
        ;;
      -o)
        shift
        OUTDIR=$1
        ;;
      -e)
        shift
        ELFFILE=$1
        ;;
      -*)
        usage
        die "Unsupported option: $1"
        ;;
      '')
        break
        ;;
    esac
    shift
done

# use strings to extract the exact version name from the ELF binary
STRINGS=`which ${PREFIX}strings 2> /dev/null`
# use objcopy to build an IHEX file from the ELF binary
# (as SoftDevice is only delivered as an IHEX file, merge cannot be done at
#  ELF level)
OBJCOPY=`which ${PREFIX}objcopy 2> /dev/null`
MERGEHEX="$(dirname $0)/mergehex.py"

if [ -z "${STRINGS}" ]; then
    die "Unable to locate strings tool"
fi
if [ -z "${OBJCOPY}" ]; then
    die "Unable to locate strings tool"
fi
if [ -z "${ELFFILE}" ]; then
    die "ELF file not specified"
fi
if [ -z "${SDDIR}" ]; then
    die "SoftDevice directory not specified"
fi
if [ ! -s "${ELFFILE}" ]; then
    die "Invalid ELF file: ${ELFFILE}"
fi
if [ ! -d "${SDDIR}" ]; then
    die "Invalid SoftDevice directory: ${SDDIR}"
fi
if [ ! -d "${OUTDIR}" ]; then
    die "Invalid output directory: ${OUTDIR}"
fi

SDHEX=`ls -1 ${SDDIR}/hex/*.hex 2> /dev/null | tail -1`
if [ -z "${SDHEX}" ]; then
    die "Unable to find SoftDevice file"
fi

# extract base components from ELF file
APPRADIX=$(basename ${ELFFILE%.*})
APPDIR=$(dirname ${ELFFILE})
# search and extract the SVN version string embedded within the ELF file
SWVER=$(${STRINGS} ${ELFFILE} | grep -F _swver_ | head -1 | cut -d_ -f3)
# extract the Soft Device version from its file name
# SDHEX Filename example: hex/s132_nrf52_5.1.0_softdevice.hex
FWVER=$(echo $(basename "${SDHEX}") | cut -d_ -f3)
OUTHEX="${OUTDIR}/${APPRADIX}_sd${FWVER}_v${SWVER}.hex"
# build application IHEX file
rm -f "${APPDIR}/${APPRADIX}.hex"
${OBJCOPY} -O ihex ${ELFFILE} ${APPDIR}/${APPRADIX}.hex || \
    die "Cannot convert to IHEX"
# merge both IHEX file
rm -f "${OUTHEX}"
${MERGEHEX} -x -r -i ${APPDIR}/${APPRADIX}.hex -i ${SDHEX} -o ${OUTHEX} || \
    die "Cannot merge IHEX files"
# (re-)generate a symlink name to ease openocd-based flash script
rm -f "${OUTDIR}/${APPRADIX}_flash.hex"
(cd "${OUTDIR}" && ln -s $(basename "${OUTHEX}") "${APPRADIX}_flash.hex")
