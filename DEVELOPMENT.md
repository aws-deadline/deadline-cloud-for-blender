# Windows Development Workflow

WARNING: This workflow installs additional Python packages into your Blender's python distribution.

1. Create a development location within which to do your git checkouts. For example `~/deadline-clients`.
   Clone packages from this directory with commands like
   `git clone git@github.com:casillas2/deadline-blender.git`. You'll also want the `deadline` repo.
2. Switch to your Blender'ts python directory, like `cd "C:\Program Files\Blender Foundation\Blender 3.4\3.4\python\bin"`.
3. Run `.\python -m pip install -e C:\Users\<username>\deadline-clients\deadline` to install the Amazon Deadline Cloud Client
   Library in edit mode.
4. Copy the folder `deadline_submitter_for_blender` from your checked out source code into the Blender
   installation addons like `C:\Program Files\Blender Foundation\Blender 3.4\3.4\scripts\addons_contrib`.
   Note that you will have to repeatedly copy for each edit you do.
5. In Blender, enable the Amazon Deadline Cloud Submitter addon.
