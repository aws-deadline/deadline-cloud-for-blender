# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Download a Blender release from download.blender.org and verify its SHA-256.

The expected digests come from pipeline/setup-runner.py, so the GUI tests and the CodeBuild
integration tests trust exactly the same installers. A version without a digest there can't be
downloaded: add its digest to setup-runner.py first.

Usage: python test/integ_gui/fetch_blender.py <version> <linux-x64|windows-x64|macos-arm64> <file>
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import time
import urllib.request
from pathlib import Path

SETUP_RUNNER = Path(__file__).resolve().parents[2] / "pipeline" / "setup-runner.py"
ARCHIVE_EXTENSIONS = {"linux-x64": "tar.xz", "windows-x64": "zip", "macos-arm64": "dmg"}


def _load_checksums() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("setup_runner", SETUP_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SETUP_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BLENDER_CHECKSUMS


def _download(url: str, dest: Path, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response, dest.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            return
        except OSError as e:
            if attempt == attempts:
                raise
            print(f"Download attempt {attempt} failed ({e}); retrying", flush=True)
            time.sleep(5 * attempt)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="Blender version, e.g. 5.2.1")
    parser.add_argument("platform", choices=sorted(ARCHIVE_EXTENSIONS))
    parser.add_argument("output", type=Path, help="Where to write the downloaded archive")
    args = parser.parse_args()

    key = f"{args.version}-{args.platform}"
    expected = _load_checksums().get(key)
    if expected is None:
        print(f"No SHA-256 for {key} in {SETUP_RUNNER}; add it there first.", file=sys.stderr)
        return 1

    major_minor = ".".join(args.version.split(".")[:2])
    url = (
        f"https://download.blender.org/release/Blender{major_minor}/"
        f"blender-{args.version}-{args.platform}.{ARCHIVE_EXTENSIONS[args.platform]}"
    )
    print(f"Downloading {url}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _download(url, args.output)

    actual = _sha256(args.output)
    if actual != expected:
        args.output.unlink()
        print(f"SHA-256 mismatch for {url}: expected {expected}, got {actual}", file=sys.stderr)
        return 1
    print(f"Verified SHA-256 {actual}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
