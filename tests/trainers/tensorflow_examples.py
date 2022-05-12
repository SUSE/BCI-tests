"""Basic tests for the Python base container images,based on tensorflow library,
and related tutorials, under Apache License.
"""
import tensorflow as tf


def tensorflow_example_1():
    """This function test that the TF library in the BCI is able to
    train a machine learning model and perform an evaluation:

    It is derived from the code in the 'TensorFlow 2 - quickstart for beginners' `tutorial <https://github.com/tensorflow/docs/blob/master/site/en/tutorials/quickstart/beginner.ipynb>`_

    The procedure is:

    - Load a ML model using a prebuilt dataset with the Keras API
    - Build a neural network ML model that classifies images
    - Trains this neural network
    - Evaluates the accuracy of the model

    Expected for this test: accuracy greater than 0.9 and final loss lower than 0.1.
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

    # The value of the loss before model trained is high,meaning >1.
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
        # ("FAIL")
        raise RuntimeError("FAIL: loss,accuracy not good")


if __name__ == "__main__":
    tensorflow_example_1()
