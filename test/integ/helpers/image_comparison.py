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
        # Check both: max difference and percentage of pixels outside tolerance
        diff = np.abs(actual.astype(int) - expected.astype(int))
        max_diff = diff.max()
        pixels_outside_tolerance = np.sum(diff > 2)
        total_pixels = diff.size
        percent_outside = (pixels_outside_tolerance / total_pixels) * 100

        # Pass if max diff <= 2 OR less than 0.5% of pixels are outside tolerance
        if max_diff > 2 and percent_outside > 0.5:
            print(f"Expected shape: {expected.shape}, Actual shape: {actual.shape}")
            print(
                f"Pixels outside tolerance (>2): {pixels_outside_tolerance}/{total_pixels} ({percent_outside:.2f}%)"
            )
            # For debugging: Uncomment to show per-channel differences
            # if len(expected.shape) == 3:
            #     for i, channel in enumerate(['R', 'G', 'B', 'A'][:expected.shape[2]]):
            #         print(f"  {channel} channel max diff: {diff[:,:,i].max()}")
            # For debugging: Uncomment to write the diff image along-side the actual image with _diff suffix
            # diff_img = diff.astype(np.uint8)
            # diff_amplified = np.clip(diff_img * 50, 0, 255).astype(np.uint8)
            # if len(diff_amplified.shape) == 3 and diff_amplified.shape[2] == 4:
            #     diff_amplified[:,:,3] = 255
            # PIL.Image.fromarray(diff_amplified).save(actual_image_directory / f"{image.name}_diff.png")
            # print(f"Diff image saved to {actual_image_directory / f'{image.name}_diff.png'} (amplified 50x)")

            assert (
                False
            ), f"Image {image.name} is not close to the expected image (max diff: {max_diff}, {percent_outside:.2f}% pixels outside tolerance)"
