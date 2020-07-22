#!/bin/sh

set -eu

cd library

CONFIG_H=../include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak

show_stack () {
    CONF=$1
    printf "\n*** Config: $CONF ***\n"

    cp ../config-p256-$CONF.h $CONFIG_H
    rm -f *.o *.su *.dfinish

    arm-none-eabi-gcc -DNO_PTR_CALL -fdump-rtl-dfinish -fstack-usage \
        -Os -fomit-frame-pointer -mthumb -mcpu=cortex-m0 \
        -I../include -c \
        platform_util.c platform.c \
        bignum.c ecp.c ecp_curves.c \
        ecdh.c ecdsa.c

    python3 wcs.py | egrep 'mbedtls_ecdh_gen_public|mbedtls_ecdh_compute_shared|mbedtls_ecdsa_sign|mbedtls_ecdsa_verify'
}

show_stack small
show_stack fast

mv $CONFIG_H.bak $CONFIG_H
rm *.o *.su *.dfinish
