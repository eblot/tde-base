#!/bin/sh

ARGS=$*

# Show usage information
usage()
{
    NAME=`basename $0`
    cat <<EOT
$NAME [options]

  Run a Docker session from a Docker image

    --env  <name:[version]>  Specify an alternate image
    --port <port>            Map a network port

EOT
}

if [ -z "${DOCKERHUB_USER}" ]; then
    DOCKERHUB_USER="iroazh"
fi
hubprefix="${DOCKERHUB_USER}/"

NOCMD=0
DEVENV=devenv
TTY_OPT=""
OPTS=""
EXEC_ARGS=""
set -- ${ARGS}
while [ -n "$1" ]; do
    case "$1" in
      --env)
        shift
        DEVENV=$1
        shift
        continue
        ;;
      --port)
        shift
        OPTS="-p $1:$1 ${OPTS}"
        shift
        continue
        ;;
      -h)
        usage
        exit 0
        ;;
      *)
        # build a list of projects
        EXEC_ARGS="${EXEC_ARGS} $1"
        ;;
    esac
    shift
done
ARGS=${EXEC_ARGS}

DIR=`dirname $0`
VOLUMES=`${DIR}/dockvol.sh`
[ $? -eq 0 ] || exit 1

for volume in ${VOLUMES}; do
    OPTS="${OPTS} --volumes-from ${volume}"
done

. "$(dirname $0)/../docker/exec/docker.conf"

$(echo "${DEVENV}" | grep -q ":")
if [ $? -eq 0 ]; then
    TMP="${DEVENV}"
    DEVENV="$(echo ${TMP} | cut -d: -f1)"
    DEVENV_VER="$(echo ${TMP} | cut -d: -f2)"
    if [ -z "${DEVENV_VER}" ]; then
        DEVENV_VER="latest"
    fi
fi

devenv="${DEVENV}:${DEVENV_VER}"

if [ ! $(docker images -q -f reference=${devenv}) ]; then
    devenv="${hubprefix}${devenv}"
    if [ ! $(docker images -q -f reference=${devenv}) ]; then
        echo "Downloading missing image ${devenv}" >&2
        docker pull ${devenv}
        if [ $? -ne 0 ]; then
            if [ -z "${DOCKERHUB_USER}" ]; then
                echo "" >&2
                echo " -> You may want to define DOCKERHUB_USER" >&2
            fi
            exit 1
        fi
    fi
fi

IMGPATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
IMGPATH=${IMGPATH}:/usr/local/clang9/bin:/usr/local/arm-none-eabi/bin:/usr/local/nrf52/bin

if [ -z "${ARGS}" ]; then
    CMD="sh"
    TTY_OPT="--tty"
else
    CMD="${ARGS}"
fi

EXTRAS=""
if [ -s "${PWD}/build/.dockenv" ]; then
    EXTRAS="--env-file ${PWD}/build/.dockenv"
fi

SBX=`basename $PWD`
mkdir -p ${PWD}/build
# run with priviledged container has tools such as openocd require access to USB HW
docker run ${EXTRAS} \
    --interactive ${TTY_OPT} \
    --rm \
    --name ${SBX} \
    ${OPTS} \
    --privileged \
    --env PATH=${IMGPATH} \
    --mount type=bind,source=${PWD},target=/${SBX} \
    --workdir=/${SBX} ${devenv} \
    /bin/sh -c "${CMD}"
DOCKER_RC=$?

rm -f ${PWD}/build/.dockenv 2> /dev/null

exit ${DOCKER_RC}
