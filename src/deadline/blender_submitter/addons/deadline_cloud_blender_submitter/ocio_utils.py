# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
from pathlib import Path

import PyOpenColorIO as ocio


def get_ocio_path() -> str:
    return os.environ["OCIO"] if "OCIO" in os.environ else ""


def get_ocio_config(filename: str) -> ocio.Config:
    return ocio.Config.CreateFromFile(filename)


def get_ocio_referenced_dirs(config: ocio.Config, config_path: str = "") -> list[str]:
    """
    Given an OCIO Config object, parse its `search_path` attribute and
    return a list of referenced directories.

    Relative search paths are resolved against ``config_path``'s directory (the
    directory of the config file the search paths belong to), falling back to
    the active ``$OCIO`` config directory when ``config_path`` is not given.
    """
    base_dir = os.path.dirname(config_path or get_ocio_path())

    path_list = []
    if config.getSearchPath():
        for path in config.getSearchPaths():
            # Paths may be absolute or relative to the config file.
            if not Path(path).is_absolute():
                path = Path.joinpath(Path(base_dir), path)

            path_list.append(path)

    return path_list


def get_current_ocio_referenced_dirs(ocio_path: str = "") -> list[str]:
    """Return the directories referenced by an OCIO config, if any.

    Reads the OCIO config at ``ocio_path`` (defaulting to the active config via
    the ``OCIO`` env var when not given) and returns the directories it
    references, so they can be added as job input attachments. Empty when no
    OCIO config is set. Shared by the GUI submitter and the unified API path so
    both attach the same OCIO-referenced directories.
    """
    ocio_path = ocio_path or get_ocio_path()
    if not ocio_path:
        return []
    config = get_ocio_config(ocio_path)
    # Resolve relative search paths against this config's own directory, not
    # necessarily the $OCIO one (they can differ when a caller passes an
    # explicit ocio_path).
    return [str(path) for path in get_ocio_referenced_dirs(config, ocio_path)]
