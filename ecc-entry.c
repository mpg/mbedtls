#include "mbedtls/ecdh.h"
#include "mbedtls/ecdsa.h"

void *dummy_calloc(size_t n, size_t s) {
    (void) n;
    (void) s;
    return NULL;
}

void dummy_free(void *ptr) {
    (void) ptr;
}

/*
 * This function is not meant to work, just to provide an entry point for the
 * linker for the purpose of size measurements.
 */
void ecc_entry(void)
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

    mbedtls_ecp_group_load(&p256, MBEDTLS_ECP_DP_SECP256R1);

    mbedtls_ecdh_gen_public(&p256, &d, &Q, NULL, NULL);
    mbedtls_ecdh_compute_shared(&p256, &r, &Q, &d, NULL, NULL);

    mbedtls_ecdsa_sign(&p256, &r, &s, &d, buf, sizeof buf, NULL, NULL);
    mbedtls_ecdsa_verify(&p256, buf, sizeof buf, &Q, &r, &s);

    mbedtls_mpi_write_binary(&r, buf, sizeof buf);
    mbedtls_mpi_read_binary(&r, buf, sizeof buf);

    mbedtls_ecp_group_free(&p256);
    mbedtls_ecp_point_free(&Q);
    mbedtls_mpi_free(&d);
    mbedtls_mpi_free(&r);
    mbedtls_mpi_free(&s);
}
