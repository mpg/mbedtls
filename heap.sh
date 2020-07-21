#!/bin/sh

set -eu

CONFIG_H=include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak

show_heap() {
    CONF=$1
    printf "\n*** Config: $CONF ***\n"

    cp config-p256-$CONF.h $CONFIG_H
    make clean

    CFLAGS='-Os -DBENCHMARK_HEAP'
    export CFLAGS
    make lib >/dev/null
    (cd programs && make test/benchmark) >/dev/null
    programs/test/benchmark ecdh ecdsa
}

show_heap small
show_heap fast

mv $CONFIG_H.bak $CONFIG_H
make clean
