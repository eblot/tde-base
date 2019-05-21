#!/bin/sh

die() {
    echo "" >&2
    echo "$*" >&2
    exit 1
}

mkdir -p ${HOME}/Sources/toolchain/src
if [ ! -d ${HOME}/Sources/toolchain/src/openocd-nrf52 ]; then
    cd ${HOME}/Sources/toolchain/src
    git clone https://github.com/eblot/openocd.git
    cd ${HOME}/Sources/toolchain/src/openocd
    git checkout -b nrf52-wdog -t origin/nrf52-wdog
    cd ${HOME}/Sources/toolchain/src
    mv openocd openocd-nrf52
    cd ${HOME}/Sources/toolchain/src/openocd-nrf52
else
    cd ${HOME}/Sources/toolchain/src/openocd-nrf52
    make distclean
fi

export CFLAGS="-O2"

./bootstrap || die "Cannot bootstrap OpenOCD"
./configure \
    --enable-verbose --enable-verbose-jtag-io --enable-verbose-usb-io \
    --enable-verbose-usb-comms --enable-ftdi --enable-cmsis-dap \
    --enable-jlink  --disable-doxygen-html --disable-doxygen-pdf \
    --disable-werror --disable-dummy --disable-stlink --disable-ti-icdi \
    --disable-ulink --disable-usb-blaster-2 --disable-ft232r \
    --disable-vsllink --disable-xds110 --disable-osbdm --disable-opendous \
    --disable-aice --disable-usbprog --disable-rlink --disable-armjtagew \
    --disable-kitprog --disable-usb-blaster --disable-presto \
    --disable-openjtag --disable-parport --disable-jtag_vpi \
    --disable-amtjtagaccel --disable-zy1000-master --disable-zy1000 \
    --disable-ep93xx --disable-at91rm9200  --disable-imx_gpio \
    --disable-gw16012 --disable-oocd_trace --disable-buspirate \
    --disable-sysfsgpio --disable-minidriver-dummy --disable-remote-bitbang \
    --prefix=/usr/local/nrf52 || die "Cannot configure OpenOCD"
make || die "Cannot build OpenOCD"
sudo make install || die "Cannot install OpenOCD"
