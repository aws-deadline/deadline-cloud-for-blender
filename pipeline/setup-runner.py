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

BLENDER_VERSIONS = ["4.2.12", "4.5.4"]
BLENDER_PYTHON_VERSIONS = {
    "4.2.12": "3.11",
    "4.5.4": "3.11",
}
USE_PUBLIC_URLS = False

# SHA256 checksums from https://www.blender.org/download/
BLENDER_CHECKSUMS = {
    "4.2.12-linux-x64": "953717011e00a21bfd4ccf0e8af0d901b4c3ef09c48f14c16a18c146d858bcf7",
    "4.5.4-linux-x64": "2e6ef8e99fc36327270429ddc8e7bad2859dd878a5a137d2e0bf0f02f6792505",
    "4.2.12-windows-x64": "d7b77bf3a925722be87e5b5e429b584d7baa3bcc82579afa7952fc1f8c19d2e1",
    "4.5.4-windows-x64": "0de55df1d99e4e7152605022cb648e795d5d49209c5c5c4889e1a19fb401a054",
    "4.2.12-macos-arm64": "810bc64b89af7f9028b9d7544a34f32ad900ac6d913fd2f288895f10dc6c2527",
    "4.5.4-macos-arm64": "7d6bd807563f0af65735cf9e21b788f6ac78bc5ceb87b96c424459785a13cd60",
}


def run(cmd, shell=False, check=True):
    print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    result = subprocess.run(cmd, shell=shell)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def download_from_s3(s3_path, local_path):
    bucket = os.environ.get("DEPENDENCY_BUCKET")
    if not bucket:
        print("DEPENDENCY_BUCKET not set")
        return False
    run(["aws", "s3", "cp", f"s3://{bucket}/{s3_path}", str(local_path), "--no-progress"])
    return True


def verify_checksum(file_path, expected_checksum):
    """Verify SHA256 checksum of downloaded file."""
    if not USE_PUBLIC_URLS:
        return True

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


def setup_linux(python_version, install_x11=False):
    pkg_mgr = (
        "dnf"
        if subprocess.run("command -v dnf", shell=True, capture_output=True).returncode == 0
        else "yum"
    )
    run(f"{pkg_mgr} update -y", shell=True)

    if install_x11:
        run(
            f"{pkg_mgr} install -y mesa-libGL mesa-libGLU mesa-libEGL libglvnd-egl fontconfig libxcb xcb-util-cursor xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm libxkbcommon-x11 xorg-x11-server-Xvfb libX11 libXrender libXi libXrandr libXxf86vm libXfixes libXcursor libXinerama libxkbcommon libSM libICE libXt libXmu",
            shell=True,
        )
        if run("pgrep Xvfb", shell=True, check=False).returncode != 0:
            run("Xvfb :99 -screen 0 1024x768x24 &", shell=True)
            run("sleep 2", shell=True)
        print("\nXvfb started. Run this before tests:")
        print("  export DISPLAY=:99")

    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        blender_dir = Path(f"/opt/blender-{version}-linux-x64")
        blender_marker = blender_dir / ".installed"

        if blender_marker.exists():
            print(f"Blender {version} already installed")
            continue

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
                f"blender/blender-{version}-linux-x64.tar.xz", blender_archive
            ):
                pass
            elif USE_PUBLIC_URLS:
                run(
                    f"wget -q -O {blender_archive} https://download.blender.org/release/Blender{major_minor}/blender-{version}-linux-x64.tar.xz",
                    shell=True,
                )
                verify_checksum(blender_archive, BLENDER_CHECKSUMS[f"{version}-linux-x64"])

            run(f"tar -xf {blender_archive} -C /opt", shell=True)
            run(f"chmod -R 755 {blender_dir}", shell=True)
            blender_marker.touch()
            blender_archive.unlink(missing_ok=True)
        finally:
            lock_file.unlink(missing_ok=True)

    print("Installing Blender submitter...")
    run("hatch build", shell=True)

    submitter_path = Path("./DeadlineCloudSubmitter")
    if submitter_path.exists():
        run(f"rm -rf {submitter_path}", shell=True, check=False)

    Path("./DeadlineCloudSubmitter/Submitters/Blender/python").mkdir(parents=True, exist_ok=True)
    run(
        "cp -r src/deadline/blender_submitter/addons/ ./DeadlineCloudSubmitter/Submitters/Blender/python/addons",
        shell=True,
    )

    run(
        f'pip install --upgrade --python-version {python_version} --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ./DeadlineCloudSubmitter/Submitters/Blender/python/modules',
        shell=True,
    )

    for version in BLENDER_VERSIONS:
        blender_exe = f"/opt/blender-{version}-linux-x64/blender"
        run(
            f"{blender_exe} --background --python ./installer/add_submitter_to_pref.py -- --deadline_cloud_install_path $(pwd)/DeadlineCloudSubmitter/Submitters/Blender/python",
            shell=True,
        )


def setup_windows(python_version):
    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        blender_dir = Path(f"C:/Tools/blender-{version}-windows-x64")
        blender_marker = blender_dir / ".installed"

        if blender_marker.exists():
            print(f"Blender {version} already installed")
            continue

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
                f"blender/blender-{version}-windows-x64.zip", blender_zip
            ):
                pass
            elif USE_PUBLIC_URLS:
                run(
                    f"powershell -Command \"Invoke-WebRequest -Uri 'https://download.blender.org/release/Blender{major_minor}/blender-{version}-windows-x64.zip' -OutFile '{blender_zip}'\"",
                    shell=True,
                )
                verify_checksum(blender_zip, BLENDER_CHECKSUMS[f"{version}-windows-x64"])

            run(
                f"powershell -Command \"Expand-Archive -Path '{blender_zip}' -DestinationPath 'C:/Tools' -Force\"",
                shell=True,
            )
            blender_marker.touch()
            blender_zip.unlink(missing_ok=True)
        finally:
            lock_file.unlink(missing_ok=True)

    print("Installing Blender submitter...")
    run("hatch build", shell=True)

    submitter_path = Path("./DeadlineCloudSubmitter")
    if submitter_path.exists():
        run("rmdir /s /q DeadlineCloudSubmitter", shell=True, check=False)

    Path("./DeadlineCloudSubmitter/Submitters/Blender/python").mkdir(parents=True, exist_ok=True)
    run(
        "xcopy /E /I src\\deadline\\blender_submitter\\addons DeadlineCloudSubmitter\\Submitters\\Blender\\python\\addons",
        shell=True,
    )

    run(
        f'pip install --upgrade --python-version {python_version} --only-binary=:all: "deadline[gui]" blender-qt-stylesheet pywin32 -t DeadlineCloudSubmitter\\Submitters\\Blender\\python\\modules',
        shell=True,
    )

    for version in BLENDER_VERSIONS:
        blender_python_site = f"C:/Tools/blender-{version}-windows-x64/{version.split('.')[0]}.{version.split('.')[1]}/python/lib/site-packages"
        run(
            f"pip install --upgrade -r requirements-integ-testing.txt --python-version={python_version} --only-binary=:all: --target {blender_python_site}",
            shell=True,
        )

    cwd = os.getcwd().replace("/", "\\")
    for version in BLENDER_VERSIONS:
        blender_exe = f"C:/Tools/blender-{version}-windows-x64/blender.exe"
        run(
            f'"{blender_exe}" --background --python installer\\add_submitter_to_pref.py -- --deadline_cloud_install_path {cwd}\\DeadlineCloudSubmitter\\Submitters\\Blender\\python',
            shell=True,
        )


def setup_macos(python_version):
    for version in BLENDER_VERSIONS:
        major_minor = ".".join(version.split(".")[:2])
        blender_app = Path(f"/Applications/Blender-{version}.app")

        print(f"Installing Blender {version}...")
        blender_dmg = Path(f"/tmp/blender-{version}.dmg")

        if not USE_PUBLIC_URLS and download_from_s3(
            f"blender/blender-{version}-macos-arm64.dmg", blender_dmg
        ):
            pass
        elif USE_PUBLIC_URLS:
            run(
                f"curl -L -o {blender_dmg} https://download.blender.org/release/Blender{major_minor}/blender-{version}-macos-arm64.dmg",
                shell=True,
            )
            verify_checksum(blender_dmg, BLENDER_CHECKSUMS[f"{version}-macos-arm64"])

        run(f"hdiutil attach {blender_dmg}", shell=True)
        run(f"sudo rm -rf {blender_app}", shell=True, check=False)
        run(f"sudo cp -R /Volumes/Blender/Blender.app {blender_app}", shell=True)
        run("hdiutil detach /Volumes/Blender", shell=True)

        blender_dmg.unlink(missing_ok=True)

    print("Installing Blender submitter...")
    run("hatch build", shell=True)

    submitter_path = Path("./DeadlineCloudSubmitter")
    if submitter_path.exists():
        run(f"rm -rf {submitter_path}", shell=True, check=False)

    Path("./DeadlineCloudSubmitter/Submitters/Blender/python").mkdir(parents=True, exist_ok=True)
    run(
        "cp -r src/deadline/blender_submitter/addons/ ./DeadlineCloudSubmitter/Submitters/Blender/python/addons",
        shell=True,
    )

    run(
        f'pip install --upgrade --python-version {python_version} --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ./DeadlineCloudSubmitter/Submitters/Blender/python/modules',
        shell=True,
    )

    for version in BLENDER_VERSIONS:
        blender_exe = f"/Applications/Blender-{version}.app/Contents/MacOS/Blender"
        run(
            f"{blender_exe} --background --python ./installer/add_submitter_to_pref.py -- --deadline_cloud_install_path $(pwd)/DeadlineCloudSubmitter/Submitters/Blender/python",
            shell=True,
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
        BLENDER_VERSIONS = args.versions

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
