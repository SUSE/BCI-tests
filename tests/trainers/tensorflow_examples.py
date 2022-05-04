"""Basic tests for the Python base container images,based on tensorflow library.
Find a description in the README file
"""

import tensorflow as tf


def tensorflow_example_1():
    """ Train a machine learning model using a prebuilt dataset.
    More information available in the README file, Tensorflow section:
    """
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

    # The value of the loss before model trained is high > 1
    lo_initial = loss_fn(y_train[:1], predictions).numpy()

    # configure and compile the model
    model.compile(optimizer="adam", loss=loss_fn, metrics=["accuracy"])

    # adjust your model parameters and minimize the loss
    model.fit(x_train, y_train, epochs=5)

    # get the model performance of loss and accuracy
    lo, ac = model.evaluate(x_test, y_test, verbose=2)

    # model to return a probability
    probability_model = tf.keras.Sequential([model, tf.keras.layers.Softmax()])

    probability_model(x_test[:5])

    print(f"loss initial:{lo_initial},loss final:{lo},accuracy:{ac}")

    if lo_initial > 1.0 and lo < 0.1 and ac > 0.9:
        print(f"PASS: loss,accuracy good")
    else:
        # print ("FAIL")
        raise RuntimeError("FAIL: loss,accuracy not good")


if __name__ == "__main__":
    tensorflow_example_1()
