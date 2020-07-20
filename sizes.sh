#!/bin/sh

set -eu

CONFIG_H=include/mbedtls/config.h
cp $CONFIG_H $CONFIG_H.bak
rm -f *.o

# Get the size of the mbed TLS P-256 ECDH-ECDSA implementation for a given
# CPU (in the Cortex-xx family) and configuration (see config-p256-*.h).
#
# Strategy: instead of just adding the sizes of the .o files involved,
# which would include extra functions, use a dummy program ecc-entry.c, link
# it using link-time garbage collection of unused symbols, and in the result
# take the sum of the sizes of symbols coming from mbed TLS.
get_size() {
    CPU=$1
    CONF=$2

    cp config-p256-$CONF.h $CONFIG_H

    arm-none-eabi-gcc -Werror -Wall -Wextra -pedantic --std=c99 -Iinclude \
        -Os -fomit-frame-pointer -mthumb -mcpu=cortex-$CPU \
        -c -ffunction-sections -fdata-sections \
        -DBAREMETAL library/platform_util.c library/platform.c \
        library/bignum.c library/ecp.c library/ecp_curves.c \
        library/ecdh.c library/ecdsa.c \
        ecc-entry.c

    arm-none-eabi-gcc -mthumb -mcpu=cortex-$CPU \
        -nostartfiles -Wl,--gc-sections --entry=ecc_entry *.o \
        -o ecc.elf

    # manual list from looking at the output; a more robust approach would be
    # to look if the symbol was defined in an mbed TLS object file
    MBEDTLS='mbedtls_|ecp_|ecdsa_|mpi_|secp256r1|add32|sub32|derive_mpi|memset_func'
    arm-none-eabi-nm --print-size --radix=d ecc.elf |
        awk "/^[0-9]{8} [0-9]{8} . $MBEDTLS/"' {sum += $2} END {print sum}'
}

for CPU in m0 m4 a5; do
    printf "$CPU: %5d %5d\n" "$(get_size $CPU small)" "$(get_size $CPU fast)"
done

mv $CONFIG_H.bak $CONFIG_H
rm *.o ecc.elf
