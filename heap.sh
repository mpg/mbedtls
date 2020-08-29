#!/bin/sh

set -eu

CONFIG_H=include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak
cp config-p256.h $CONFIG_H

show_heap() {
    CONF=$1
    printf "\n*** Config: $CONF ***\n"

    make clean

    CFLAGS="-Os -march=native -DBENCHMARK_HEAP -DCONFIG_SMALLER=$CONF"
    export CFLAGS
    make lib >/dev/null
    (cd programs && make test/benchmark) >/dev/null
    programs/test/benchmark ecdh ecdsa
}

show_heap 0
show_heap 1
show_heap 2

mv $CONFIG_H.bak $CONFIG_H
make clean
