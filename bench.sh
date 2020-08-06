#!/bin/sh

set -eu

CONFIG_H=include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak

bench_config() {
    CONF=$1
    printf "\n*** Config: $CONF ***\n"

    cp config-p256-$CONF.h $CONFIG_H

    gcc --std=c99 -Werror -Wall -Wextra -pedantic -Iinclude \
        -Os -ffunction-sections -fdata-sections -Wl,--gc-sections \
        library/platform_util.c library/platform.c \
        library/bignum.c library/ecp.c library/ecp_curves.c \
        library/ecdh.c library/ecdsa.c \
        benchmark.c -o benchmark

    ./benchmark
}

bench_config small
bench_config fast

mv $CONFIG_H.bak $CONFIG_H
rm benchmark
