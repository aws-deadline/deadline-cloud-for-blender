# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
from pathlib import Path

import PyOpenColorIO as ocio


def get_ocio_path() -> str:
    return os.environ["OCIO"] if "OCIO" in os.environ else ""


def get_ocio_config(filename: str) -> ocio.Config:
    return ocio.Config.CreateFromFile(filename)


def get_ocio_referenced_dirs(config: ocio.Config) -> list[str]:
    """
    Given an OCIO Config object, parse its `search_path` attribute and
    return a list of referenced directories.
    """

    path_list = []
    if config.getSearchPath():
        for path in config.getSearchPaths():
            # Paths may be absolute or relative to the config file.
            if not Path(path).is_absolute():
                path = Path.joinpath(Path(os.path.dirname(get_ocio_path())), path)

            path_list.append(path)

    return path_list
