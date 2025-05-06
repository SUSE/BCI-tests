CI Setup & Secrets/Credentials
==============================

The CI is using github actions to run all or a subset of the tests on each pull
request next to general sanity checks.

Some checks require access to paywalled LTSS container images on
registry.suse.com. These are accessible after logging into the registry using
the credentials ``REGISTRY_LOGIN_USERNAME`` and ``REGISTRY_LOGIN_PASSWORD``.

.. TODO(dirk):

To regenerate these credentials, go to scc.suse.com, login and navigate to
https://scc.suse.com/organizations/460227/dashboard. Create a new **XXX**
subscription starting with ``INTERNAL-USE-ONLY``. The password is the
registration code and the username is ``regcode``.

.. TODO(dirk):

The tests for :command:`container-suseconnect` require a
:file:`/etc/zypp/credentials.d/SCCcredentials` from a registered SLES host. This
file is constructed on the CI from the secrets ``SCC_SYSTEM_PASSWORD`` and
``SCC_SYSTEM_USERNAME``. You can obtain both values by registering a
``registry.suse.com/bci/bci-base:15.6`` container image via
:command:`suseconnect --regcode $regcode`. The username and password can then be
obtained from :file:`/etc/zypp/credentials.d/SCCcredentials` in the container
image.
