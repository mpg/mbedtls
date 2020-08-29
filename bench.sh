#!/bin/sh

set -eu

CONFIG_H=include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak
cp config-p256.h $CONFIG_H

bench_config() {
    CONF=$1
    printf "\n*** Config: $CONF ***\n"

    gcc --std=c99 -Werror -Wall -Wextra -pedantic -Iinclude \
        -Os -ffunction-sections -fdata-sections -Wl,--gc-sections \
        -march=native -DCONFIG_SMALLER=$CONF \
        library/platform_util.c library/platform.c \
        library/bignum.c library/ecp.c library/ecp_curves.c \
        library/ecdh.c library/ecdsa.c \
        benchmark.c -o benchmark

    ./benchmark
}

bench_config 0
bench_config 1
bench_config 2

mv $CONFIG_H.bak $CONFIG_H
rm benchmark
