# Container testing

## Adding tests

1. Find container "type" or "language"
2. Add it into `tox.ini` in envlist, if not present.
3. Create or update a file named `test_<container_type>.py` (for example, `test_python.py`)
4. Add your tests there based on [testinfra](https://testinfra.readthedocs.io/en/latest/modules.html)
5. Ensure the container data is up to date by updating `matryoshka_tester/data.py`.

## Adding containers in 
## Running all tests

tox --parallel

## Running specific tests

`tox -e testname`. `testname` equals to `python` for the test file `test_python.py`

This will run _all_ the tests for a language, which could mean multiple stacks.