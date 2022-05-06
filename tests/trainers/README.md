BCI tests modules
=================

Description
-----------

This directory contains modules and files that shall be copied into the container under test, for the execution of specific exercises and examples during the BCI validation .

See the pytest_container/source/usage.rst documentation about the _copy to containers_.


Tests for BCI python
--------------------

1. Communication examples: 

Module to check communication capabilities of python functionalities. 

The *get_file_www* function test that the python _wget_ [library](https://pypi.org/project/wget/) is able to fetch files from a webserver.

We use the _download_ method to get a specific file from a remote url.

Input parameters of this function are: (1) "URL/FIL" , (2) "DIR", where:

- URL : the http remote url
- FIL : the remote file to get
- DIR : the directory in the container receiving FIL 

Expected for this test: FIL present in DIR.


1. Tensorflow examples:

This is a pyhton training module making use of tensorflow library and some related tutorials, under Apache License.

The *tensorflow_example_1* function is derived from the code in the 'TensorFlow 2 - quickstart for beginners' [tutorial](https://github.com/tensorflow/docs/blob/master/site/en/tutorials/quickstart/beginner.ipynb)

This function, using the Tensorflow library, trains a machine learning model and evaluates accuracy:

- Load a ML model using a prebuilt dataset with the Keras API
- Build a neural network ML model that classifies images
- Trains this neural network
- Evaluates the accuracy of the model

Expected for this test: accuracy greather than 0.9 and loss lower than 0.1.
