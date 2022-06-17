/** Simple C program that will calculate the hash of a fixed string using
 * openSSL.
 *
 * The hash to be used is passed as the first parameter to the binary.
 * This program has been taken from
 * https://www.openssl.org/docs/manmaster/man3/EVP_DigestInit.html
 */

#include <assert.h>
#include <openssl/err.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
  EVP_MD_CTX *mdctx;
  const EVP_MD *md;
  char mess1[] = "Test Message\n";
  char mess2[] = "Hello World\n";
  char *err_msg = NULL;
  unsigned char md_value[EVP_MAX_MD_SIZE];
  unsigned int md_len, i;

#define FAIL(msg)                                                              \
  err_msg = msg;                                                               \
  goto fail

  if (argv[1] == NULL) {
    FAIL("Usage: mdtest digestname");
  }

  md = EVP_get_digestbyname(argv[1]);
  if (md == NULL) {
    fprintf(stderr, "Unknown message digest %s\n", argv[1]);
    exit(1);
  }

  mdctx = EVP_MD_CTX_new();
  if (mdctx == NULL) {
    FAIL("EVP_MD_CTX_new returned NULL");
  }
  if (1 != EVP_DigestInit_ex(mdctx, md, NULL)) {
    FAIL("EVP_DigestInit_ex was not successful");
  }
  if ((1 != EVP_DigestUpdate(mdctx, mess1, strlen(mess1))) ||
      (1 != EVP_DigestUpdate(mdctx, mess2, strlen(mess2)))) {
    FAIL("EVP_DigestUpdate was not successful");
  }
  if (1 != EVP_DigestFinal_ex(mdctx, md_value, &md_len)) {
    FAIL("EVP_DigestFinal_ex was not successful");
  }

  EVP_MD_CTX_free(mdctx);

  printf("Digest is: ");
  for (i = 0; i < md_len; i++) {
    printf("%02x", md_value[i]);
  }
  printf("\n");

  return 0;
fail:
  assert(err_msg);
  fprintf(stderr, "%s\n", err_msg);
  unsigned long err;
  while ((err = ERR_get_error())) {
    fprintf(stderr, "%s\n", ERR_error_string(err, NULL));
  }
  exit(1);
}
