# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

#!/usr/bin/env python3
"""Setup runner for Blender integration tests in CodeBuild."""
import argparse
import hashlib
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

BLENDER_VERSIONS = ["4.2.21", "4.5.10", "5.0.1", "5.1.2"]
BLENDER_PYTHON_VERSIONS = {
    "4.2.21": "3.11",
    "4.5.10": "3.11",
    "5.0.1": "3.11",
    "5.1.2": "3.13",
}
USE_PUBLIC_URLS = False

# SHA256 checksums from https://www.blender.org/download/
BLENDER_CHECKSUMS = {
    "4.2.21-linux-x64": "b9ee313018de52697eeabcb76fc2cd6d404dbb670be9b0d3a5847a09ca325981",
    "4.5.10-linux-x64": "198a4248b38899af661aa9241cebd746394eaddbfafbeb53152440de80b118f7",
    "4.2.21-windows-x64": "917254620e2528d032c1c93c149f25f0cfc8ab9b37c9aa117f05fc8eccdc7b24",
    "4.5.10-windows-x64": "ef6d846b8015f47ade6df3f9322ce17419080a5d922fa562b6c966064fe30dce",
    "4.2.21-macos-arm64": "ead53e078ce3102bdc0dc3aa5636b926a82058344c5b8f1bc210b34799c5af1d",
    "4.5.10-macos-arm64": "cf3076fd531e74713f858830b558e71ffae7b26f104608c5c2cb2fc123535f16",
    "5.0.1-linux-x64": "8019580ee1b7262e505f4196a00237ccf743c88d205b38d34201510676e60b09",
    "5.0.1-windows-x64": "921d77f6c505a35b2c2f6e67d4ad1c10b72418338ba0e0d3ea7f582a5e5fe46e",
    "5.0.1-macos-arm64": "102a81ddee5346c96339c6a529069a2d52df05f330eb9bfd431c8dd79fb4afb6",
    "5.1.2-linux-x64": "aaccb355f50183979b698bcce7467103a76261b5fa59f4972295842662a285fb",
    "5.1.2-windows-x64": "345bedea7b0acf7cc9666423d8553f9129622aea34ded65c23e8cb70f83f14ff",
    "5.1.2-macos-arm64": "f104ffee2ba6aee32328e5c203b7e4608d8a1745f7bbcf2766f3b9777e8fbe17",
}


def run(cmd, check=True):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def download_from_s3(s3_path, local_path):
    bucket = os.environ.get("INSTALLER_BUCKET")
    if not bucket:
        print("INSTALLER_BUCKET not set")
        return False
    run(["aws", "s3", "cp", f"s3://{bucket}/{s3_path}", str(local_path), "--no-progress"])
    return True


def verify_checksum(file_path, expected_checksum):
    """Verify SHA256 checksum of downloaded file."""
    print(f"Verifying checksum for {file_path}...")
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    actual = sha256.hexdigest()
    if actual != expected_checksum:
        print("ERROR: Checksum mismatch!")
        print(f"  Expected: {expected_checksum}")
        print(f"  Actual:   {actual}")
        sys.exit(1)

    print("OK Checksum verified")
    return True


def validate_version(version):
    """Validate Blender version string"""
    import re

    if not re.match(r"^\d+\.\d+\.\d+$", version):
        print(f"ERROR: Invalid version format: {version}")
        print("Version must be in format X.Y.Z (e.g., 4.2.12)")
        sys.exit(1)
    return version


def setup_linux(python_version, install_x11=False):
    pkg_mgr = (
        "dnf"
        if subprocess.run(["command", "-v", "dnf"], capture_output=True).returncode == 0
        else "yum"
    )
    run([pkg_mgr, "update", "-y"])

    # Optional, for running tests on a headless runner.
    if install_x11:
        run(
            [
                pkg_mgr,
                "install",
                "-y",
                "mesa-libGL",
                "mesa-libGLU",
                "mesa-libEGL",
                "libglvnd-egl",
                "fontconfig",
                "libxcb",
                "xcb-util-cursor",
                "xcb-util-image",
                "xcb-util-keysyms",
                "xcb-util-renderutil",
                "xcb-util-wm",
                "libxkbcommon-x11",
                "xorg-x11-server-Xvfb",
                "libX11",
                "libXrender",
                "libXi",
                "libXrandr",
                "libXxf86vm",
                "libXfixes",
                "libXcursor",
                "libXinerama",
                "libxkbcommon",
                "libSM",
                "libICE",
                "libXt",
                "libXmu",
            ]
        )
        if run(["pgrep", "Xvfb"], check=False).returncode != 0:
            # Start Xvfb in background
            subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x24"])
            run(["sleep", "2"])
        print("\nXvfb started. Run this before tests:")
        print("  export DISPLAY=:99")

    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        blender_dir = Path(f"/opt/blender-{version}-linux-x64")
        # Marker file indicates successful installation, avoiding redundant reinstalls
        blender_marker = blender_dir / ".installed"

        if blender_marker.exists():
            print(f"Blender {version} already installed")
            continue

        # Lock file prevents concurrent installations that could corrupt the installation
        lock_file = Path(f"/tmp/blender-{version}.lock")
        if lock_file.exists():
            print(f"Waiting for concurrent Blender {version} install...")
            for _ in range(60):
                time.sleep(1)
                if blender_marker.exists():
                    break
            continue

        lock_file.touch()
        try:
            print(f"Installing Blender {version}...")
            blender_archive = Path(f"/tmp/blender-{version}.tar.xz")
            if not USE_PUBLIC_URLS and download_from_s3(
                f"blender/{major_minor}/blender-{version}-linux-x64.tar.xz", blender_archive
            ):
                verify_checksum(blender_archive, BLENDER_CHECKSUMS[f"{version}-linux-x64"])
            elif USE_PUBLIC_URLS:
                run(
                    [
                        "wget",
                        "-q",
                        "-O",
                        str(blender_archive),
                        f"https://download.blender.org/release/Blender{major_minor}/blender-{version}-linux-x64.tar.xz",
                    ]
                )
                verify_checksum(blender_archive, BLENDER_CHECKSUMS[f"{version}-linux-x64"])

            run(["tar", "-xf", str(blender_archive), "-C", "/opt"])
            run(["chmod", "-R", "755", str(blender_dir)])
            blender_marker.touch()
            blender_archive.unlink(missing_ok=True)
        finally:
            lock_file.unlink(missing_ok=True)

    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        submitter_path = Path(f"./DeadlineCloudSubmitter/Submitters/Blender{major_minor}")

        Path(f"{submitter_path}/python").mkdir(parents=True, exist_ok=True)
        run(
            [
                "cp",
                "-r",
                "src/deadline/blender_submitter/addons/",
                f"{submitter_path}/python/addons",
            ]
        )

        run(
            [
                "pip",
                "install",
                "--upgrade",
                "--python-version",
                python_version,
                "--only-binary=:all:",
                "deadline[gui]",
                "blender-qt-stylesheet",
                "-t",
                f"{submitter_path}/python/modules",
            ]
        )

        blender_exe = f"/opt/blender-{version}-linux-x64/blender"
        run(
            [
                blender_exe,
                "--background",
                "--python",
                "./installer/add_submitter_to_pref.py",
                "--",
                "--deadline_cloud_install_path",
                f"{os.getcwd()}/{submitter_path}/python",
            ]
        )


def setup_windows(python_version):
    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        blender_dir = Path(f"C:/Tools/blender-{version}-windows-x64")
        # Marker file indicates successful installation, avoiding redundant reinstalls
        blender_marker = blender_dir / ".installed"

        if blender_marker.exists():
            print(f"Blender {version} already installed")
            continue

        # Lock file prevents concurrent installations that could corrupt the installation
        lock_file = Path(f"C:/Temp/blender-{version}.lock")
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        if lock_file.exists():
            print(f"Waiting for concurrent Blender {version} install...")
            for _ in range(60):
                time.sleep(1)
                if blender_marker.exists():
                    break
            continue

        lock_file.touch()
        try:
            print(f"Installing Blender {version}...")
            blender_zip = Path(f"C:/Tools/blender-{version}.zip")
            blender_zip.parent.mkdir(parents=True, exist_ok=True)

            if not USE_PUBLIC_URLS and download_from_s3(
                f"blender/{major_minor}/blender-{version}-windows-x64.zip", blender_zip
            ):
                verify_checksum(blender_zip, BLENDER_CHECKSUMS[f"{version}-windows-x64"])
            elif USE_PUBLIC_URLS:
                run(
                    [
                        "powershell",
                        "-Command",
                        f"Invoke-WebRequest -Uri 'https://download.blender.org/release/Blender{major_minor}/blender-{version}-windows-x64.zip' -OutFile '{blender_zip}'",
                    ]
                )
                verify_checksum(blender_zip, BLENDER_CHECKSUMS[f"{version}-windows-x64"])

            run(
                [
                    "powershell",
                    "-Command",
                    f"Expand-Archive -Path '{blender_zip}' -DestinationPath 'C:/Tools' -Force",
                ]
            )
            blender_marker.touch()
            blender_zip.unlink(missing_ok=True)
        finally:
            lock_file.unlink(missing_ok=True)

    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        submitter_path = f"DCS\\Blender{major_minor}"

        run(
            [
                "xcopy",
                "/E",
                "/I",
                "src\\deadline\\blender_submitter\\addons",
                f"{submitter_path}\\python\\addons",
            ]
        )

        run(
            [
                "pip",
                "install",
                "--upgrade",
                "--python-version",
                python_version,
                "--only-binary=:all:",
                "deadline[gui]",
                "blender-qt-stylesheet",
                "pywin32",
                "-t",
                f"{submitter_path}\\python\\modules",
            ]
        )

        blender_python_site = f"C:/Tools/blender-{version}-windows-x64/{version.split('.')[0]}.{version.split('.')[1]}/python/lib/site-packages"
        run(
            [
                "pip",
                "install",
                "--upgrade",
                "-r",
                "requirements-integ-testing.txt",
                f"--python-version={python_version}",
                "--only-binary=:all:",
                "--target",
                blender_python_site,
            ]
        )

        cwd = os.getcwd().replace("/", "\\")
        blender_exe = f"C:/Tools/blender-{version}-windows-x64/blender.exe"
        run(
            [
                blender_exe,
                "--background",
                "--python",
                "installer\\add_submitter_to_pref.py",
                "--",
                "--deadline_cloud_install_path",
                f"{cwd}\\{submitter_path}\\python",
            ]
        )


def setup_macos(python_version):
    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        blender_app = Path(f"/Applications/Blender-{version}.app")
        # Marker file indicates successful installation, avoiding redundant reinstalls
        # Stored outside app directory to prevent corruption
        blender_marker = Path(
            f"~/Library/Application Support/.blender-{version}-installed"
        ).expanduser()
        blender_marker.parent.mkdir(parents=True, exist_ok=True)

        if blender_marker.exists():
            print(f"Blender {version} already installed")
            continue

        # Lock file prevents concurrent installations that could corrupt the installation
        lock_file = Path(f"/tmp/blender-{version}.lock")
        if lock_file.exists():
            print(f"Waiting for concurrent Blender {version} install...")
            for _ in range(60):
                time.sleep(1)
                if blender_marker.exists():
                    break
            continue

        lock_file.touch()
        try:
            print(f"Installing Blender {version}...")
            blender_dmg = Path(f"/tmp/blender-{version}.dmg")

            if not USE_PUBLIC_URLS and download_from_s3(
                f"blender/{major_minor}/blender-{version}-macos-arm64.dmg", blender_dmg
            ):
                verify_checksum(blender_dmg, BLENDER_CHECKSUMS[f"{version}-macos-arm64"])
            elif USE_PUBLIC_URLS:
                run(
                    [
                        "curl",
                        "-L",
                        "-o",
                        str(blender_dmg),
                        f"https://download.blender.org/release/Blender{major_minor}/blender-{version}-macos-arm64.dmg",
                    ]
                )
                verify_checksum(blender_dmg, BLENDER_CHECKSUMS[f"{version}-macos-arm64"])

            run(["hdiutil", "attach", str(blender_dmg)])
            run(["sudo", "rm", "-rf", str(blender_app)], check=False)
            run(["sudo", "cp", "-R", "/Volumes/Blender/Blender.app", str(blender_app)])
            run(["hdiutil", "detach", "/Volumes/Blender"])

            blender_marker.touch()
            blender_dmg.unlink(missing_ok=True)
        finally:
            lock_file.unlink(missing_ok=True)

    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        submitter_path = Path(f"./DeadlineCloudSubmitter/Submitters/Blender{major_minor}")

        Path(f"{submitter_path}/python").mkdir(parents=True, exist_ok=True)
        run(
            [
                "cp",
                "-r",
                "src/deadline/blender_submitter/addons/",
                f"{submitter_path}/python/addons",
            ]
        )

        run(
            [
                "pip",
                "install",
                "--upgrade",
                "--python-version",
                python_version,
                "--only-binary=:all:",
                "deadline[gui]",
                "blender-qt-stylesheet",
                "-t",
                f"{submitter_path}/python/modules",
            ]
        )

        blender_exe = f"/Applications/Blender-{version}.app/Contents/MacOS/Blender"
        run(
            [
                blender_exe,
                "--background",
                "--python",
                "./installer/add_submitter_to_pref.py",
                "--",
                "--deadline_cloud_install_path",
                f"{os.getcwd()}/{submitter_path}/python",
            ]
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup Blender test environment")
    parser.add_argument(
        "--public-urls", action="store_true", help="Download from public URLs instead of S3"
    )
    parser.add_argument(
        "--versions", nargs="+", help="Blender versions to install (e.g., 4.5.4 4.2.12)"
    )
    parser.add_argument(
        "--python-version", help="Python version to use for pip installs (e.g., 3.11)"
    )
    parser.add_argument(
        "--install-x11",
        action="store_true",
        help="Install X11 libraries and start Xvfb (Linux only)",
    )
    args = parser.parse_args()

    USE_PUBLIC_URLS = args.public_urls
    if args.versions:
        BLENDER_VERSIONS = [validate_version(v) for v in args.versions]

    # Validate all versions have checksums
    for version in BLENDER_VERSIONS:
        system_suffix = {"Linux": "linux-x64", "Windows": "windows-x64", "Darwin": "macos-arm64"}
        key = f"{version}-{system_suffix.get(platform.system())}"
        if key not in BLENDER_CHECKSUMS:
            print(f"ERROR: No checksum available for {key}")
            sys.exit(1)

    # Use provided python version or infer from first Blender version
    if args.python_version:
        python_version = args.python_version
    else:
        python_version = BLENDER_PYTHON_VERSIONS.get(BLENDER_VERSIONS[0], "3.11")

    system = platform.system()
    print(f"Setting up {system} with Blender {', '.join(BLENDER_VERSIONS)}")
    print(f"Using {'public URLs' if USE_PUBLIC_URLS else 'S3 bucket'}")
    print(f"Python version: {python_version}")

    if system == "Linux":
        setup_linux(python_version=python_version, install_x11=args.install_x11)
    elif system == "Windows":
        setup_windows(python_version=python_version)
    elif system == "Darwin":
        setup_macos(python_version=python_version)
    else:
        raise OSError(f"Unsupported OS: {system}")
    print("Setup complete!")
