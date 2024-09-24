# AWS Deadline Cloud for Blender

[![pypi](https://img.shields.io/pypi/v/deadline-cloud-for-blender.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-blender)
[![python](https://img.shields.io/pypi/pyversions/deadline-cloud-for-blender.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-blender)
[![license](https://img.shields.io/pypi/l/deadline-cloud-for-blender.svg?style=flat)](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/mainline/LICENSE)

AWS Deadline Cloud for Blender is a Python package that supports creating and running Blender jobs within [AWS Deadline Cloud](deadline-cloud). It provides both the implementation of a Blender addon for your workstation that helps you offload the computation for your rendering workloads
to [AWS Deadline Cloud](deadline-cloud) to free up your workstation's compute for other tasks, and the implementation of a command-line
adaptor application based on the [Open Job Description (OpenJD) Adaptor Runtime][openjd-adaptor-runtime] that improves AWS Deadline Cloud's
ability to run Blender efficiently on your render farm.

[deadline-cloud]: https://docs.aws.amazon.com/deadline-cloud/latest/userguide/what-is-deadline-cloud.html
[deadline-cloud-client]: https://github.com/aws-deadline/deadline-cloud
[openjd]: https://github.com/OpenJobDescription/openjd-specifications/wiki
[openjd-adaptor-runtime]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python
[openjd-adaptor-runtime-lifecycle]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/release/README.md#adaptor-lifecycle
[service-managed-fleets]: https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html
[default-queue-environment]: https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment

## Compatibility

This library requires:

1. Blender 3.6 or greater,
1. Python 3.10 or higher; and
1. Linux, Windows, or a macOS operating system.
   * Adaptor only supports Linux and macOS

## Versioning

This package's version follows [Semantic Versioning 2.0](https://semver.org/), but is still considered to be in its 
initial development, thus backwards incompatible versions are denoted by minor version bumps. To help illustrate how
versions will increment during this initial development stage, they are described below:

1. The MAJOR version is currently 0, indicating initial development. 
2. The MINOR version is currently incremented when backwards incompatible changes are introduced to the public API. 
3. The PATCH version is currently incremented when bug fixes or backwards compatible changes are introduced to the public API. 

## Getting Started

This repository contains two components that integrate AWS Deadline Cloud with Blender:

1. The Blender submitter addon, installed on the workstation that you will use to submit jobs; and
2. The Blender adaptor, installed on all of your AWS Deadline Cloud worker hosts that will be running the Blender jobs that you submit.

Before submitting any large, complex, or otherwise compute-heavy Blender render jobs to your farm using the submitter and adaptor that you
set up, we strongly recommend that you construct a simple test scene that can be rendered quickly and submit renders of that
scene to your farm to ensure that your setup is correctly functioning.

### Submitter

The Blender submitter addon creates a menu item in Blender's "Render" dropdown that allows can be used to submit jobs to AWS Deadline Cloud. Clicking the menu item opens a job submission dialog using the [AWS Deadline Cloud client library][deadline-cloud-client]. It automatically determines which files are required for the scene, allows the user to specify render options, builds an [Open Job Description template][openjd] that defines the workflow, and submits the job to the farm and queue of your chosing. 

To install the submitter plug-in:

If you have installed the submitter using the Deadline Cloud submitter installer you can follow the guide to [Setup Deadline Cloud submitters](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html#load-dca-plugin) for the manual steps needed after installation.

If you are setting up the submitter for a developer workflow or manual installation you can follow the instructions in the [DEVELOPMENT](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/mainline/DEVELOPMENT.md#one-time-plugin-in-environment-setup) file. Be sure to complete the one-time environment setup. 


## Adaptor

Jobs created by the submitter component require this adaptor to be installed on your worker host. Both the adaptor and Blender need to be available in the user's PATH for the jobs to run.

The adaptor application is a command-line Python-based application that enhances the functionality of Blender for running
within a render farm like Deadline Cloud. Its primary purpose for existing is to add a "sticky rendering" functionality
where a single process instance of Blender is able to load the scene file and then dynamically be instructed to perform
desired renders without needing to close and re-launch Blender between them. The alternative 
to "sticky rendering" is that Blender would need to be run separately for each render that is done, and close afterwards.
Some scenes can take 10's of minutes just to load for rendering, so being able to keep the application open and loaded between
renders can be a significant time-saving optimization; particularly when the render itself is quick.

If you are using the [default Queue Environment](default-queue-environment), or an equivalent, to run your jobs, then the adaptor will be
automatically made available to your job. Otherwise, you will need to install the adaptor.

The adaptor can be installed by the standard python packaging mechanisms:
```sh
$ pip install deadline-cloud-for-blender
```

After installation it can then be used as a command line tool:
```sh
$ blender-openjd --help
```

For more information on the commands the OpenJD adaptor runtime provides, see [here][openjd-adaptor-runtime-lifecycle].


## Blender Software Availability in AWS Deadline Cloud Service Managed Fleets

In order to avoid any compatability issues, you will want to ensure that the version of Blender that you want to run is available on the worker host when you are using
AWS Deadline Cloud's [Service Managed Fleets](service-managed-fleets) to run jobs;
hosts do not have any rendering applications pre-installed. The standard way of accomplishing this is described
[in the service documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-applications.html).
You can find a list of the versions of Blender that are available by default 
[in the user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment)
if you are using the default Conda queue enivonment in your setup.

## Viewing the Job Bundle that will be submitted

To submit a job, the submitter first generates a [Job Bundle](job-bundle), and then uses functionality from the
[Deadline](deadline-cloud-client) package to submit the Job Bundle to your render farm to run. If you would like to see
the job that will be submitted to your farm, then you can use the "Export Bundle" button in the submitter to export the
Job Bundle to a location of your choice. If you want to submit the job from the export, rather than through the
submitter plug-in then you can use the [Deadline Cloud application](deadline-cloud-client) to submit that bundle to your farm.

[job-bundle]: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle.html

## Security

We take all security reports seriously. When we receive such reports, we will 
investigate and subsequently address any potential vulnerabilities as quickly 
as possible. If you discover a potential security issue in this project, please 
notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/)
or directly via email to [AWS Security](aws-security@amazon.com). Please do not 
create a public GitHub issue in this project.

## Telemetry

See [telemetry](https://github.com/aws-deadline/deadline-cloud-for-blender/blob/release/docs/telemetry.md) for more information.

## License

This project is licensed under the Apache-2.0 License.
