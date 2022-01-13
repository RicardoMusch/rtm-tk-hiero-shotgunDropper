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
import sgtk
import hiero
from hiero.core.events import *
from hiero.core import *
from sgtk.platform import Application

app = None

class HieroDropperApp(Application):
    """
    The app entry point. This class is responsible for intializing and tearing down
    the application, handle menu registration etc.
    """
    
    def init_app(self):
        """
        Called as the application is being initialized
        """

        #self.logger.info("###########################")
        #self.logger.info("Hiero ShotgunDropper")
        #self.logger.info("###########################")

        # first, we use the special import_module command to access the app module
        # that resides inside the python folder in the app. This is where the actual UI
        # and business logic of the app is kept. By using the import_module command,
        # toolkit's code reload mechanism will work properly.
        #app_payload = self.import_module("app")

        # now register a *command*, which is normally a menu entry of some kind on a Shotgun
        # menu (but it depends on the engine). The engine will manage this command and 
        # whenever the user requests the command, it will call out to the callback.

        # first, set up our callback, calling out to a method inside the app module contained
        # in the python folder of the app
        #menu_callback = lambda : app_payload.dialog.show_dialog(self)

        # now register the command with the engine
        #self.engine.register_command("Show Starter Template App...", menu_callback)

        self.logger.info("- Loading ShotGridDropper DropData callback for Hiero")

        try:
            #"Get Setting for the version bin name"
            #os.environ["HIERODROPPER_VERSION_BIN_NAME"] = self.get_setting("version_bin_name")

            # "Import and Register HieroDropper"
            # sys.path.insert(0, os.path.dirname(__file__))
            # import hieroDropper

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
        #print("mimeData: {}".format(event.mimeData))
        app.logger.debug("Drop Event MimeData: {}".format(event.mimeData))

        # fast/easy way to get at text data
        #if event.mimeData.hasText():
        #  print event.mimeData.text()
        
        # more complicated way
        if event.mimeData.hasFormat(BinViewDropHandler.kTextMimeType):
            byteArray = event.mimeData.data(BinViewDropHandler.kTextMimeType)
            print("byteArray: {}".format(byteArray.data()))
        
        # If ShotGrid URL in dropdata, assume dropped data is ShotGrid Data
        tk = sgtk.platform.current_engine().sgtk
        if not str(tk.shotgun_url) in str(byteArray.data()):
            app.logger.debug("Ignoring drop event, ShotGrid URL not in dropped data.")
            return False

        # signal that we've handled the event here
        event.dropEvent.accept()

        # get custom hiero objects if drag from one view to another (only present if the drop was from one hiero view to another)
        if hasattr(event, "items"):
            #print "hasItems"
            #print event.items
            pass
        
        # figure out which item it was dropped onto
        #print "dropItem: ", event.dropItem
        
        # get the widget that the drop happened in
        #print "dropWidget: ", event.dropWidget
        
        # get the higher level container widget (for the Bin View, this will be the Bin View widget)
        #print "containerWidget: ", event.containerWidget
        
        # can also get the sender
        #print "eventSender: ", event.sender
    
        shotgunDrop(byteArray.data())

    def unregister(self):
        unregisterInterest((EventType.kDrop, EventType.kBin), self.dropHandler)
        hiero.ui.unregisterBinViewCustomMimeDataType(BinViewDropHandler.kTextMimeType)


# Drop callback
def shotgunDrop(droppedArray):

    global app

    def getBin(binName):
        # Existing Bins
        existingBins = clipsBin.bins()

        for myBin in existingBins:
            if myBin.name() == binName:
                # Bin Exists
                return myBin

        # Bin doesnt exist yet
        myBin = clipsBin.addItem(Bin(binName))
        return myBin

    def dropVersion(sgID, sgEntityType):
        # Find Version
        filters = [ ["id", "is", int(sgID)] ]
        fields = ["code", "sg_path_to_frames", "sg_path_to_movie"]
        sgVersion = app.shotgun.find_one("Version", filters, fields)

        # Get Version Path and check if it exists
        filePath = sgVersion["sg_path_to_frames"]
        if filePath == None:
            filePath = sgVersion["sg_path_to_movie"]
        if filePath == None:
            app.logger.error("Version has no Source paths for Frames or Movies, skipping...")
            app.logger.error(str(filePath))
            return
        if not os.path.exists(os.path.dirname(filePath)):
            app.logger.error("The source path doesnt exist, skipping...")
            app.logger.error(str(filePath))
            return
        app.logger.info("Filepath: {}".format(filePath))

        # Create Clip inside bin
        myBin = getBin(app.get_setting("version_bin_name"))
        clip = Clip(MediaSource(filePath))
        myBin.addItem(BinItem(clip))        

    def dropPlaylist(sgID, sgEntityType):
        # Find Playlist
        filters = [ ["id", "is", int(sgID)] ]
        fields = ["code"]
        sgPlaylist = app.shotgun.find_one("Playlist", filters, fields)
        app.logger.debug(sgPlaylist)

        # Find Versions in playlist
        filters = [ ["playlists", "name_contains",  sgPlaylist["code"] ] ]
        fields = ["code", "sg_path_to_frames", "sg_path_to_movie"]
        sgVersions = app.shotgun.find("Version", filters, fields)
        app.logger.debug(sgVersions)

        for sgVersion in sgVersions:

            # Load Version into Bin
            filePath = sgVersion["sg_path_to_frames"]
            if filePath == None:
                filePath = sgVersion["sg_path_to_movie"]
            if filePath == None:
                app.logger.error("Version has no Source paths for Frames or Movies, skipping...")
                app.logger.error(str(filePath))
                return
            if not os.path.exists(os.path.dirname(filePath)):
                app.logger.error("The source path doesnt exist, skipping...")
                app.logger.error(str(filePath))
                return
            app.logger.debug(str(filePath))

            # Create Clip inside bin
            myBin = getBin(sgPlaylist["code"])
            clip = Clip(MediaSource(filePath))
            myBin.addItem(BinItem(clip))  

    # ----------------------------------------------------------

    # Dropped Data from ShotGrid is usually the same and not an array
    # Example:
    #       b'https://acme.shotgunstudio.com/detail/Version/68882'

    dropped_url = str(droppedArray)

    entity_type = dropped_url.split("/")[-2]
    entity_id = (dropped_url.split("/")[-1]).strip("'")
    app.logger.info("Attempting to Drop {} with id: {}...".format(entity_type, entity_id))

    # get the last loaded project
    myProject = projects()[-1]

    # Get The Project ClipsBin
    clipsBin = myProject.clipsBin()

    # Handle Version Drop
    if entity_type == "Version":
        dropVersion(entity_id, entity_type)

    # Handle Playlist Drop
    if entity_type == "Playlist":
        dropPlaylist(entity_id, entity_type)
