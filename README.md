# AWS Deadline Cloud for Blender

[![pypi](https://img.shields.io/pypi/v/deadline-cloud-for-blender.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-blender)
[![python](https://img.shields.io/pypi/pyversions/deadline-cloud-for-blender.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-blender)
[![license](https://img.shields.io/pypi/l/deadline-cloud-for-blender.svg?style=flat)](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/mainline/LICENSE)

AWS Deadline Cloud for Blender is a python package that allows users to create [AWS Deadline Cloud][deadline-cloud] jobs from within Blender. Using the [Open Job Description (OpenJD) Adaptor Runtime][openjd-adaptor-runtime] this package also provides a command line application that adapts Blender's command line interface to support the [OpenJD specification][openjd].

[deadline-cloud]: https://docs.aws.amazon.com/deadline-cloud/latest/userguide/what-is-deadline-cloud.html
[deadline-cloud-client]: https://github.com/aws-deadline/deadline-cloud
[openjd]: https://github.com/OpenJobDescription/openjd-specifications/wiki
[openjd-adaptor-runtime]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python
[openjd-adaptor-runtime-lifecycle]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/release/README.md#adaptor-lifecycle

## Compatibility

This library requires:

1. Blender 3.6 or greater,
1. Python 3.10 or higher; and
1. Linux, Windows, or a macOS operating system.
   * Adaptor only supports Linux and macOS

## Submitter

This package provides a Blender plugin that creates jobs for AWS Deadline Cloud using the [AWS Deadline Cloud client library][deadline-cloud-client]. Based on the loaded scene it determines the files required, allows the user to specify render options, and builds an [OpenJD template][openjd] that defines the workflow.

### Getting Started

If you have installed the submitter using the Deadline Cloud submitter installer you can follow the guide to [Setup Deadline Cloud submitters](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html#load-dca-plugin) for the manual steps needed after installation.

If you are setting up the submitter for a developer workflow or manual installation you can follow the instructions in the [DEVELOPMENT](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/mainline/DEVELOPMENT.md#manual-installation) file.
## Adaptor

The Blender Adaptor implements the [OpenJD][openjd-adaptor-runtime] interface that allows render workloads to launch Blender and feed it commands. This gives the following benefits:
* a standardized render application interface,
* sticky rendering, where the application stays open between tasks,

Jobs created by the submitter use this adaptor by default, and require that both the installed adaptor
and the Blender executable be available on the PATH of the user that will be running your jobs.

Or you can set the `BLENDER_EXECUTABLE` to point to the Blender executable.

### Getting Started

The adaptor can be installed by the standard python packaging mechanisms:
```sh
$ pip install deadline-cloud-for-blender
```

After installation it can then be used as a command line tool:
```sh
$ blender-openjd --help
```

For more information on the commands the OpenJD adaptor runtime provides, see [here][openjd-adaptor-runtime-lifecycle].

## Versioning

This package's version follows [Semantic Versioning 2.0](https://semver.org/), but is still considered to be in its
initial development, thus backwards incompatible versions are denoted by minor version bumps. To help illustrate how
versions will increment during this initial development stage, they are described below:

1. The MAJOR version is currently 0, indicating initial development.
2. The MINOR version is currently incremented when backwards incompatible changes are introduced to the public API.
3. The PATCH version is currently incremented when bug fixes or backwards compatible changes are introduced to the public API.

## Security

See [CONTRIBUTING](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/release/CONTRIBUTING.md#security-issue-notifications) for more information.

## Telemetry

See [telemetry](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/release/docs/telemetry.md) for more information.

## License

This project is licensed under the Apache-2.0 License.
