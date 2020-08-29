#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/time.h>
#include <inttypes.h>

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

static uint64_t usec(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t) tv.tv_sec * 1000000 + (uint64_t) tv.tv_usec;
}

#define SUCCESS     0
#define TIMES       20
#define TIMEIT(N, CODE)                                             \
do {                                                                \
    if (CODE != SUCCESS)                                            \
        printf("%s failed\n", names[N]);                            \
    const uint64_t start = usec();                                  \
    for (unsigned i = 0; i < TIMES; i++) {                          \
        CODE;                                                       \
    }                                                               \
    results[N][i] = (usec() - start) / TIMES;                       \
} while (0)

#define RUNS 5

int cmp_u64(const void *a, const void *b) {
    uint64_t x = *((uint64_t *) a);
    uint64_t y = *((uint64_t *) b);
    if (x < y)
        return -1;
    if (x > y)
        return 1;
    return 0;
}

int main(void)
{
    uint64_t results[4][RUNS], total_ms = 0;
    const char * names[4] = {"Keygen", "ECDH", "Sign", "Verify"};

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


    for (unsigned i = 0; i < RUNS; i++) {
        TIMEIT(0, mbedtls_ecdh_gen_public(&p256, &d, &Q, test_prng, NULL));
        TIMEIT(1, mbedtls_ecdh_compute_shared(&p256, &r, &Q, &d, test_prng, NULL));
        TIMEIT(2, mbedtls_ecdsa_sign(&p256, &r, &s, &d, buf, sizeof buf, test_prng, NULL));
        TIMEIT(3, mbedtls_ecdsa_verify(&p256, buf, sizeof buf, &Q, &r, &s));
    }

    for (unsigned n = 0; n < 4; n++) {
        qsort(results[n], RUNS, sizeof results[n][0], cmp_u64);
        uint64_t median_ms = results[n][RUNS / 2] / 1000;
        printf("%s: %"PRIu64" ms\n", names[n], median_ms);
        total_ms += median_ms;
    }
    printf("%s: %"PRIu64" ms\n", "Total", total_ms);

    mbedtls_ecp_group_free(&p256);
    mbedtls_ecp_point_free(&Q);
    mbedtls_mpi_free(&d);
    mbedtls_mpi_free(&r);
    mbedtls_mpi_free(&s);

    return 0;
}
