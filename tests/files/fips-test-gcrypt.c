/** Simple C program that will calculate the hash of a fixed string using
 * libgcrypt.
 *
 * The hash to be used is passed as the first parameter to the binary.
 * This program demonstrates the use of libgcrypt for computing message digests.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gcrypt.h>

int main(int argc, char *argv[]) {
    gcry_md_hd_t md_hd;
    const char *mess1 = "Test Message\n";
    const char *mess2 = "Hello World\n";
    unsigned char md_value[128];
    size_t md_len;
    int ret_code = 1;

    if (argc < 2) {
        fprintf(stderr, "Usage: %s digestname\n", argv[0]);
        return ret_code;
    }

    if (!gcry_check_version(GCRYPT_VERSION)) {
        fprintf(stderr, "libgcrypt version mismatch\n");
        return ret_code;
    }
    gcry_control(GCRYCTL_INITIALIZATION_FINISHED, 0);

    int algo = gcry_md_map_name(argv[1]);
    if (algo == 0) {
        fprintf(stderr, "Unknown message digest %s\n", argv[1]);
        goto cleanup;
    }

    if (gcry_md_open(&md_hd, algo, GCRY_MD_FLAG_SECURE) != 0) {
        fprintf(stderr, "Failed to create hash context\n");
        goto cleanup;
    }

    gcry_md_write(md_hd, (const void *)mess1, strlen(mess1));
    unsigned char hash1[64];
    size_t hash1_size = gcry_md_get_algo_dlen(algo);
    memcpy(hash1, gcry_md_read(md_hd, 0), hash1_size);

    gcry_md_reset(md_hd);
    gcry_md_write(md_hd, (const void *)mess2, strlen(mess2));
    unsigned char hash2[64];
    size_t hash2_size = gcry_md_get_algo_dlen(algo);
    memcpy(hash2, gcry_md_read(md_hd, 0), hash2_size);

    memcpy(md_value, hash1, hash1_size);
    memcpy(md_value + hash1_size, hash2, hash2_size);
    md_len = hash1_size + hash2_size;

    printf("Digest is: ");
    for (size_t i = 0; i < md_len; i++) {
        printf("%02x", md_value[i]);
    }
    printf("\n");
    ret_code = 0;

cleanup:
    gcry_md_close(md_hd);
    return ret_code;
}
