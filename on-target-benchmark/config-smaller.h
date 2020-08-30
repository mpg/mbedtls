/*
 * Mbed TLS user config - adjust the default Mbed OS config
 *
 * Usage:  mbed compile '-DMBEDTLS_USER_CONFIG_FILE="mbedtls_user_config.h"' -DCONFIG_SMALLER=0
 */

/* Force-enable ECDH even on platforms with no entropy */
#define MBEDTLS_ECDH_C

/* Save RAM by adjusting to our exact needs */
#define MBEDTLS_ECP_MAX_BITS   256
#define MBEDTLS_MPI_MAX_SIZE    32  // 256 bits is 32 bytes

#if CONFIG_SMALLER > 0
/* Save RAM at the expense of speed, see ecp.h */
#define MBEDTLS_ECP_WINDOW_SIZE        2
#define MBEDTLS_ECP_FIXED_POINT_OPTIM  0
#endif

#if CONFIG_SMALLER > 1
/* Save code size at the expense of speed */
#undef MBEDTLS_ECP_NIST_OPTIM
#endif
