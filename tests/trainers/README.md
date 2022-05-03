BCI tests modules
=================

Description
-----------

This directory contains modules and files that shall be copied into the container under test, for the execution of specific exercises and examples during the BCI validation .

The copy from the test server to the container can be done in two main ways:


1. Copy at build time, creating, in the test\_testname.py header, the content of a proper Dockerfile as a string, including COPY and any other command needed to the container preparation

:..

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


Then we parametrize the new container for each test and assign it to the auto_container_per_test fixtures, adding this last as input parameter of the test;

:..

    @pytest.mark.parametrize("auto_container_per_test", [CONTAINER_IMAGES_NEW], indirect=True)
    def test_ testname(auto_container_per_test, ...):
        ...


In the test code we can run commands in the new container using the testinfra commands (See <https://testinfra.readthedocs.io/en/latest/modules.html>).

I.e.:

:..

    auto_container_per_test.connection.run_expect([0], "python3 filename.py")


2. Copy local files into the running container, using the 'podman|docker' cp command, via testinfra:

:..

    def test_<nnn>(auto_container_per_test, host, container_runtime):

        CID = auto_container_per_test.container_id

        host.run_expect( [0],
            f"{container_runtime.runner_binary} cp {DIR}/{FILE}  {CID}:{CDIR}")


Tests for BCI python
--------------------

1. Communication examples: 

Module to check communication capabilities with python. 

We use the wget library to get a specific file from a remote url.

The get_file_www function input parameters are: (1) "URL/FIL" , (2) "DIR", where:

- URL : the http remote url
- FIL : the remote file to get
- DIR : the directory in the container receiving FIL 

Expected for this test: FIL present in DIR.


2. Tensorflow examples:

This is a pyhton training module making use of tensorflow library and some related tutorials under Apache license. See the attached tensorflow_examples.LICENSE file.

The tensorflow_example_1 original code is available here: 
<https://github.com/tensorflow/docs/blob/master/site/en/tutorials/quickstart/beginner.ipynb>

This function, using the Tensorflow library, trains a machine learning model and evaluates accuracy:

- Load a prebuilt dataset with the Keras API
- Build a neural network ML model that classifies images
- Trains this neural network
- Evaluates the accuracy of the model

Expected for this test: accuracy greather than 0.9 and loss lower than 0.1.

