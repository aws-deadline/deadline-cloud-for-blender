#!/usr/bin/env python
"""Script to create platform-specific Deadline submission installers using Bitrock InstallBuilder."""
import argparse
import os
import sys
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime
from typing import List, NamedTuple

# If the InstallBuilder version is being changed, please ensure the archives are in a "flattened" structure.
# This is automatically done if the update_install_builder.sh script is used.
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
#
# Update June 2023: InstallBuilder can build installers for all platforms. We only need to run InstallBuilder on one platform,
# so we're only going to build it on Linux.
INSTALL_BUILDER = {
    'archive': f'install_builder/VMware-InstallBuilder-Professional-linux.tar.gz',
    'command': os.path.join('bin', 'builder'),
}

# This is derived from <installerFilename> in DeadlineCloudForBlenderSubmitter.xml
# See "Supported Platforms" table in https://releases.installbuilder.com/installbuilder/docs/installbuilder-userguide.html
INSTALLER_FILENAMES = {
  'windows-x64': 'DeadlineCloudForBlenderSubmitter-windows-x64-installer.exe',
  'linux-x64': 'DeadlineCloudForBlenderSubmitter-linux-x64-installer.run',
  'osx': 'DeadlineCloudForBlenderSubmitter-osx-installer.app',
}

# This is the directory containing the InstallBuilder root .xml component.
# All file paths in the InstallBuilder component files are relative to this directory
INSTALL_BUILDER_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_ZIP = 'deadline_blender_submitter.zip'
INSTALLER_TEMPLATE = 'DeadlineCloudForBlenderSubmitter.xml'
EVALUATION_VERSION_STRING = "Built with an evaluation version of InstallBuilder"

class DccSubmitter(NamedTuple):
    """
    A structure representing the parameters for integrating a DCC submitter into the InstallBuilder
    project.
    """

    name: str
    """
    The name of the DCC application this submitter is for.

    This **must** match up exactly with a corresponding value in the `DccSubmitter` enum in the
    `lib/constructs/Config.ts` file.
    """

    componentName: str
    """
    The component name that corresponds to a subdirectory of 'components' subdir
    of the InstallBuilder project file's directory. By convention, this should
    match the submitter's repository name.
    """

    @property
    def cliArgName(self) -> str:
        """
        The command-line argument name used as input for this script
        """
        return f"{self.name}-deadline-submitter-artifact-path"

DCC_SUBMITTERS: List[DccSubmitter] = [
    DccSubmitter(
       name='blender',
       componentName='deadline-cloud-for-blender',
    ),
]
"""The DCC submitter component configurations"""


class BadRCError(Exception):
    pass

class EvaluationBuildError(Exception):
    pass


def run(cmd, cwd=None, env=None, echo=True):
    if echo:
        sys.stdout.write(f"Running cmd: {cmd}\n")
    kwargs = {
        'shell': True,
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE,
    }
    if isinstance(cmd, list):
        kwargs['shell'] = False
    if cwd is not None:
        kwargs['cwd'] = cwd
    if env is not None:
        kwargs['env'] = env
    p = subprocess.Popen(cmd, **kwargs)
    stdout, stderr = p.communicate()
    output = stdout.decode('utf-8') + stderr.decode('utf-8')
    if p.returncode != 0:
        raise BadRCError(f"Bad rc ({p.returncode}) for cmd '{cmd}': {output}")
    return output


def download_from_s3(bucket_name, key, output_folder):
    dest_path = os.path.join(output_folder, os.path.basename(key))
    print(f'Downloading {key} from s3:\\\\{bucket_name}')
    import boto3
    s3 = boto3.client('s3')
    s3.download_file(bucket_name, key, dest_path)
    return dest_path


def download_from_secretsmanager(secret_id, output_path):
    print(f'Downloading {secret_id}')
    import boto3
    sm = boto3.client('secretsmanager')
    response = sm.get_secret_value(SecretId=secret_id)
    with open(output_path, mode='w') as f:
        f.write(response.get('SecretString'))


def build_installer(
    workdir: str,
    s3bucket: str,
    license_secret_id: str,
    platform: str,
    local_dev_build: bool
):
    
    install_builder_config = INSTALL_BUILDER
    install_builder_version = "24.11.1"

    install_build_path = ""
    if sys.platform.startswith("darwin"):
        install_build_path = f"/Applications/InstallBuilder Professional {install_builder_version}/"
    if not install_build_path:
        raise FileNotFoundError(f"Could not find install builder's `builder` executable")
    
    # if not local_dev_build:
    #     install_builder_archive = download_from_s3(s3bucket, install_builder_config['archive'], workdir)
    # else:
        # existing_archive = os.path.dirname(INSTALL_BUILDER_PROJECT_ROOT) + f"/git-lfs/dependency-bucket/{install_builder_config['archive']}"
        # install_builder_archive = os.path.join(workdir, install_builder_config['archive'])
        # os.makedirs(os.path.dirname(install_builder_archive), exist_ok=True)
        # if os.path.exists(existing_archive):
        #     # copy to workdir
        #     shutil.copy(existing_archive, install_builder_archive)
        # else:
        #     raise FileNotFoundError(f"Could not find {existing_archive}")
    # shutil.unpack_archive(install_builder_archive, workdir)

    if license_secret_id and not local_dev_build:
        download_from_secretsmanager(license_secret_id, os.path.join(workdir, 'license.xml'))

    install_builder = os.path.join(install_build_path, install_builder_config['command'])
    out_dir = os.path.join(workdir, 'out')
    installer_version = os.getenv('INSTALLER_VERSION') if not local_dev_build else "00000000"
    date = datetime.today().date()
    output = run([
        install_builder,
        'build',
        os.path.join(INSTALL_BUILDER_PROJECT_ROOT, INSTALLER_TEMPLATE),
        platform,
        '--setvars', f'project.outputDirectory={out_dir}', f'project.version={installer_version[:8]}-{date}'
    ])
    sys.stdout.write(
        f"{'-'*30}\nBegin Install Builder Output\n{'-'*30}\n"
        f"{output}\n"
        f"{'-'*30}\nEnd Install Builder Output\n{'-'*30}\n"
    )

    if EVALUATION_VERSION_STRING in output and not local_dev_build:
        raise EvaluationBuildError("InstallBuilder was detected using an evaluation version.")
    elif local_dev_build and EVALUATION_VERSION_STRING not in output:
        raise EvaluationBuildError(
            "InstallBuilder was not detected using an evaluation version when running a dev build. "
            "This could indicate that the error messaging when using an evaluation version has changed.\n"
            "Please check the InstallBuilder logs to confirm if the error messaging has changed from "
            f"'{EVALUATION_VERSION_STRING}' and update the install_builder.py script accordingly."
        )
    return out_dir


# def dev_create_dcc_components(workdir: tempfile.TemporaryDirectory):
#     """
#     Creates artifacts locally that mimic what happen in codepipeline.
#     """
#     # Clone deadline-cloud
#     deadline_cloud_dir = f"{workdir}/deadline-cloud"
#     source_folder = os.environ.get("DEADLINE_CLOUD_SOURCE_FOLDER")
#     if source_folder:
#         run(f"cp -rf {source_folder} {deadline_cloud_dir}")
#     else:
#         repository_owner = os.environ.get(f"DEADLINE_CLOUD_FORK_OWNER", "aws-deadline")
#         run(f"git clone git@github.com:{repository_owner}/deadline-cloud.git {deadline_cloud_dir}")
#         branch_override = os.environ.get('DEADLINE_CLOUD_BRANCH_OVERRIDE')
#         if branch_override:
#             sys.stdout.write(f"Branch override for deadline-cloud: {branch_override}\n")
#             run(f"cd {deadline_cloud_dir}; git fetch origin {branch_override} && git checkout {branch_override}")
#     run(f"cd {deadline_cloud_dir}; pip install hatch")
#     run(f"cd {deadline_cloud_dir}; hatch run codebuild-installer:build")
#     os.environ["OUT_FILE"] = f"{workdir}/deadline.zip"
#     run(f"cd {deadline_cloud_dir}; hatch run codebuild-installer:make_exe")

#     for dcc_submitter in DCC_SUBMITTERS:
#         dev_create_dcc_component(workdir, dcc_submitter)

def dev_create_dcc_component(workdir: tempfile.TemporaryDirectory, dcc_component: DccSubmitter):
    """
    Creates artifacts locally that mimic what happen in codepipeline.
    """
    # Clone dcc component
    repo_dir= f"{workdir}/{dcc_component.componentName}"
    source_folder = os.environ.get(f"{dcc_component.name.upper()}_SOURCE_FOLDER")
    if source_folder:
        run(f"cp -rf {source_folder} {repo_dir}")
    else:
        repository_owner = os.environ.get(f"{dcc_component.name.upper()}_FORK_OWNER", "aws-deadline")
        run(f"git clone git@github.com:{repository_owner}/{dcc_component.componentName}.git {repo_dir}")
        branch_override = os.environ.get(f"{dcc_component.name.upper()}_BRANCH_OVERRIDE")
        if branch_override:
            sys.stdout.write(f"Branch override for {dcc_component.name}: {branch_override}\n")
            run(f"cd {repo_dir}; git fetch origin {branch_override} && git checkout {branch_override}")
    run(f"cd {repo_dir}; chmod +x ./depsBundle.sh")
    run(f"cd {repo_dir}; ./depsBundle.sh")

class RequiredArg(NamedTuple):
    """
    Structure to represent a required CLI argument. Only used to provide better error messaging
    """
    argument: str
    attr: str

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    prod_required_args: List[RequiredArg] = []

    parser.add_argument(
        '--local-dev-build',
        action=argparse.BooleanOptionalAction,
        help=(
            ''
        )
    )
    parser.add_argument(
        '--install-builder-s3-bucket',
        help='The name of S3 Bucket that contains Install Builder.',
    )  # Required for non-local-builds
    prod_required_args.append(RequiredArg('--install-builder-s3-bucket', "install_builder_s3_bucket"))

    parser.add_argument(
        '--install-builder-license-secret-id',
        help='The ID (ARN or name) of Secret that contains the InstallBuilder license. This can be set to NO_LICENSE to skip downloading the license.',
    )  # Required for non-local-builds
    prod_required_args.append(RequiredArg('--install-builder-license-secret-id', "install_builder_license_secret_id"))

    parser.add_argument(
        '--bc-artifact-path',
        help=(
            'Path to the Deadline Client pyinstaller ZIP archive'
        )
    )  # Required for non-local-builds
    prod_required_args.append(RequiredArg("--bc-artifact-path", "bc_artifact_path"))

    for dcc_submitter in DCC_SUBMITTERS:
        parser.add_argument(
            f'--{dcc_submitter.cliArgName}',
            help=(
                f'Path to the directory containing the {dcc_submitter.componentName} source code'
            )
        )  # Required for non-local-builds
        prod_required_args.append(RequiredArg(f'--{dcc_submitter.cliArgName}', dcc_submitter.cliArgName.replace("-", "_")))

    parser.add_argument(
        '--no-cleanup',
        dest='cleanup',
        action='store_false',
        help=(
            'Leave the build folder produced by pyinstaller. This can be '
            'useful for debugging.'
        ),
    )
    parser.add_argument(
        '--platform',
        required=True,
        help='The platform to build an installer for',
        choices=('windows-x64', 'linux-x64', 'osx'),
    )
    parser.add_argument(
        '--output-dir',
        required=False,
        default=None,
        help='The directory to create the installer in. Default is the current directory.'
    )
    args = parser.parse_args()
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
        if not args.local_dev_build:
            run('pip install --upgrade pip --user')
        else:
            run('pip install --upgrade pip')
        print(f'cwd: {os.getcwd()}')
        print(f'working directory: {workdir}')

        # Stage a "components" directory immediately under the install builder project file's directory.
        # The directory structure convention is:
        #
        # <INSTALL_BUILDER_PROJECT_ROOT>/
        #    +- DeadlineCloudSubmitter.xml (value of INSTALLER_TEMPLATE variable)
        #    +- components/
        #       +- <COMPONENT_NAME>
        #          +- install_builder/
        #             +- <COMPONENT_NAME>.xml
        components_dir = os.path.join(INSTALL_BUILDER_PROJECT_ROOT, 'components')
        # shutil.rmtree(components_dir, ignore_errors=False)
        os.makedirs(components_dir, exist_ok=True)
        if args.local_dev_build:
            dev_create_dcc_component(workdir, DCC_SUBMITTERS[0])

        ######################
        #   DCC Submitters   #
        ######################
        for dcc_submitter in DCC_SUBMITTERS:
            src_component_path = (
                getattr(args, dcc_submitter.cliArgName.replace('-', '_'))
                if not args.local_dev_build
                else f"{workdir}/{dcc_submitter.componentName}"
            )
            dst_component_path = os.path.join(components_dir, dcc_submitter.componentName)
            if os.path.exists(dst_component_path):
                shutil.rmtree(dst_component_path)
            shutil.copytree(src_component_path, dst_component_path)


        try:
            installer_dir = build_installer(
                workdir=workdir,
                s3bucket=args.install_builder_s3_bucket,
                license_secret_id=args.install_builder_license_secret_id if args.install_builder_license_secret_id != 'NO_LICENSE' else None,
                platform=args.platform,
                local_dev_build=args.local_dev_build,
            )
        except Exception as e:
            # always want to delete the components_dir if build fails
            shutil.rmtree(components_dir)
            raise e

        installer_filename = INSTALLER_FILENAMES[args.platform]
        installer_path = os.path.join(installer_dir, installer_filename)
        print(installer_path)
        missing_mac = sys.platform.startswith("darwin") and not os.path.isdir(installer_path)
        missing_else = not sys.platform.startswith("darwin") and os.path.isfile(installer_path)
        if missing_mac or missing_else:
            raise FileNotFoundError(
                f'Expected installer file {installer_filename} not found in {installer_dir}.\n'
                f'Found:\n\t{os.linesep.join(os.listdir(installer_dir))}'
            )

        output_path = installer_filename
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            output_path = os.path.join(args.output_dir, output_path)
        if sys.platform.startswith("darwin") and os.path.exists(output_path):
            shutil.rmtree(output_path)
        shutil.move(installer_path, output_path)

        if args.cleanup:
            shutil.rmtree(components_dir)
            print(f"Deleted build directory: {components_dir}")


if __name__ == '__main__':
    main()
