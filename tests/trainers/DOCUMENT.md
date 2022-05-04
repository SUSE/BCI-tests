BCI tests help
==============

Copy files to containers
------------------------

Consider we a directory DIR containing modules and files that shall be copied into the container under test, for the execution of specific exercises and examples during the BCI validation.

The copy from the test server to the container can be done in two main ways:


1. **Copy at build time in a derived image** 

Create, in the test\_testname.py header, the content of a proper Dockerfile as a string, including COPY and any other command needed to the container preparation

```python
        DIR = "directory"
        FILE = "filename.py"
        CDIR = "container-dir"

        DOCKERFIL = f"""
        ...
        COPY {DIR}/{FILE}  {CDIR}
        ...
        """

        CONTAINER1 = pytest.param(
            DerivedContainer(
                base=container_from_pytest_param(CONTAINER),
                containerfile=DOCKERFIL,
            ),
            marks=CONTAINER.marks,
        )

        CONTAINER_IMAGES_NEW = [ CONTAINER1, ... ]
```

Then we parametrize the new container for each test and assign it to the auto_container_per_test fixtures, adding this last as input parameter of the test;

```python

        @pytest.mark.parametrize("auto_container_per_test", [CONTAINER_IMAGES_NEW], indirect=True)
        def test_ testname(auto_container_per_test, ...):
            ...
```

A derived container is built and started when this fixture is invoked.

In the test code we can run commands in the new container using the testinfra commands (See <https://testinfra.readthedocs.io/en/latest/modules.html>).

I.e.:

```python
        auto_container_per_test.connection.run_expect([0], f"python3 {CDIR}/{FILE}")
```

1. **Copy at runtime in the running container** 

The main step are:

- pass to the test the parameters: container, host, container_runtime,
- save the container id,
- Use the 'podman|docker' cp command, via testinfra

Here is a snippet as example:
```python
        def test_<nnn>(container, host, container_runtime):

            CID = container.container_id

            host.run_expect( [0],
                f"{container_runtime.runner_binary} cp {DIR}/{FILE}  {CID}:{CDIR}")
```
