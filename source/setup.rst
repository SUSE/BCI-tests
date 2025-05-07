Secrets/Credentials for the CI
==============================

The following outlines the use of Git Hub secrets to enable larger test coverage
on each pull request as would otherwise be possible. This is because some check
combinations require credentials to retrieve otherwise access-protected content.

Below is a list of secrets and what they are used for.

Access to `registry.suse.com`
-----------------------------

Some checks require access to SUSE Linux Enterprise Server LTSS container images on
registry.suse.com. These are accessible after logging into the registry which is automatically
performed by the ci.yml Git Hub Action. It accesses the following secrets stored for that
purpose:

* ``REGISTRY_LOGIN_USERNAME``
* ``REGISTRY_LOGIN_PASSWORD``

These point to mirroring credentials in a BCI testing organization. Please contact the
BCI team for expanding the configuration of that testing organization.

Access to `dp.apps.rancher.io`
------------------------------

Some checks require access to `SUSE Application Collection <https://apps.rancher.io/>` container images on
`dp.apps.rancher.io`. These are accessible after logging into the Application Collection Distribution
Platform ("DP") which is automatically performed by the ci.yml Git Hub Action. It accesses the following
secrets stored for that purpose:

* ``APPCO_USERNAME``
* ``APPCO_PASSWORD``

These point to access token granted after logging into a sufficiently privileged subscription account
and can be created in the SUSE Application Collection accounts profile page. Please contact the
BCI team for expanding the configuration of that testing organization and please contact the SUSE Application
Collection team to get an account created that has sufficiently subscriptions provisioned.


Access to SLES repositories
---------------------------

The tests for LTSS container images require also access to SUSE Linux Enterprise Server repositories
which are generally access protected. However, the containers are prepared to handle that by embedding
:command:`container-suseconnect`.

The tests for :command:`container-suseconnect` require a
:file:`/etc/zypp/credentials.d/SCCcredentials` from a registered SLES host. This
file is currently constructed on the CI from the following GitHub secrets

* ``SCC_SYSTEM_USERNAME``
* ``SCC_SYSTEM_PASSWORD``

but will in the future be simplified to a plain set of regcodes instead.

SUSE Linux Enterprise Server LTSS Regcodes can be obtained from the BCI testing organization. Please contact the
BCI team for expanding the configuration of that testing organization.
