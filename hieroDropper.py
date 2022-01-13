######################################
"Hiero DropData Callback for ShotGrid"
######################################

import hiero
import os
import sgtk
from hiero.core.events import *
from hiero.core import *

app = sgtk.platform.current_bundle()

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


# Custom loggers to write better data to log
def logSmall(msg):
    print("-  {}".format(msg))
def logBig(msg):
    print("################################")
    print(msg)
    print("################################")


def shotgunDrop(droppedArray):

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
        sgVersion = sg.find_one("Version", filters, fields)

        "Get Version Path and check if it exists"
        filePath = sgVersion["sg_path_to_frames"]
        if filePath == None:
            filePath = sgVersion["sg_path_to_movie"]
        if filePath == None:
            logSmall("Version has no Source paths for Frames or Movies, skipping...")
            logSmall(str(filePath))
            return
        if not os.path.exists(os.path.dirname(filePath)):
            logSmall("The source path doesnt exist, skipping...")
            logSmall(str(filePath))
            return
        logSmall(str(filePath))

        "Create Clip inside bin"
        myBin = getBin(os.environ["HIERODROPPER_VERSION_BIN_NAME"])
        clip = Clip(MediaSource(filePath))
        myBin.addItem(BinItem(clip))        

    def dropPlaylist(sgID, sgEntityType):
        # Find Playlist
        filters = [ ["id", "is", int(sgID)] ]
        fields = ["code"]
        sgPlaylist = sg.find_one("Playlist", filters, fields)
        print(sgPlaylist)

        # Find Versions in playlist
        filters = [ ["playlists", "name_contains",  sgPlaylist["code"] ] ]
        fields = ["code", "sg_path_to_frames", "sg_path_to_movie"]
        sgVersions = sg.find("Version", filters, fields)
        print(sgVersions)

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
            logSmall(str(filePath))

            # Create Clip inside bin
            myBin = getBin(sgPlaylist["code"])
            clip = Clip(MediaSource(filePath))
            myBin.addItem(BinItem(clip))  

    
    ##################################################################
    "MAIN CODE"
    ##################################################################
    # Instantiate the handler to get it to register itself.
    dropHandler = BinViewDropHandler()

    # Get ShotGrid Instance
    engine = sgtk.platform.current_engine()
    context = engine.context
    sg = engine.shotgun
    tk = engine.sgtk
    
    # "If ShotGrid URL in dropdata, assume dropped data is ShotGrid Data"
    # if not str(tk.shotgun_url) in str(droppedArray):
    #     return
    
    # Dropped Data from ShotGrid is usually the same and not an array
    # Example:
    #       b'https://acme.shotgunstudio.com/detail/Version/68882'

    sgEntityType = str(droppedArray).split("/")[-2]
    #logSmall(sgEntityType)

    sgID = str(droppedArray).split("/")[-1]
    #logSmall(sgID)

    # get the last loaded project
    myProject = projects()[-1]

    # Get The Project ClipsBin
    clipsBin = myProject.clipsBin()

    # Handle Version Drop
    if sgEntityType == "Version":
        dropVersion(sgID, sgEntityType)

    # Handle Playlist Drop
    if sgEntityType == "Playlist":
        dropPlaylist(sgID, sgEntityType)



        


