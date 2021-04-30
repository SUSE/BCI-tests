# Container testing

## Requirements

You need the following CLIs installed on your machine:
docker, tox, pack, git

## Adding new containers and their tests

1. Find container "type" or "language"
2. Add it into `tox.ini` in envlist, if not present.
3. Create or update a file named `test_<container_type>.py` (for example, `test_python.py`)
4. Add your tests there based on [testinfra](https://testinfra.readthedocs.io/en/latest/modules.html)
5. Ensure the container data is up to date by updating `matryoshka_tester/data.py`.

## Extending coverage/Writing tests for existing containers

Just use testinfra documentation (linked above). It should be
easy.

You can use the convenience tools from conftest:

* If you are using the "container" fixture, your test will auto generate the right tests for _all_ the versions of your language. This is auto loaded, and doesn't need anything from your side except using the keyword "container"
* If you want to _skip_ some of those tests, use the decorator named `restrict_to_version`. This decorator accepts a list of strings matching the versions from `data.py`. To use it, add first `from conftest import restrict_to_version` and then wrap your code like this (assuming openjdk here):
```
@restrict_to_version(['11])
def mytest(container):
    pass
```

## Running all tests

tox --parallel

## Running specific tests

```
tox -e testname
```

`testname` equals to `python` for the test file named `test_python.py`

This will run _all_ the tests for a language, which could mean multiple stacks.
