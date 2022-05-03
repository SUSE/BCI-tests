"""Basic tests for the Python base container images,based on tensorflow library.
Find a description in the README file
"""

import tensorflow as tf


def tensorflow_example_1():
    # Train a machine learning model using a prebuilt dataset with the Keras API.
    #
    # Original tutorial from the TensorFlow 2 quickstart for beginners link:
    # https://github.com/tensorflow/docs/blob/master/site/en/tutorials/quickstart/beginner.ipynb
    #
    # @title Licensed under the Apache License, Version 2.0 (the "License");
    # you may not use this file except in compliance with the License.
    # https://www.apache.org/licenses/LICENSE-2.0
    #

    print("TensorFlow version:", tf.__version__)

    # Load a dataset
    mnist = tf.keras.datasets.mnist

    (x_train, y_train), (x_test, y_test) = mnist.load_data()
    x_train, x_test = x_train / 255.0, x_test / 255.0

    # Build a machine learning model
    model = tf.keras.models.Sequential(
        [
            tf.keras.layers.Flatten(input_shape=(28, 28)),
            tf.keras.layers.Dense(128, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(10),
        ]
    )

    #  the model returns a vector of logits or log-odds scores, one for each class
    predictions = model(x_train[:1]).numpy()

    # converts these logits to probabilities for each class:
    tf.nn.softmax(predictions).numpy()

    # Define a loss function for training
    loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

    loss_fn(y_train[:1], predictions).numpy()

    # configure and compile the model
    model.compile(optimizer="adam", loss=loss_fn, metrics=["accuracy"])

    # adjust your model parameters and minimize the loss
    model.fit(x_train, y_train, epochs=5)

    # checks the model performance
    lo, ac = model.evaluate(x_test, y_test, verbose=2)

    # model to return a probability
    probability_model = tf.keras.Sequential([model, tf.keras.layers.Softmax()])

    probability_model(x_test[:5])

    print(f"loss:{lo},accuracy:{ac}")

    if lo < 0.1 and ac > 0.9:
        print(f"PASS: loss,accuracy good")
    else:
        # print ("FAIL")
        raise Exception("FAIL: loss,accuracy not good")


if __name__ == "__main__":
    tensorflow_example_1()
