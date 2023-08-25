#!/bin/bash

set -ex

download_and_install_blender() {
    DCC_INSTALLER_S3_BUCKET=${DCC_INSTALLER_S3_BUCKET:?}

    BLENDER_MAJOR_MINOR_VERSION=3.3
    BLENDER_VERSION=3.3.4
    BLENDER_ARCHIVE=blender-${BLENDER_VERSION}-linux-x64.tar.xz
    BLENDER_INSTALL_FOLDER=/usr/local/blender

    echo "Downloading and unpacking Blender ${BLENDER_VERSION}"
    sudo mkdir -p ${BLENDER_INSTALL_FOLDER}
    sudo chmod 777 ${BLENDER_INSTALL_FOLDER}

    # Download the Blender archive
    aws s3 cp s3://${DCC_INSTALLER_S3_BUCKET}/blender/${BLENDER_MAJOR_MINOR_VERSION}/${BLENDER_ARCHIVE} ${BLENDER_INSTALL_FOLDER}
    # Extract the Blender archive, stripping the parent directory
    tar -xf ${BLENDER_INSTALL_FOLDER}/${BLENDER_ARCHIVE} -C ${BLENDER_INSTALL_FOLDER} --strip-components=1

    # Delete the archive
    echo "Removing Blender archive"
    rm ${BLENDER_INSTALL_FOLDER}/${BLENDER_ARCHIVE}

    echo "Finished installing Blender ${BLENDER_VERSION}"
}

if [ ! -f /usr/local/blender/blender ]
then
  download_and_install_blender
else
  echo "Blender already installed"
  /usr/local/blender/blender -v
fi