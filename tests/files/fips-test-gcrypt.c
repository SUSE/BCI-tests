/** Simple C program that will calculate the hash of a fixed string using
 * libgcrypt.
 *
 * The hash to be used is passed as the first parameter to the binary.
 * This program demonstrates the use of libgcrypt for computing message digests.
 */
#include <stdio.h>
#include <string.h>
#include <gcrypt.h>

int main(int argc, char *argv[]) {
    gcry_md_hd_t md_hd = NULL;
    const char *mess1 = "Test Message\n";
    const char *mess2 = "Hello World\n";
    unsigned char md_value[128];
    int ret_code = 1;

    if (argc < 2) {
        fprintf(stderr, "Usage: fips-test-gcrypt digestname\n");
        return ret_code;
    }

    if (!gcry_check_version(GCRYPT_VERSION)) {
        fprintf(stderr, "libgcrypt version mismatch\n");
        return ret_code;
    }
    gcry_control(GCRYCTL_INITIALIZATION_FINISHED, 0);

    const int algo = gcry_md_map_name(argv[1]);
    if (algo == 0) {
        fprintf(stderr, "Unknown message digest %s\n", argv[1]);
        return ret_code;
    }
    // check if the algorithm is FIPS compliant to the service indicator
    // SUSE named it GCRYCTL_FIPS_SERVICE_INDICATOR_HASH, but upstream named it GCRYCTL_FIPS_SERVICE_INDICATOR_MD since 1.11.0
    // upstream added it in 1.11.0 , but we already had it backported for SP6 in 1.10.3.
    // indicators are new with FIPS 140-3 which we started with 1.9.4
#if GCRYPT_VERSION_NUMBER >= 0x010904
# if GCRYPT_VERSION_NUMBER < 0x010a03
#  define GCRYCTL_FIPS_SERVICE_INDICATOR_MD GCRYCTL_FIPS_SERVICE_INDICATOR_HASH
# endif
    if (gcry_control(GCRYCTL_FIPS_SERVICE_INDICATOR_MD, algo) != GPG_ERR_NO_ERROR) {
        fprintf(stderr, "Algorithm %s is not FIPS compliant\n", argv[1]);
        return ret_code;
    }
#endif

    if (gcry_md_open(&md_hd, algo, GCRY_MD_FLAG_SECURE) != 0) {
        fprintf(stderr, "Failed to create hash context\n");
        goto cleanup;
    }

    gcry_md_write(md_hd, (const void *)mess1, strlen(mess1));
    unsigned char hash1[64];
    const size_t hash1_size = gcry_md_get_algo_dlen(algo);
    memcpy(hash1, gcry_md_read(md_hd, 0), hash1_size);

    gcry_md_reset(md_hd);
    gcry_md_write(md_hd, (const void *)mess2, strlen(mess2));
    unsigned char hash2[64];
    const size_t hash2_size = gcry_md_get_algo_dlen(algo);
    memcpy(hash2, gcry_md_read(md_hd, 0), hash2_size);

    memcpy(md_value, hash1, hash1_size);
    memcpy(md_value + hash1_size, hash2, hash2_size);
    const size_t md_len = hash1_size + hash2_size;

    printf("Digest is: ");
    for (size_t i = 0; i < md_len; i++) {
        printf("%02x", md_value[i]);
    }
    ret_code = 0;

cleanup:
    if (md_hd != NULL) {
        gcry_md_close(md_hd);
    }
    return ret_code;
}
