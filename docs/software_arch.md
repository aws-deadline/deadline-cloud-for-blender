# Software Architecture

This document provides an overview of the Blender submitter plug-in and adaptor that are in this repository.
The intent is to help you have a basic understanding of what the applications are doing to give you context
to understand what you are looking at when diving through the code. This is not a comprehensive deep dive of
the implementation.

## Blender Submitter Plug-in

The Blender Submitter plug-in is a Python module located in `/src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter`.
It implements Blender's Operator interface and all the functionality of the Blender plug-in.

The entrypoint that launches the dialog in Blender is found in `/src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/__init__.py`. 

Fundamentally, what this submitter is doing is creating a [Job Bundle](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle.html)
and using the GUI creation code in the [`deadline` Python package](https://pypi.org/project/deadline/) to generate the UI
that is displayed to the user. The important parts to know about in a job bundle are:

1. The job template file. The submitter code dynamically generates the template based on properties of the specific scene file
   that is loaded. For example, it may contain a Step for each layer of the scene to render.
   Note: All job template files are currently derived from a standard static job template located at
   `src/deadline/blender_submitter/addons/deadline_cloud_blender_submitter/default_blender_template.yaml`.
2. Asset references. These are the files that the job, when submitted, will require to be able to run. The submitter contains code
   that introspects the loaded scene to automatically discover these. The submitter plug-in's UI allows the end-user to modify this
   list of files.

The job submission itself is handled by functionality within the `deadline` package that is hooked up when the UI is created.

## Blender Adaptor Application

See the [README](../README.md#adaptor) for background on what purpose the adaptor application serves.

The implementation of the adaptor for Blender has two parts:

1. The adaptor application itself whose code is located in `src/deadline/blender_adaptor/BlenderAdaptor`. This is the
   implementation of the command-line application (named `blender-openjd`) that is run by Jobs created by the Blender submitter.
2. A "BlenderClient" application located in `src/deadline/blender_adaptor/BlenderClient`. This is an application that is
   run within Blender by the adaptor application when it launches Blender. The BlenderClient remains running as long as the Blender
   process is running. It facilitates communication between the adaptor process and the running Blender process; communication
   to tell Blender to, say, load a scene file, or render frame 20 of the loaded scene.

The adaptor application is built using the [Open Job Description Adaptor Runtime](https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python)
package. This package supplies the application entrypoint that defines and parses the command-line subcommands and options, as well as
the business logic that drives the state machine of the adaptor itself. Please see the README for the runtime package for information on
the lifecycle states of an adaptor, and the command line options that are available. 

Digging through the code for the adaptor, you will find that the `BlenderAdaptor.on_start()` method is where the Blender application is started.
The adaptor tells Blender to run the "BlenderClient" application. This application is, essentially, a secure web
server that is running over named pipes rather than network sockets. The adaptor sends the client commands (look for calls to `enqueue_action()`
in the adaptor) to instruct Blender to do things, and then waits for the results of those actions to take effect. 

You can see the definitions of the available commands, and the actions that they take by inspecting `src/deadline/BlenderClient/blender_client.py`. You'll
notice that the commands that it directly defines are minimal, and that the set of commands that are available is updated when the adaptor sends
it a command to set the renderer being used. Each renderer has its own command handler defined under `src/deadline/BlenderClient/render_handlers`.

The final thing to be aware of is that the adaptor defines a number of stdout/stderr handlers. These are registered when launching the Blender process
via the `LoggingSubprocess` class. Regex callbacks are defined in `src/deadline/BlenderAdaptor/adaptor.py`. These callbacks are compared to Blender's output stream and allow the adaptor to, say, translate rendering progress from Blender to a form that can be understood by Deadline Cloud and report it.
