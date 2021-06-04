# Container testing

## What is this?

This is our tooling to test the BCI containers, ensuring they are matching what our ISVs are expecting, e.g.:

* ensure that they don't exceed a certain size,
* working with multi-stage dockerfiles,
* able to build common software for the languages stacks that we provide,
* test how they behave in FIPS enabled environments,
* ...

## How can I contribute?

* Create a PR to increase test coverage (See below for further information).
* Create an issue, stating your use case.
* Improve our documentation.

## What do I need to contribute?

* A host with python 3.8+
* tox
* docker or podman+buildah

## Technical contributions

### Adding new containers and their tests

1. Find container "type" or "language"
2. Add it into `tox.ini` in envlist, if not present.
3. Create or update a file named `test_<container_type>.py` (for example, `test_python.py`)
4. Add your tests there based on [testinfra](https://testinfra.readthedocs.io/en/latest/modules.html)
5. Ensure the container data is up to date by updating `bci_tester/data/containers.json`.

### Extending coverage/Writing tests for existing containers

Just use testinfra documentation (linked above). It should be
easy.

You can use the convenience tools from conftest:

* If you are using the `auto_container` fixture, your test will auto generate the right tests for _all_ the versions of your language. This is auto loaded, and doesn't need anything from your side except using the keyword `auto_container`. See below for more details.
* If you want to _skip_ some of those tests, use the decorator named `restrict_to_version`, which accepts a list of strings of the versions for which to run the test. See below for more details.

### The container fixture

The `auto_container` fixture contains the black magic to run commands for all versions of a language container.
If you need to run a test only for certain versions of a language stack, you have the following three options (by order of preference):

1. Use the [`restrict_to_version`](#the-restrict_to_version-decorator) decorator to limit which containers your test applies to.
2. Create your own fixture
3. Use the `container` fixture and parametrize it yourself.

The `auto_container` fixture automatically finds the testfile filename, uses it to infer the language of the container under test,
and starts all the necessary containers. See also `conftest.py`.

### The `restrict_to_version` decorator

This decorator accepts a list of strings matching the versions from `data.py`.

To use it:

1. add `from conftest import restrict_to_version` to your imports.
2. wrap your test function as follow (assuming openjdk here):

```Python
@restrict_to_version(['11'])
def mytest(container):
    pass
```
* If you want to restrict certain tests from running in parallel, add the
  `serial` mark to the respective function:
```python
@pytest.mark.serial
def test_my_heavy_installation(container):
    ...
```

In the example above, the test function `mytest` will only run for the `openjdk:11` container, instead of all the containers for openjdk.

## Running all tests

```ShellSession
$ tox --parallel
```

## Running specific tests

```ShellSession
$ tox -e testname
```

`testname` equals to `python` for the test file named `test_python.py`

This will run _all_ the tests for a language, which could mean multiple stacks.


## Testing on FIPS enabled systems

The base container tests execute a different set of tests on a FIPS enabled
system. Currently, the CI does not run on such a system, so these must be
executed manually. If you do not have access to such a system, you can use a
prebuild vagrant box from the Open Build Service for this.

Install [vagrant](https://www.vagrantup.com/downloads) and run `vagrant up` in
the root directory of this repository. The provisioning script defined in the
`Vagrantfile` will automatically run the base container tests.
