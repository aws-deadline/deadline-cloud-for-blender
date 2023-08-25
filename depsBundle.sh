#!/bin/bash
set -xeuo pipefail

python depsBundle.py

rm -f dependency_bundle/deadline_submitter_for_blender-deps-windows.zip
rm -f dependency_bundle/deadline_submitter_for_blender-deps-linux.zip
rm -f dependency_bundle/deadline_submitter_for_blender-deps-macos.zip

cp dependency_bundle/deadline_submitter_for_blender-deps.zip dependency_bundle/deadline_submitter_for_blender-deps-windows.zip
cp dependency_bundle/deadline_submitter_for_blender-deps.zip dependency_bundle/deadline_submitter_for_blender-deps-linux.zip
cp dependency_bundle/deadline_submitter_for_blender-deps.zip dependency_bundle/deadline_submitter_for_blender-deps-macos.zip
