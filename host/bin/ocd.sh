#!/bin/sh

CURDIR=`dirname $0`
HOST_DIR="host/etc/openocd"

# Show usage information
usage()
{
    NAME=`basename $0`
    cat <<EOT
$NAME [options] <script>

  Flash/Debug Cortex-M target with OpenOCD and SWD interface

    -h       Print this help message
    -j       Use J-Link SWD bridge device
    -f       Use FTDI SWD bridge device
    -s SN    Define a serial number to select a specific SWD device
    -g       Do not flash but enter GDB server mode
    -dN      Set a debug level for OpenOCD

    script   OpenOCD config file
EOT
}

ARGS=""
OPENOCD_SN=""
OPENOCD_DEVICE=0
OPENOCD_DOCKER=0
OPENOCD_SCRIPT=""
OPENOCD_DEBUG=""
GDB=0
while [ $# -gt 0 ]; do
    case $1 in
        -h)
            usage
            exit 0
            ;;
        -D)
            OPENOCD_DOCKER=1
            ;;
        -j)
            OPENOCD_DEVICE=2
            ;;
        -f)
            OPENOCD_DEVICE=1
            ;;
        -s)
            shift
            OPENOCD_SN="$1"
            ;;
        -d*)
            OPENOCD_DEBUG=`echo $1 | cut -c3-`
            ;;
        -g)
            GDB=1
            ;;
        -*)
            echo "Invalid option: $1" >&2
            exit 1
            ;;
        *)
            OPENOCD_SCRIPT=$1
            if [ ! -f "${OPENOCD_SCRIPT}" ]; then
                echo "Invalid configuration file: '${OPENOCD_SCRIPT}'" >&2
                exit 2
            fi
            ;;
    esac
    shift
done

if [ -z "${OPENOCD_SCRIPT}" ]; then
    echo "No OpenOCD script specified" >&2
    exit 1
fi

if [ ${OPENOCD_DEVICE} -eq 0 ]; then
    echo "No SWD bridge device selected" >&2
    exit 1
fi

if [ ${GDB} -eq 0 ]; then
    COMMAND="-f ${OPENOCD_SCRIPT}"
else
    COMMAND="-f ${OPENOCD_SCRIPT_DIR}/debug.cfg"
fi

OPENOCD_SCRIPT_DIR=$(dirname ${OPENOCD_SCRIPT})

if [ -n "${OPENOCD_SN}" ]; then
    if [ ${OPENOCD_DEVICE} -eq 2 ]; then
        export OPENOCD_JLINK_SN="${OPENOCD_SN}"
    else
        export OPENOCD_FTDI_SN="${OPENOCD_SN}"
    fi
fi

if [ ${OPENOCD_DEVICE} -eq 2 ]; then
    export OPENOCD_JLINK=1
else
    export OPENOCD_FTDI=1
fi

if [ -n "${OPENOCD_DEBUG}" ]; then
    ARGS="-d${OPENOCD_DEBUG}"
    export OPENOCD_DEBUG
fi

if [ ${OPENOCD_DOCKER} -eq 0 ]; then
    # host execution
    OPENOCD=$(which openocd-nrf52 2>/dev/null)
    if [ -z "${OPENOCD}" ]; then
        echo "openocd-nrf52 not found" >&2
        exit 1
    fi
    if [ ${OPENOCD_DEVICE} -eq 2 ]; then
        if [ -n "${OPENOCD_JLINK_SN}" ]; then
            echo "Use J-Link S/N ${OPENOCD_JLINK_SN}"
        fi
    else
        if [ -n "${OPENOCD_FTDI_SN}" ]; then
            echo "Use FTDI S/N ${OPENOCD_FTDI_SN}"
        fi
    fi
    ${OPENOCD} -s ${HOST_DIR} -s ${OPENOCD_SCRIPT_DIR} ${COMMAND} ${ARGS}
else
    # docker execution
    rm -f ${PWD}/build/.dockenv 2> /dev/null
    mkdir -p ${PWD}/build
    if [ ${OPENOCD_DEVICE} -eq 2 ]; then
        echo "OPENOCD_JLINK=${OPENOCD_JLINK}" > ${PWD}/build/.dockenv
        if [ -n "${OPENOCD_JLINK_SN}" ]; then
            echo "OPENOCD_JLINK_SN=${OPENOCD_JLINK_SN}" >> \
                ${PWD}/build/.dockenv
        fi
    else
        if [ -n "${OPENOCD_FTDI_SN}" ]; then
            echo "OPENOCD_FTDI_SN=${OPENOCD_FTDI_SN}" >> \
                ${PWD}/build/.dockenv
        fi
    fi
    if [ -n "${OPENOCD_DEBUG}" ] && [ ${OPENOCD_DEBUG} -gt 0 ]; then
        cat ${PWD}/build/.dockenv
    fi
    ${CURDIR}/dockexec.sh /usr/local/nrf52/bin/openocd \
        -s ${HOST_DIR} -s ${OPENOCD_SCRIPT_DIR} ${COMMAND} ${ARGS}
fi
