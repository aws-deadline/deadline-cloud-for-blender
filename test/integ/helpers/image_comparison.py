# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path

import PIL.Image

import numpy as np


def assert_all_images_close(
    expected_image_directory: Path,
    actual_image_directory: Path,
):
    """Assert that all images in the expected directory are close to the images in the actual directory.

    Args:
        expected_image_directory: The directory containing the expected images.
        actual_image_directory: The directory containing the actual images.
    """
    for image in (expected_image_directory).iterdir():
        if not image.is_file() or image.name == ".DS_Store":
            continue

        # Open the two image files with Pillow https://pillow.readthedocs.io/en/stable/index.html
        # and put them in numpy arrays. Pillow doesn't have a good built-in way to do image comparison
        # with tolerance.
        try:
            actual = np.asarray(PIL.Image.open(actual_image_directory / image.name))
        except FileNotFoundError:
            actual_images_per_line = "\n".join(
                sorted(p.name for p in actual_image_directory.iterdir())
            )
            raise AssertionError(
                f"Image {image.name} not found in {actual_image_directory}. Contents:\n{actual_images_per_line}"
            ) from None
        expected = np.asarray(PIL.Image.open(image))

        # Check that the two images are the same within a tolerance.
        # It's normal for there to be noise in an output image, so it is unlikely that two
        # renders will be exactly the same.
        if not np.allclose(actual, expected, atol=2):
            # For debugging: Uncomment to write the diff image along-side the expected image with _diff suffix
            # diff = actual - expected
            # PIL.Image.fromarray(diff).save(expected_image_directory / f"{image.name}_diff.png")

            assert False, f"Image {image.name} is not close to the expected image"
