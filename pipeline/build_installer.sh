#!/bin/sh
# Set the -e option
set -e

pip install --upgrade pip
pip install --upgrade hatch

# This script is specifically for non-dev builds, so it requires the prod arguments.
hatch run build-installer --platform $1 --install-builder-license-file $2 --install-builder-s3-bucket $3