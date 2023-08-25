# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
utility_functions.py

This file defines functions that may be used by the submitter in multiple places within the
Blender Submitter.
"""

import os
import bpy
from deadline.client import api as deadline_api
from deadline.client import config as deadline_config
from configparser import ConfigParser
from typing import Optional
import boto3
from botocore.exceptions import ProfileNotFound


def get_profiles_list():
    """
    Gets list of availible profiles.
    Default profile from Deadline config is marked as such.
    """
    config = deadline_config.config_file.read_config()
    profile_list = []
    default_profile = deadline_config.get_setting("defaults.aws_profile_name", config)
    default = tuple([default_profile, default_profile, "Default profile"])
    found_default = False
    profile_list.append(default)
    try:
        aws_config_profiles = boto3.session.Session().available_profiles
    except ProfileNotFound as pnf:
        print("No AWS profiles found, please check your .aws/config file")
        raise pnf
    for profile in aws_config_profiles:
        if profile != default_profile:
            profile_list.append(tuple([profile, profile, ""]))
        else:
            found_default = True
    if not found_default:
        print(
            "The profile name you have set as default in .deadline/config is not found in .aws/config and may not be available"
        )

    return profile_list


def active_profile(config: Optional[ConfigParser] = None):
    """
    Returns Deadline config object with deafult profile as set by UI element
    """
    wm = bpy.context.window_manager
    if not config:
        config = deadline_config.config_file.read_config()
    if hasattr(wm, "deadline_profiles_lookup"):
        deadline_config.config_file.set_setting(
            "defaults.aws_profile_name", wm.deadline_profiles, config
        )
        return config
    else:
        return deadline_config.config_file.read_config()


def get_assets():
    """
    Return a set of all external assets referenced by the active project.
    """
    types = [
        "libraries",
        "images",
        "volumes",
        "sounds",
        "movieclips",
        "fonts",
        "texts",
        "cache_files",
    ]
    files = []

    for ext_type in types:
        for item in getattr(bpy.data, ext_type):
            filepath = getattr(item, "filepath")
            library = getattr(item, "library")
            if filepath:
                relpath = bpy.path.abspath(filepath, library=library)
                # Blender only returns relative absolute paths, use os.path to get absolute paths
                files.append(os.path.abspath(relpath))

    return set(files)


def get_farms(config: Optional[ConfigParser] = None):
    farms = deadline_api.list_farms(config=config)
    farm_items = []
    for farm in farms.get("farms"):
        farm_items.append(
            (farm.get("farmId"), farm.get("displayName"), farm.get("description", ""))
        )

    return farm_items


def get_queues(farm_id: str, config: Optional[ConfigParser] = None):
    queues = deadline_api.list_queues(farmId=farm_id, config=config)
    queue_items = []
    for queue in queues.get("queues"):
        queue_items.append(
            (queue.get("queueId"), queue.get("displayName"), queue.get("description", ""))
        )

    return queue_items


def set_farm_and_queue_lookups():
    """
    Loads all the available farm and queue data into temporary attributes for fast lookups to keep the UI performant.
    If we use the get_farms and get_queues directly in the farm/queue callbacks, Blender will continually call Deadline
    for this info.
    """
    if bpy.context.window_manager.deadline_logged_in:
        wm_type = bpy.types.WindowManager

        if hasattr(wm_type, "deadline_farm_lookup"):
            del wm_type.deadline_farm_lookup

        if hasattr(wm_type, "deadline_queue_lookup"):
            del wm_type.deadline_queue_lookup

        congfig = active_profile()
        farms = get_farms(config=congfig)
        wm_type.deadline_farm_lookup = farms

        queue_lookup = {}
        for farm_id, farm_name, farm_description in farms:
            queue_lookup[farm_id] = get_queues(farm_id, config=congfig)

        wm_type.deadline_queue_lookup = queue_lookup


def get_credentials_status() -> str:
    """
    Return the Credential Status name as a string
    """
    status = deadline_api.check_credentials_status()
    return status.name


def get_credentials_type() -> str:
    """
    Return the Credential type name as a string
    """
    cred_type = deadline_api.get_credentials_type()
    return cred_type.name


def get_deadline_api_available() -> str:
    """
    Return Deadline API status as a string
    """
    api_status = "UNAVAILABLE"

    if deadline_api.check_deadline_api_available():
        api_status = "AUTHORIZED"

    return api_status


def deadline_logout():
    config = active_profile()
    deadline_api.logout(config=config)
    wm = bpy.context.window_manager
    wm_type = bpy.types.WindowManager

    wm.deadline_logged_in = False

    wm.deadline_status = get_credentials_status()
    wm.deadline_creds = get_credentials_type()
    wm.deadline_api_status = get_deadline_api_available()

    if hasattr(wm_type, "deadline_farm_lookup"):
        del wm_type.deadline_farm_lookup

    if hasattr(wm_type, "deadline_queue_lookup"):
        del wm_type.deadline_queue_lookup


def deadline_login():
    def _on_cancellation_check():
        return False

    config = active_profile()
    deadline_api.login(
        on_pending_authorization=None,
        on_cancellation_check=_on_cancellation_check,
        config=config,
    )

    wm = bpy.context.window_manager
    creds_status = get_credentials_status()
    wm.deadline_status = "Logging in..."
    print(creds_status)
    if creds_status == "AUTHENTICATED":
        print("Deadline Logged In")
        set_farm_and_queue_lookups()
        wm.deadline_logged_in = True

    wm.deadline_status = creds_status
    wm.deadline_creds = get_credentials_type()
    wm.deadline_api_status = get_deadline_api_available()
