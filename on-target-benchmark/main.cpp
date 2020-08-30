/*
 * On-target benchmark program for Mbed TLS's P-256 using Mbed OS.
 */
#include "mbed.h"

#include "mbedtls/ecdh.h"
#include "mbedtls/ecdsa.h"

/* test version based on stdlib - never do this in production! */
int test_prng(void *ctx, unsigned char *output, size_t output_size)
{
    (void) ctx;
    for (unsigned i = 0; i < output_size; i++) {
        output[i] = (uint8_t) rand();
    }

    return 0;
}
Timer t;
int total_ms = 0;

#define FMT "%10s: %5d ms\n"

#define TIMEIT(NAME, CODE)          \
    CODE;                           \
    t.reset();                      \
    t.start();                      \
    CODE;                           \
    t.stop();                       \
    total_ms += t.read_ms();        \
    printf(FMT, NAME, t.read_ms());

int main()
{
    mbedtls_ecp_group p256;
    mbedtls_ecp_point Q;
    mbedtls_mpi d, r, s;
    unsigned char buf[32];

    mbedtls_ecp_group_init(&p256);
    mbedtls_ecp_point_init(&Q);
    mbedtls_mpi_init(&d);
    mbedtls_mpi_init(&r);
    mbedtls_mpi_init(&s);
    memset(buf, 42, sizeof buf);

    mbedtls_ecp_group_load(&p256, MBEDTLS_ECP_DP_SECP256R1);

    int config = 0;
#if defined(CONFIG_SMALLER)
    config = CONFIG_SMALLER;
#endif
    printf("\nMbed TLS P-256 benchmark, config %d\n", config);

    TIMEIT("Keygen", mbedtls_ecdh_gen_public(&p256, &d, &Q, test_prng, NULL));
    TIMEIT("ECDH", mbedtls_ecdh_compute_shared(&p256, &r, &Q, &d, test_prng, NULL));
    TIMEIT("Sign", mbedtls_ecdsa_sign(&p256, &r, &s, &d, buf, sizeof buf, test_prng, NULL));
    TIMEIT("Verify", mbedtls_ecdsa_verify(&p256, buf, sizeof buf, &Q, &r, &s));
    printf(FMT, "Total", total_ms);

    mbedtls_ecp_group_free(&p256);
    mbedtls_ecp_point_free(&Q);
    mbedtls_mpi_free(&d);
    mbedtls_mpi_free(&r);
    mbedtls_mpi_free(&s);

    return 0;
}
