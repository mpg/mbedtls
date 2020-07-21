/*
 * Minimal configuration for ECDH+ECDSA with P-256 only.
 *
 * Optimized for speed at the expense of footprint (code size, RAM usage).
 */
#ifndef MBEDTLS_CONFIG_H
#define MBEDTLS_CONFIG_H

/* System support */
#define MBEDTLS_HAVE_ASM

/* mbed TLS feature support */
#define MBEDTLS_ECP_DP_SECP256R1_ENABLED

/* mbed TLS modules */
#define MBEDTLS_ASN1_PARSE_C
#define MBEDTLS_ASN1_WRITE_C
#define MBEDTLS_BIGNUM_C
#define MBEDTLS_ECDH_C
#define MBEDTLS_ECDSA_C
#define MBEDTLS_ECP_C

/* Minimize dependencies */
#define MBEDTLS_ECP_NO_INTERNAL_RNG

/* Avoid annoying libc dependencies */
#if defined(BAREMETAL)
#define MBEDTLS_PLATFORM_C
#define MBEDTLS_PLATFORM_MEMORY
#include <stdlib.h>
#define MBEDTLS_PLATFORM_CALLOC_MACRO   dummy_calloc
void *dummy_calloc(size_t n, size_t s);
#define MBEDTLS_PLATFORM_FREE_MACRO     dummy_free
void dummy_free(void *ptr);
#endif

/* Save RAM by adjusting to our exact needs */
#define MBEDTLS_ECP_MAX_BITS   256
#define MBEDTLS_MPI_MAX_SIZE    32  // 256 bits is 32 bytes

/* Don't save RAM at the expense of speed, keep default, see ecp.h */
//#define MBEDTLS_ECP_WINDOW_SIZE        2
//#define MBEDTLS_ECP_FIXED_POINT_OPTIM  0

/* Expend code size to gain speed */
#define MBEDTLS_ECP_NIST_OPTIM

#include "mbedtls/check_config.h"

#endif /* MBEDTLS_CONFIG_H */
