# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import re
import sgtk
import hiero
from hiero.core.events import *
from hiero.core import *
from sgtk.platform import Application

app = None


class HieroDropperApp(Application):
    """
    The app entry point. This class is responsible for initializing and tearing down
    the application, handle menu registration etc.
    """

    def init_app(self):
        """
        Called as the application is being initialized
        """

        # first, we use the special import_module command to access the app module
        # that resides inside the python folder in the app. This is where the actual UI
        # and business logic of the app is kept. By using the import_module command,
        # toolkits code reload mechanism will work properly.
        # app_payload = self.import_module("app")

        # now register a *command*, which is normally a menu entry of some kind on a Shotgun
        # menu (but it depends on the engine). The engine will manage this command and
        # whenever the user requests the command, it will call out to the callback.

        # first, set up our callback, calling out to a method inside the app module contained
        # in the python folder of the app
        # menu_callback = lambda : app_payload.dialog.show_dialog(self)

        # now register the command with the engine
        # self.engine.register_command("Show Starter Template App...", menu_callback)

        self.logger.info("Loading ShotGridDropper DropData callback for Hiero")

        try:
            # fill the global app var so we can use it elsewhere
            global app
            app = self

            # Instantiate the handler to get it to register itself.
            dropHandler = BinViewDropHandler()

        except Exception as e:
            self.logger.error("Failed to load ShotGridDropper!")
            self.logger.error(e)


# Drop handler for BinView
class BinViewDropHandler:
    """
    The Drop handler Class
    """
    kTextMimeType = "text/plain"

    def __init__(self):
        # hiero doesn't deal with drag and drop for text/plain data, so tell it to allow it
        hiero.ui.registerBinViewCustomMimeDataType(BinViewDropHandler.kTextMimeType)

        # register interest in the drop event now
        registerInterest((EventType.kDrop, EventType.kBin), self.dropHandler)

    def dropHandler(self, event):

        # get the mime data
        # print("mimeData: {}".format(event.mimeData))
        app.logger.debug("Drop Event MimeData: {}".format(event.mimeData))

        # fast/easy way to get at text data
        # if event.mimeData.hasText():
        #  print event.mimeData.text()

        # more complicated way
        if event.mimeData.hasFormat(BinViewDropHandler.kTextMimeType):
            byteArray = event.mimeData.data(BinViewDropHandler.kTextMimeType)
            # print("byteArray: {}".format(byteArray.data()))

        # If ShotGrid URL in dropdata, assume dropped data is ShotGrid Data
        tk = sgtk.platform.current_engine().sgtk
        if not str(tk.shotgun_url) in str(byteArray.data()):
            app.logger.debug("Ignoring drop event, ShotGrid URL not in dropped data.")
            return False

        # signal that we've handled the event here
        event.dropEvent.accept()

        # Get custom hiero objects if drag from one view to another
        # (only present if the drop was from one hiero view to another)
        if hasattr(event, "items"):
            pass

        # figure out which item it was dropped onto
        # print "dropItem: ", event.dropItem

        # get the widget that the drop happened in
        # print "dropWidget: ", event.dropWidget

        # get the higher level container widget (for the Bin View, this will be the Bin View widget)
        # print "containerWidget: ", event.containerWidget

        # can also get the sender
        # print "eventSender: ", event.sender

        shotgun_drop(byteArray.data())

    def unregister(self):
        unregisterInterest((EventType.kDrop, EventType.kBin), self.dropHandler)
        hiero.ui.unregisterBinViewCustomMimeDataType(BinViewDropHandler.kTextMimeType)


# Drop callback
def shotgun_drop(dropped_array):
    global app

    # Dropped Data from ShotGrid is usually the same and not an array
    # Example: https://acme.shotgunstudio.com/detail/Version/68882

    dropped_url = str(dropped_array)

    entity_type = dropped_url.split("/")[-2]
    entity_id = int((dropped_url.split("/")[-1]).strip("'"))
    app.logger.info("Attempting to Drop {} with id: {}...".format(entity_type, entity_id))

    drop_entity(entity_id, entity_type)


def drop_entity(sg_id, entity_type):
    """
    Processing either a Version or a Playlist. Version is singular, Playlist can contain many Versions
    :param sg_id: int - Entity id
    :param entity_type: str - Entity Type
    :return: None
    """
    global app

    # Find Versions
    version_filters = []
    if entity_type == 'Version':
        version_filters = [["id", "is", sg_id]]

    elif entity_type == 'Playlist':
        # Find Playlist
        filters = [['id', 'is', sg_id]]
        fields = ['code']
        playlist = app.shotgun.find_one('Playlist', filters, fields)
        if not playlist:
            raise ValueError(f'Unable to find ShotGrid Playlist #{sg_id}')

        version_filters = [['playlists', 'is', {'type': 'Playlist', 'id': sg_id}]]

    fields = ["code", "sg_path_to_frames", "sg_path_to_movie"]
    versions = app.shotgun.find("Version", version_filters, fields)

    for version in versions:
        if not version["sg_path_to_frames"] and not version["sg_path_to_movie"]:
            app.logger.error(f"Version {version['code']} (#{version['id']}) has no "
                             f"Source paths for Frames or Movies, skipping...")
            continue

        file_path = version["sg_path_to_frames"] or version["sg_path_to_movie"]

        # Remap the SG file path to the OS specific file path
        app.logger.info(f'Remap file path: {file_path}')
        file_path = remap_file_path_from_sg_storage_path(file_path, app.shotgun)
        app.logger.info(f'... remapped to: {file_path}')

        if not os.path.exists(os.path.dirname(file_path)):
            app.logger.error(f'The source path "{file_path}" doesnt exist, skipping...')
            continue

        # Create Clip inside bin
        if entity_type == 'Playlist':
            my_bin = get_bin(playlist["code"])

        elif entity_type == 'Version':
            my_bin = get_bin(app.get_setting("version_bin_name"))

        clip = Clip(MediaSource(file_path))
        my_bin.addItem(BinItem(clip))


def remap_file_path_from_sg_storage_path(path, sg):
    """
    From the given path (Windows, OSX, Linux) substitute the root of the path with the SG Local Storage path for the
    current OS path. Example: A Version Path to Movie path might be using an OSX root path, update it to use Windows

    /Volumes/prodtecheastvfx/SHOTGRID/KS1/EP0_SHOTS/TST/TST_0200/previz/TST_0200_previz_v01.mov
    becomes
    L:\SHOTGRID/KS1/EP0_SHOTS/TST/TST_0200/previz/TST_0200_previz_v01.mov

    :param path: str - path to file on disk
    :param sg: Shotgun object
    :return:
    """

    local_storages = sg.find('LocalStorage', [], ['code', 'linux_path', 'mac_path', 'windows_path'])

    platform_keys = {
        'darwin': 'mac_path',
        'linux2': 'linux_path',
        'win32': 'windows_path',
    }

    for local_storage in local_storages:
        for platform in ['linux_path', 'mac_path', 'windows_path']:
            path = re.sub(re.escape(local_storage[platform]),
                          re.escape(local_storage[platform_keys[sys.platform]]), path)

    return path


def get_bin(bin_name):
    # get the last loaded project
    myProject = projects()[-1]

    # Get The Project ClipsBin
    clipsBin = myProject.clipsBin()

    # Existing Bins
    existing_bins = clipsBin.bins()

    for myBin in existing_bins:
        if myBin.name() == bin_name:
            # Bin Exists
            return myBin

    # Bin doesnt exist yet
    myBin = clipsBin.addItem(Bin(bin_name))
    return myBin
