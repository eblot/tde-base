#!/bin/sh

ARGS=$*
# output files/directories that should be retrieved from the Docker session
PRODUCTS='*.elf *.hex *.pdf *.egg html'

BUILD_SCRIPT="host/bin/build.sh"

if [ -z "${DOCKERHUB_USER}" ]; then
    DOCKERHUB_USER="iroazh"
fi
hubprefix="${DOCKERHUB_USER}/"

. "$(dirname $0)/../docker/exec/docker.conf"

# Show usage information
usage()
{
    NAME=`basename $0`
    cat <<EOT
$NAME [options]

  Build up embedded application projects from Docker containers

    --shell       Debug docker environment (run an interactive shell, ignoring
                  build commands)
    --prod        Build in a fully isolated environment (no local build files)

EOT

   ${BUILD_SCRIPT} -h | tail -n +5
}

NOCMD=0
PROD=0
TTY_OPT=""
DEVENV="lightdevenv:${LIGHTDEVENV_VER}"
BUILD_ARGS=""
BPRJS=""
set -- ${ARGS}
while [ -n "$1" ]; do
    case "$1" in
      --shell)
        # to debug the docker environment, run an interactive shell
        # instead of the regular command
        NOCMD=1
        TTY_OPT="--tty"
        ;;
      --prod)
        PROD=1
        # discard this flags from the lower script argument list
        shift
        continue
        ;;
      -y|-Y)
        # when documentation generation is requested, switch to an heavier
        # base environment with a complete Python3 installation
        DEVENV="devenv:${DEVENV_VER}"
        case "$2" in
          pdf)
            # when PDF documentation generation is requested, switch to an even
            # heavier base environment with a complete LaTeX installation
            DEVENV="texdevenv:${TEXDEVENV_VER}"
            BUILD_ARGS="${BUILD_ARGS} $1"
            ;;
        esac
        ;;
      -h)
        usage
        exit 0
        ;;
      -*)
        ;;
      *)
        # build a list of projects
        BPRJS="${BPRJS} ${arg}"
        ;;
    esac
    if [ -z "${BUILD_ARGS}" ]; then
        BUILD_ARGS="$1"
    else
        BUILD_ARGS="${BUILD_ARGS} $1"
    fi
    shift
done

# Upper directories are not mapped into Docker
# It is not possible to check out a branch hierarchy, and build from a
# sub directory of the working copy, i.e. checkout branches/release works,
# but ckeckiout branches/, cd'ing into release and invoke build does not.
if [ ! -d ".git" ]; then
    echo "Git repository not found. Run $(basename $0) from top-level dir" >&2
    exit 1
fi

DIR=`dirname $0`
VOLUMES=`${DIR}/dockvol.sh`
[ $? -eq 0 ] || exit 1

OPTS=""
for volume in ${VOLUMES}; do
    OPTS="${OPTS} --volumes-from ${volume}"
done

devenv="${hubprefix}${DEVENV}"

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

IMGPATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
IMGPATH=${IMGPATH}:/usr/local/clang8/bin:/usr/local/arm-none-eabi/bin

FILTER=''
for product in ${PRODUCTS}; do
    if [ -n "${FILTER}" ]; then
        FILTER="${FILTER} -o"
    fi
    FILTER="${FILTER} -name '$product'"
done
if [ ${NOCMD} -eq 0 ]; then
    CMD="${BUILD_SCRIPT} ${BUILD_ARGS}"
    if [ ${PROD} -ne 0 ]; then
        CMD="${CMD} && \
            (rm -f /build-output/.dockbuild.tar;
             cd build && \
            find . ${FILTER} | xargs tar cf /build-output/.dockbuild.tar)"
    fi
else
    CMD="sh"
fi

echo "Using Docker environment \"${DEVENV}\""
SBX=`basename $PWD`

if [ ${PROD} -ne 0 ]; then
    # Production (isolated) mode:
    # - ignore all local build files (force full rebuild)
    # - all build files are stored in guest temporary FS (RAM)
    # - final output files will be copied back to the host through tarball
    DOCKOPTS="--mount type=bind,source=${PWD}/build,target=/build-output"
    DOCKOPTS="${DOCKOPTS} --mount type=tmpfs,target=/${SBX}/build"
    echo "Production mode"
    if [ -d "${PWD}/build" ]; then
        if [ -z "${BPRJS}" ]; then
            # force removal of all build directories
            rm -rf "${PWD}/build"
        else
            # force removal of specified projects
            (cd "${PWD}/build" && rm -rf "${BPRJS}")
        fi
    fi
    mkdir -p "${PWD}/build"
else
    # Development (transparent) mode"
    # - build with user id so that output files belongs to the effective user
    DOCKOPTS="--user $(id -u):$(id -g)"
fi

docker run \
    --interactive ${TTY_OPT} \
    --rm \
    --name ${SBX} \
    ${OPTS} \
    --env PATH=${IMGPATH} \
    --mount type=bind,source=${PWD},target=/${SBX} \
    ${DOCKOPTS} \
    --workdir=/${SBX} ${devenv} \
    /bin/sh -c "${CMD}"

if [ ${PROD} -ne 0 ] && [ -s "${PWD}/build/.dockbuild.tar" ]; then
    # Production mode: extract useful output file from generated tar file
    (cd "${PWD}/build" && tar xf .dockbuild.tar)
    rm -f "${PWD}/build/.dockbuild.tar" 2> /dev/null
fi
