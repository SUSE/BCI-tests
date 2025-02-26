|CI|

.. |CI| image:: https://github.com/SUSE/BCI-tests/actions/workflows/ci.yaml/badge.svg?branch=main
   :target: https://github.com/SUSE/BCI-tests/actions/workflows/ci.yaml

BCI tests
=========

What is this?
-------------

This is our tooling to test the BCI containers, ensuring they are matching what
our ISVs are expecting, e.g.:

* ensure that they don't exceed a certain size,
* working with multi-stage dockerfiles,
* able to build common software for the languages stacks that we provide,
* test how they behave in FIPS enabled environments,
* ...

How can I contribute?
---------------------

* Create a PR to increase test coverage (See below for further information).
* Create an issue, stating your use case.
* Improve our documentation.

What do I need to contribute?
-----------------------------

* A host with python 3.6+, gcc and the python development header files
* tox
* go
* docker and/or podman+buildah

How can I run the tests?
------------------------

1. Ensure that you have the dependencies installed
2. Optionally set the ``BCI_DEVEL_REPO`` environment variable (see next section).
3. Run ``tox -e build`` (this is not strictly necessary to run beforehands, but it
   will reduce the danger of race conditions when building containers)
4. Run ``tox -e $language_stack -- -n auto``

Technical contributions
-----------------------

The base container
^^^^^^^^^^^^^^^^^^

We are basing most of our tests on _the_ base container (available via the
``BASE_CONTAINER`` variable in :file:`bci_tester/data.py`). This container is pulled
directly from ``registry.suse.de`` and is being build from the
`SUSE:SLE-15-SP3:Update:CR:ToTest/sles15-image
<https://build.suse.de/package/show/SUSE:SLE-15-SP3:Update:CR:ToTest/sles15-image>`_
package.

That container is automatically configured at build time to contain the
``SLE_BCI`` repository from ``update.suse.com`` (i.e. the repository **after** QA
tested it). We also want to be able to test the current development state of the
``SLE_BCI`` repository. This can be achieved by setting the environment variable
``BCI_DEVEL_REPO`` to the url of the development/snapshot state. It is published
on ``dist.nue.suse.com`` in one of the subfolders of
http://dist.nue.suse.com/ibs/SUSE:/SLE-15-SP3:/Update:/BCI/images/repo/. Unfortunately,
you have to hand pick the correct folder (use the one ending with ``-Media1`` and
for the correct arch) because the build number is put into the folder name.

The ``BASE_CONTAINER`` will then be rebuild with the ``SLE_BCI`` repository
replaced with the one from the ``BCI_DEVEL_REPO`` and all tests will thus use
the new repository.

Adding new containers and their tests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Find container "type" or "language". When adding a new container, be sure to
   add it to :file:`bci_tester/data.py`, optionally also include it in the if branch
   to replace the ``SLE_BCI`` repository.
2. Add it into :file:`tox.ini` in envlist, if not present.
3. Create or update a file named :file:`test_<container_type>.py` (for example,
   :file:`test_python.py`)
4. Add your tests there based on `testinfra
   <https://testinfra.readthedocs.io/en/latest/modules.html>`_ and
   `pytest_container <https://github.com/dcermak/pytest_container/>`_

Extending coverage/Writing tests for existing containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Just use testinfra documentation (linked above). It should be
easy.

You can use the convenience tools from conftest:

* If you are using the ``auto_container`` fixture, your test will automatically be
  run for all containers defined in the module variables ``CONTAINER_IMAGES``.

The container fixture
^^^^^^^^^^^^^^^^^^^^^

The ``auto_container`` fixture contains the black magic to run tests for all
container images without having to parametrize everything yourself.
If you need to run a test only for certain versions of a language stack, you
have the following three options (by order of preference):

1. Use the ``container`` fixture and parametrize it yourself.
2. Create your own fixture


Adding additional container run and build parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is sometimes necessary to add additional parameters to the ``docker build`` or
``docker run`` invocation, for it to succeed. E.g. when the docker network needs
access to a VPN connection to access dist.nue.suse.de, then one has to run
docker with ``--network=host``.

This can be achieved by setting the environment variables ``EXTRA_RUN_ARGS`` and
``EXTRA_BUILD_ARGS`` to whatever should be added to the calls to ``docker
run`` / ``podman run`` and ``docker build`` / ``buildah bud``, respectively.


Running all tests
-----------------

.. code-block:: shell-session

    $ tox --parallel

For CI environments it is recommended to set the environment variable
``TOX_PARALLEL_NO_SPINNER`` to ``1`` so that the output from tox is not mangled.


Running tests in production
---------------------------

Some of the tests can be a bit flaky due to network resources not being
available. To avoid these issues, we make use of the `pytest-rerunfailures
<https://github.com/pytest-dev/pytest-rerunfailures>`_ plugin. To enable it,
invoke tox with the ``--reruns`` command line flag as follows:

.. code-block:: shell-session

   $ tox -e test_name -- --reruns 3 --reruns-delay 10

The option ``--reruns-delay`` delays the rerun (in this case) by 10 seconds,
thereby reducing the likelihood of another network issue.


Running specific tests
----------------------

.. code-block:: shell-session

    $ tox -e testname

``testname`` equals to ``python`` for the test file named :file:`test_python.py`

This will run _all_ the tests for a language, which could mean multiple
stacks. If you have Python 3.6 or later available and have the python
development headers installed, then ``pytest-xdist`` will be installed as well
and can be used to launch the tests of a single test suite in parallel via:

.. code-block:: shell-session

    $ tox -e testname -- -n auto


Adding the pre-commit hook
--------------------------

You can setup the :file:`pre-commit.sh` script as a pre-commit hook in git, so
that it runs each time before a commit is created. The script exits with a
non-zero status when the desired formatting is not applied.

The :file:`pre-commit-full.sh` script in addition also checks if any container
marker in :file:`pyproject.toml` is missing. This checks takes some time.

To install the hook, execute the following commands from the top level project
directory:

.. code-block:: shell-session

    $ pushd .git/hooks/
    $ ln -s ../../pre-commit.sh pre-commit   # use `pre-commit-full.sh` to also check container marks
    $ popd

