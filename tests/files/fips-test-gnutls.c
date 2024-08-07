/** Simple C program that will calculate the hash of a fixed string using
 * GnuTLS.
 *
 * The hash to be used is passed as the first parameter to the binary.
 * This program demonstrates the use of GnuTLS for computing message digests.
 */

#include <stdio.h>
#include <string.h>
#include <gnutls/gnutls.h>
#include <gnutls/crypto.h>
#include <stdlib.h>
#include <assert.h>

int main(int argc, char *argv[]) {
    gnutls_digest_algorithm_t digest_algorithm;
    const char *mess1 = "Test Message\n";
    const char *mess2 = "Hello World\n";
    unsigned char md_value[128];
    size_t md_len;
    int ret_code=1;

    if (argc < 2) {
        fprintf(stderr, "Usage: mdtest digestname\n");
        return ret_code;
    }

    gnutls_global_init();
    digest_algorithm = gnutls_digest_get_id(argv[1]);
    if (digest_algorithm == GNUTLS_DIG_UNKNOWN) {
        fprintf(stderr, "Unknown message digest %s\n", argv[1]);
        goto cleanup;
    }

    unsigned char hash1[64];
    size_t hash1_size = gnutls_hash_get_len(digest_algorithm);
    if (gnutls_hash_fast(digest_algorithm, (const unsigned char *)mess1, strlen(mess1), hash1) != GNUTLS_E_SUCCESS) {
        fprintf(stderr, "Hash calculation failed\n");
        goto cleanup;
    }

    unsigned char hash2[64];
    size_t hash2_size = gnutls_hash_get_len(digest_algorithm);
    if (gnutls_hash_fast(digest_algorithm, (const unsigned char *)mess2, strlen(mess2), hash2) != GNUTLS_E_SUCCESS) {
        fprintf(stderr, "Hash calculation failed\n");
        goto cleanup;
    }

    memcpy(md_value, hash1, hash1_size);
    memcpy(md_value + hash1_size, hash2, hash2_size);
    md_len = hash1_size + hash2_size;

    gnutls_global_deinit();
    printf("Digest is: ");
    for (size_t i = 0; i < md_len; i++) {
        printf("%02x", md_value[i]);
    }
    printf("\n");
    ret_code=0;
    goto cleanup;

    cleanup:
        gnutls_global_deinit();
        return ret_code;
}