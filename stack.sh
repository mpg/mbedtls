#!/bin/sh

set -eu

cd library

CONFIG_H=../include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak
cp ../config-p256.h $CONFIG_H

show_stack () {
    CONF=$1
    printf "\n*** Config: $CONF ***\n"

    rm -f *.o *.su *.dfinish

    arm-none-eabi-gcc -DNO_PTR_CALL -fdump-rtl-dfinish -fstack-usage \
        -Os -fomit-frame-pointer -mthumb -mcpu=cortex-m0 \
        -DCONFIG_SMALLER=$CONF -I../include -c \
        platform_util.c platform.c \
        bignum.c ecp.c ecp_curves.c \
        ecdh.c ecdsa.c

    python3 wcs.py | egrep 'mbedtls_ecdh_gen_public|mbedtls_ecdh_compute_shared|mbedtls_ecdsa_sign|mbedtls_ecdsa_verify'
}

show_stack 0
show_stack 1
show_stack 2

mv $CONFIG_H.bak $CONFIG_H
rm *.o *.su *.dfinish
