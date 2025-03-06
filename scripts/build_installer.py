# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Script to create platform-specific Deadline submission installers"""
import argparse
import os
import platform
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple, Optional

# If the InstallBuilder version is being changed, please ensure the archives are in a "flattened" structure.
#
# The InstallBuilder archives listed below must be in a "flattened" file structure, where the
# actual install files are at the root of the archive. The structure of the root of the archive
# should contain the following: (relevant output from `ls -l`)
# drwxr-xr-x autoupdate
# drwxr-xr-x bin
# drwxr-xr-x demo
# drwxr-xr-x docs
# drwxr-xr-x output
# drwxr-xr-x paks
# drwxr-xr-x projects
# drwxr-xr-x tools
# -rwx------ uninstall (.app folder on Mac, .exe on Windows)
#
# Since the BitRock license ("license.xml" file) needs to be put at the root of the InstallBuilder
# installation folder, having a flattened structure makes this location consistent across platforms.
# See https://installbuilder.com/docs/installbuilder-userguide/_installation_and_getting_started.html
#
# For example, the InstallBuilder 19.8.0 archives originally had the installation files one folder deeper
# from the root of the archive for Windows and Linux:
# - Windows: <archive-root>/BitRock InstallBuilder Professional 19.8.0/<files>
# - Linux: <archive-root>/installbuilder-19.8.0/<files>
# - Mac: <archive-root>/<files>
# In this case, the Windows and Linux archives were changed to be "flattened" like the Mac one above.
INSTALL_BUILDER = {
    "archive": "install_builder/VMware-InstallBuilder-Professional-linux.tar.gz",
    "command": Path("bin") / "builder",
}

# This is derived from <installerFilename> in DeadlineCloudForBlenderSubmitter.xml
# See "Supported Platforms" table in https://releases.installbuilder.com/installbuilder/docs/installbuilder-userguide.html
INSTALLER_FILENAME_TEMPLATE = "DeadlineCloudForBlenderSubmitter-{platform}-installer.{ext}"

# This is the directory containing the InstallBuilder root .xml component.
# All file paths in the InstallBuilder component files are relative to this directory
INSTALL_BUILDER_PROJECT_ROOT = Path(__file__).absolute().parent.parent / "install_builder"
INSTALLER_ROOT = Path(__file__).absolute().parent.parent / "installer"
INSTALLER_TEMPLATE = "DeadlineCloudForBlenderSubmitter.xml"
EVALUATION_VERSION_STRING = "Built with an evaluation version of InstallBuilder"


class DccSubmitter(NamedTuple):
    """
    A structure representing the parameters for integrating a DCC submitter into the InstallBuilder
    project.
    """

    name: str
    """
    The name of the DCC application this submitter is for.
    """

    @property
    def componentName(self) -> str:
        """
        The component name that corresponds to a subdirectory of 'components' subdir
        of the InstallBuilder project file's directory. By convention, this should
        match the submitter's repository name.
        """
        return f"deadline-cloud-for-{self.name}"


class EvaluationBuildError(Exception):
    """
    Raised when an evaluation build of InstallBuilder is detected where it should not be used.
    """

    pass


def download_from_s3(bucket_name: str, key: Path, output_folder: Path) -> Path:
    dest_path = output_folder / key.name
    print(f"Downloading {key} from s3:\\\\{bucket_name}")
    import boto3

    s3 = boto3.client("s3")
    s3.download_file(bucket_name, key, dest_path)
    return dest_path


def _add_write_perms(func, path, exc_info) -> None:
    """
    Used as an error callback in `shutil.rmtree` to address an AccessDenied error that occurs on Windows.
    If a directory fails to delete, attempt to add write permissions to it and try again.
    Re-raise the error if it persists.
    """

    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def build_installer(
    workdir: Path,
    license_file: str,
    install_builder_location: Path,
    platform: str,
    local_dev_build: bool,
    s3bucket: Optional[str],
) -> Path:
    install_builder_config = INSTALL_BUILDER
    if not local_dev_build:
        install_builder_archive = download_from_s3(
            s3bucket, install_builder_config["archive"], workdir
        )
        shutil.unpack_archive(install_builder_archive, workdir)
        install_builder_path = workdir
    else:
        install_builder_path = install_builder_location

    if not install_builder_path.is_dir():
        raise FileNotFoundError(
            f"InstallBuilder path '{str(install_builder_path)}' must be a directory containing 'bin/builder'."
        )

    if license_file and not local_dev_build:
        shutil.copy(license_file, Path(workdir) / "license.xml")

    install_builder = install_builder_path / install_builder_config["command"]
    out_dir = Path(workdir) / "out"
    installer_version = os.getenv("INSTALLER_VERSION") if not local_dev_build else "00000000"
    date = datetime.today().date()

    print("Running Install Builder...")
    output = subprocess.run(
        [
            install_builder,
            "build",
            INSTALLER_ROOT / INSTALLER_TEMPLATE,
            platform,
            "--setvars",
            f"project.outputDirectory={out_dir}",
            f"project.version={installer_version[:8]}-{date}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    print(
        f"{'-'*30}\nBegin Install Builder Output\n{'-'*30}\n"
        f"{output.stdout}"
        f"{'-'*30}\nEnd Install Builder Output\n{'-'*30}\n"
    )

    if EVALUATION_VERSION_STRING in output.stdout and not local_dev_build:
        raise EvaluationBuildError(
            "InstallBuilder was detected using an evaluation version, which is only permitted in local dev builds."
        )
    elif local_dev_build and EVALUATION_VERSION_STRING not in output.stdout:
        print(
            "WARNING: InstallBuilder was not detected using an evaluation version when running a dev build. "
            "This could indicate that the error messaging when using an evaluation version has changed.\n"
            "Please check the InstallBuilder logs to confirm if the error messaging has changed from "
            f"'{EVALUATION_VERSION_STRING}' and update the install_builder.py script accordingly."
        )
    return out_dir


def dev_create_dcc_component(
    workdir: tempfile.TemporaryDirectory, dcc_component: DccSubmitter
) -> None:
    """
    Creates artifacts locally
    """
    # Clone dcc component by copying it into the working directory & allowing the dependency bundle script to be executed
    repo_dir = f"{workdir}/{dcc_component.componentName}"
    source_folder = Path(__file__).absolute().parent.parent
    shutil.copytree(source_folder, repo_dir, dirs_exist_ok=True)
    bundle_file = Path(repo_dir) / "depsBundle.sh"
    bundle_file.chmod(bundle_file.stat().st_mode | stat.S_IEXEC)
    subprocess.run(str(bundle_file), check=True)


class RequiredArg(NamedTuple):
    """
    Structure to represent a required CLI argument. Used to provide better error messaging.
    """

    argument: str
    attr: str


def main(args: argparse.Namespace) -> None:

    dcc_submitter = DccSubmitter(name=args.dcc_name)
    if not args.local_dev_build:
        missing_args = []
        for required_arg in prod_required_args:
            if getattr(args, required_arg.attr) is None:
                missing_args.append(required_arg.argument)
        if missing_args:
            parser.error(
                "the following arguments are required for non-dev builds: "
                f"{', '.join(missing_args)}\n"
            )
    else:
        if os.environ.get("CODEBUILD_BUILD_ID") is not None:
            parser.error("--local-dev-build cannot be used when running in CodeBuild.")
    with tempfile.TemporaryDirectory() as workdir:
        print(f"cwd: {Path.cwd()}")
        print(f"working directory: {workdir})")
        components_dir = INSTALLER_ROOT / "components"
        components_dir.mkdir(exist_ok=True)
        if args.local_dev_build:
            dev_create_dcc_component(workdir, dcc_submitter)

        src_component_path = f"{workdir}/{dcc_submitter.componentName}"
        dst_component_path = Path(components_dir) / dcc_submitter.componentName
        if Path(dst_component_path).exists():
            shutil.rmtree(dst_component_path, onerror=_add_write_perms)
        shutil.copytree(src_component_path, dst_component_path)

        try:
            installer_dir = build_installer(
                workdir=workdir,
                license_file=(
                    args.install_builder_license_file
                    if args.install_builder_license_file != "NO_LICENSE"
                    else None
                ),
                install_builder_location=args.install_builder_location,
                platform=args.platform,
                local_dev_build=args.local_dev_build,
                s3bucket=args.install_builder_s3_bucket,
            )
        except Exception as e:
            if args.cleanup:
                shutil.rmtree(components_dir, onerror=_add_write_perms)
            raise e

        # There are three possible extensions for built installers, depending on the platform.
        # See `platform_exec_suffix` in https://releases.installbuilder.com/installbuilder/docs/installbuilder-userguide.html#built_in_variables
        if args.platform == "osx":
            installer_extension = "app"
        elif args.platform.startswith("windows"):
            installer_extension = "exe"
        else:
            installer_extension = "run"
        installer_filename = INSTALLER_FILENAME_TEMPLATE.format(
            platform=args.platform, ext=installer_extension
        )
        installer_path = Path(installer_dir) / installer_filename

        # The macOS .app installer will always be a directory, not a file.
        # Other OS installers will be files.
        if not installer_path.is_dir() if args.platform == "osx" else not installer_path.is_file():
            raise FileNotFoundError(
                f"Expected installer file {installer_filename} not found in {installer_dir}.\n"
                f"Found:\n\t{os.linesep.join(installer_dir.iterdir())}"
            )

        output_path = installer_filename
        if args.output_dir:
            args.output_dir.mkdir(exist_ok=True)
            output_path = args.output_dir / output_path
        if platform.system() == "Darwin" and Path(output_path).exists():
            shutil.rmtree(output_path, onerror=prod_required_args)
        shutil.move(installer_path, output_path)

        if args.cleanup:
            shutil.rmtree(components_dir, onerror=_add_write_perms)
            print(f"Deleted build directory: {components_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    prod_required_args: List[RequiredArg] = []

    parser.add_argument(
        "--dcc-name", required=True, help="The name of the DCC application this submitter is for."
    )
    parser.add_argument(
        "--dcc-installer-file", required=True, help="The main installer file for the DCC"
    )

    parser.add_argument(
        "--local-dev-build",
        action=argparse.BooleanOptionalAction,
        help=(
            "Add this argument when running a development build. This will use an evaluation copy of InstallBuilder and not require a license."
        ),
    )
    parser.add_argument(
        "--install-builder-s3-bucket",
        help="The name of S3 Bucket that contains Install Builder. Required for non-local builds.",
    )  # Required for non-local builds
    prod_required_args.append(
        RequiredArg("--install-builder-s3-bucket", "install_builder_s3_bucket")
    )

    parser.add_argument(
        "--install-builder-location",
        help="The InstallBuilder location, containing 'bin/builder'.",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--install-builder-license-file",
        help="The path to the file containing the InstallBuilder license. This can be set to NO_LICENSE to skip downloading the license.",
    )  # Required for non-local builds
    prod_required_args.append(
        RequiredArg("--install-builder-license-file", "install_builder_license_file")
    )

    parser.add_argument(
        "--no-cleanup",
        dest="cleanup",
        action="store_false",
        help="Do not delete the build components folder after completion.",
    )
    parser.add_argument(
        "--platform",
        required=True,
        help="The platform to build an installer for. See the InstallBuilder documentation for a full list of allowed platforms.",
    )
    parser.add_argument(
        "--output-dir",
        required=False,
        default=None,
        type=Path,
        help="The directory to create the installer in. Default is the current directory.",
    )
    args = parser.parse_args()
    main(args)
