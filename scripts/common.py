# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import subprocess
import sys

from os import PathLike
from typing import Union, Dict, Optional, List


class BadExitCodeError(Exception):
    pass


class EvaluationBuildError(Exception):
    pass


class UnsupportedOSError(Exception):
    pass


def run(
    cmd: Union[PathLike, str, List[Union[str, PathLike]]],
    cwd: Optional[Union[str, PathLike]] = None,
    env: Optional[Dict[str, str]] = None,
    echo: bool = True,
) -> str:
    if echo:
        sys.stdout.write(f"Running cmd: {cmd}\n")
    shell = not isinstance(cmd, list)
    p = subprocess.Popen(
        cmd, shell=shell, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = p.communicate()
    output = stdout.decode("utf-8") + stderr.decode("utf-8")

    if p.returncode != 0:
        raise BadExitCodeError(
            f"Process '{str(cmd)}' failed with exit code {p.returncode} and output: {output}"
        )

    return output


def get_latest_git_tag(cwd: Optional[Union[PathLike, str]] = None) -> str:
    result = run(["git", "describe", "--tags", "--abbrev=0"], cwd=cwd, echo=False).strip()
    return result


def get_latest_commit_hash(cwd: Optional[Union[PathLike, str]] = None) -> str:
    result = run(["git", "rev-parse", "HEAD"], cwd=cwd, echo=False).strip()
    return result


def get_latest_git_tag_hash(cwd: Optional[Union[PathLike, str]] = None) -> str:
    tag = get_latest_git_tag(cwd)
    result = run(["git", "rev-list", "-n", "1", tag], cwd=cwd, echo=False).strip()
    return result


def get_latest_commit_short_hash(cwd: Optional[Union[PathLike, str]] = None) -> str:
    result = run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd, echo=False).strip()
    return result


def get_version_string(cwd: Optional[Union[PathLike, str]] = None) -> str:
    latest_tag = get_latest_git_tag(cwd)
    latest_commit_hash = get_latest_commit_hash(cwd)
    latest_tag_hash = get_latest_git_tag_hash(cwd)
    if latest_commit_hash == latest_tag_hash:
        return latest_tag
    latest_commit_hash_short = get_latest_commit_short_hash()
    return f"{latest_tag}.{latest_commit_hash_short}"
