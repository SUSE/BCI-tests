# Container testing

## Adding tests

1. Find container name
2. Add it into `tox.ini` in envname
3. Create a file named `test_<containername>.py`
4. Add your tests there based on [testinfra](https://testinfra.readthedocs.io/en/latest/modules.html)

## Running all tests

tox --parallel

## Running specific tests

tox -e `testname`. `testname` equals to `python39` for the test file `test_python39.py`