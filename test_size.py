from typing import Union

import pytest


@pytest.mark.parametrize(
    "image_name,size_mb",
    [
        ("bci/base", 100),
        pytest.param(
            "bci/golang:1.16",
            1000,
            marks=pytest.mark.xfail(reason="The golang container is too fat"),
        ),
        pytest.param(
            "bci/golang:1.15",
            1000,
            marks=pytest.mark.xfail(reason="The golang container is too fat"),
        ),
        pytest.param(
            "bci/golang:1.14",
            1000,
        ),
        pytest.param(
            "bci/openjdk-devel",
            400,
        ),
        pytest.param(
            "bci/openjdk:",
            320,
        ),
    ],
)
def test_size(
    host, container_runtime, image_name: str, size_mb: Union[float, int]
) -> None:
    """Test that the size of a container image is below a certain threshold.

    Parameters:
    * image_name: regex to identify your container image
    * size_mb: the maximum size of the image in MB
    """
    image_size_lines = list(
        filter(
            None,
            host.run_expect(
                [0],
                f"{container_runtime.runner_binary} images "
                + f"--filter reference={image_name} "
                + '--format "{{ .Repository }}:{{ .Tag }} {{ .Size }}"',
            ).stdout.split("\n"),
        )
    )

    assert (
        len(image_size_lines) > 0
    ), f"found no images matching the name {image_name}"

    for line in image_size_lines:
        image_url, size, unit = line.split(" ")
        assert unit in ("MB", "GB"), f"invalid container size unit {unit}"
        multiplier = 2 ** 20 if unit == "MB" else 2 ** 30

        assert float(size) * multiplier < size_mb * 2 ** 20, (
            f"image {image_url} exceeds size limit of {size_mb} MB: "
            + "{size} {unit}"
        )
