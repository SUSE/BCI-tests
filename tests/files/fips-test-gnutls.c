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

static inline const char *
fips_operation_state_to_string(gnutls_fips140_operation_state_t state) {
    switch (state) {
    case GNUTLS_FIPS140_OP_INITIAL:
	return "INITIAL";
    case GNUTLS_FIPS140_OP_APPROVED:
	return "APPROVED";
    case GNUTLS_FIPS140_OP_NOT_APPROVED:
	return "NOT_APPROVED";
    case GNUTLS_FIPS140_OP_ERROR:
	return "ERROR";
    default:
	/*NOTREACHED*/ assert(0);
	return NULL;
    }
}

static void tls_log_func(int level, const char *str) {
    fprintf(stderr, "<%d>| %s", level, str);
}

static void audit_log_func(gnutls_session session, const char *str) {
    fprintf(stderr, "audit| %s", str);
}



int main(int argc, char *argv[]) {
    gnutls_digest_algorithm_t digest_algorithm;
    gnutls_fips140_operation_state_t state;
    gnutls_fips140_context_t fips_context;
    const char *mess1 = "Test Message\n";
    const char *mess2 = "Hello World\n";
    unsigned char md_value[128];
    size_t md_len;
    int ret;
    int ret_code=1;

    if (argc < 2) {
        fprintf(stderr, "Usage: mdtest digestname\n");
        return ret_code;
    }

    gnutls_global_set_log_function(tls_log_func);
    gnutls_global_set_log_level(4711);
    gnutls_global_set_audit_log_function(audit_log_func);

    gnutls_global_init();

    assert(gnutls_fips140_context_init(&fips_context) >= 0);

    ret = gnutls_fips140_push_context(fips_context);
    if (ret < 0) {
	fprintf(stderr,"gnutls_fips140_push_context failed\n");
        goto cleanup;
    }

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

    printf("Digest is: ");
    for (size_t i = 0; i < md_len; i++) {
        printf("%02x", md_value[i]);
    }
    printf("\n");

    ret_code=0;
    goto cleanup;

    cleanup:
    ret = gnutls_fips140_pop_context();
    if (ret < 0) {
	fprintf(stderr,"gnutls_fips140_context_pop failed\n");
	return ret_code;
    }
    state = gnutls_fips140_get_operation_state(fips_context);
    if (state != GNUTLS_FIPS140_OP_APPROVED) {
	fprintf(stderr,"This operation was not FIPS 140-3 approved (%s)\n",
	     fips_operation_state_to_string(state));
	return ret_code;
    }

    gnutls_global_deinit();
    return ret_code;
}