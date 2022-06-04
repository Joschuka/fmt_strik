from inc_noesis import *
import os
import pickle
import math
import noewin
from pprint import pprint

#Version 0.1

# =================================================================
# Plugin options, reload after change (tools->reload plugins)
# =================================================================
global bLoadAnimations
global animStartRange
global animEndRange
global bLoadMaterials

gearModelFolder = "" # the folder where you extracted the gears. Ex : "D:\\GearSets\\Persistent\\Models"
bLoadAnimations = False # Load anims in the specified range when opening a strikm file
bLoadMaterials = True  # Try to load materials
animStartRange = 0      # First anim to load
animEndRange = 0        # Last anim to load

#You can use these fields if the skeleton is misplaced for some reason.
skelPosCorrection = NoeVec3([0,0,0])
skelRotCorrection = NoeAngles([0,0,0])

# =================================================================
# Misc
# =================================================================

global gearIndices
global bIsmatCheckBoxChecked

gearIndices = []
bIsmatCheckBoxChecked = False
globalPath = None
charaGearMap = {l : i*28 for i,l in enumerate(["Bowser", "DonkeyKong", "Luigi", "Mario", "Peach", "Rosalina", "Toad", "Waluigi", "Wario", "Yoshi"])}

def registerNoesisTypes():
    handle = noesis.register("Strikers texture",".strikt")
    noesis.setHandlerTypeCheck(handle, CheckTextureType)
    noesis.setHandlerLoadRGBA(handle, LoadRGBA)
    handle = noesis.register("Strikers model",".strikm")
    noesis.setHandlerTypeCheck(handle, CheckModelType)
    noesis.setHandlerLoadModel(handle, LoadModel)
    handle = noesis.register("Strikers decompress archive",".dict_d")
    noesis.setHandlerTypeCheck(handle, CheckModelType)
    noesis.setHandlerLoadModel(handle, LoadDictD)
    handle = noesis.register("Strikers skeleton",".strikskl")
    noesis.setHandlerTypeCheck(handle, CheckModelType)
    noesis.setHandlerLoadModel(handle, LoadSkel)
    handle = noesis.registerTool("Gear equip", GearToolMethod, "Open gear window")
    noesis.setToolFlags(handle, noesis.NTOOLFLAG_CONTEXTITEM)
    noesis.setToolVisibleCallback(handle, GearContextVisible)
    handle = noesis.registerTool("Extract dict_d", ExtractToolMethod, "Extract the decomped dict")
    noesis.setToolFlags(handle, noesis.NTOOLFLAG_CONTEXTITEM)
    noesis.setToolVisibleCallback(handle, ExtractContextVisible)
    return 1

def GearContextVisible(toolIndex, selectedFile):
    if selectedFile is None or (not selectedFile.endswith(".strikm")):
        return 0
    return 1

def ExtractContextVisible(toolIndex, selectedFile):
    if selectedFile is None or (not selectedFile.endswith(".dict_d")):
        return 0
    return 1

def ExtractToolMethod(toolIndex):
    selFileName = noesis.getSelectedFile()
    if selFileName == "":
        noesis.messagePrompt("No file selected.")
        return 0
    noeMod = noesis.instantiateModule()
    noesis.setModuleRAPI(noeMod)
    bs = NoeBitStream(rapi.loadIntoByteArray(selFileName))
    ExtractAssets(bs, selFileName)	
    noesis.messagePrompt("Assets extracted.")
    noesis.freeModule(noeMod)
    return 0

def UpdateScene(gearBaseFileName):
    if noesis.isPreviewModuleRAPIValid():
        noesis.setPreviewModuleRAPI()		
        viewData = rapi.getInternalViewData()
    else:
        viewData = None
    
    noesis.openFile(gearBaseFileName)
    if viewData:
        noesis.setPreviewModuleRAPI() #the preview module was invalidated when we loaded a new scene, so set it again
        rapi.setInternalViewData(viewData)

def comboMethod(noeWnd, controlId, wParam, lParam):
    global comboBoxIds
    global gearIndices
    global gearBaseFileName
    global bLoadAnimations
    global bLoadMaterials
    global gearNameToTrueIdx
    notificationId = (wParam >> 16)
    if notificationId == noewin.CBN_SELCHANGE:        
        comboBox = noeWnd.getControlById(controlId)
        comboIndex = comboBox.getSelectionIndex()
        cbBoxId = comboBoxIds.index(controlId - 100)
        cbBoxValue = comboBox.getStringForIndex(comboIndex)
        if cbBoxValue == "Nothing":
            gearIndices[cbBoxId] = -1
        else:
            gearIndices[cbBoxId] = gearNameToTrueIdx[cbBoxValue]
        oldValue = bLoadAnimations
        oldMatValue = bLoadMaterials
        bLoadAnimations = False
        bLoadMaterials = bIsmatCheckBoxChecked
        UpdateScene(gearBaseFileName)
        bLoadAnimations = oldValue
        bLoadMaterials = oldMatValue
    return False

def animButtonMethod(noeWnd, controlId, wParam, lParam):
    global bLoadAnimations
    global bLoadMaterials
    global gearBaseFileName
    global animBoxIds
    global animStartRange
    global animEndRange
    global bIsmatCheckBoxChecked
    
    comboBox = noeWnd.getControlById(animBoxIds[0] + 100)
    comboIndex = comboBox.getSelectionIndex()
    cbBoxValue = comboBox.getStringForIndex(comboIndex)
    oldStart, animStartRange = animStartRange, int(cbBoxValue.split("_")[-1])
    
    comboBox = noeWnd.getControlById(animBoxIds[1] + 100)
    comboIndex = comboBox.getSelectionIndex()
    cbBoxValue = comboBox.getStringForIndex(comboIndex)
    oldEnd, animEndRange = animEndRange, int(cbBoxValue.split("_")[-1]) + 1 
    
    oldValue = bLoadAnimations
    bLoadAnimations = True
    oldMatValue = bLoadMaterials
    bLoadMaterials = bIsmatCheckBoxChecked
    UpdateScene(gearBaseFileName)
    bLoadAnimations = oldValue
    bLoadMaterials = oldMatValue
    animStartRange, animEndRange = oldStart, oldEnd
    return True

def matCheckMethod(noeWnd, controlId, wParam, lParam):
    global bIsmatCheckBoxChecked
    bIsmatCheckBoxChecked = not bIsmatCheckBoxChecked
    matCheckBox = noeWnd.getControlById(controlId)
    matCheckBox.setChecked(bIsmatCheckBoxChecked)
    return True

def GearWindowProc(hWnd, message, wParam, lParam):
    return noewin.defaultWindowProc(hWnd, message, wParam, lParam)    
    
def GearToolMethod(toolIndex):
    global gearIndices 
    gearIndices = [-1,-1,-1,-1]
    global gearBaseFileName    
    gearBaseFileName = noesis.getSelectedFile()
    global comboBoxIds
    comboBoxIds = []
    global bLoadAnimations
    oldValue = bLoadAnimations
    global animBoxIds
    animBoxIds = []
    global gearNameToTrueIdx
    gearNameToTrueIdx = {}
    
    if gearBaseFileName == "":
        noesis.messagePrompt("No file selected.")
        return 0
    
    #First make sure that the path is set accurately and that we have a few assets as expected
    for i in [0,1,2,3,4]:
        gearPath = gearModelFolder + os.sep + "model_" + str(i) +".strikm"
        if not os.path.exists(gearPath):
            noesis.messagePrompt("Wrong gear path or gear path not set.")
            return 0
    
    #Make sure that this character is known
    characterName = os.path.dirname(os.path.dirname(gearBaseFileName)).split("_")[-1]
    if characterName not in charaGearMap:
        noesis.messagePrompt("Unknown character : " + str(characterName) + " or wrong path.")
        return 0
        
    gearOffset = charaGearMap[characterName]    
        
    noeWnd = noewin.NoeUserWindow("Gear UI", "GearUIClass", 280, 400, GearWindowProc)
    noeWindowRect = noewin.getNoesisWindowRect()
    if noeWindowRect:
        noeWnd.x = noeWindowRect[0] + 630
        noeWnd.y = noeWindowRect[1] + 80
    if not noeWnd.createWindow():
        print("Failed to create window.")
        return 0
    
    #Combo boxes
    sRange, eRange = gearOffset,gearOffset+28
    noeWnd.createStatic("Head", 16, 20, 80, 20)
    comboBoxIds.append(noeWnd.createComboBox(16, 40, 224, 64, comboMethod, noewin.CBS_DROPDOWNLIST))
    headComboBox = noeWnd.getControlByIndex(comboBoxIds[-1])
    headIdx, armsIdx, bodyIdx, legsIdx = [0 for _ in range(4)]
    for i in range(sRange,eRange):
        if not (i + 3 ) % 4:
            headComboBox.addString(characterName + " head gear " + str(headIdx))
            gearNameToTrueIdx[characterName + " head gear " + str(headIdx)] = i
            headIdx += 1
    headComboBox.addString("Nothing")
    headComboBox.selectString("Nothing")
    
    noeWnd.createStatic("Arms", 16, 70, 80, 20)
    comboBoxIds.append(noeWnd.createComboBox(16, 90, 224, 64, comboMethod, noewin.CBS_DROPDOWNLIST))
    armsComboBox = noeWnd.getControlByIndex(comboBoxIds[-1])
    for i in range(sRange,eRange):
        if not (i % 4):
            armsComboBox.addString(characterName + " arms gear " + str(armsIdx))
            gearNameToTrueIdx[characterName + " arms gear " + str(armsIdx)] = i
            armsIdx += 1
    armsComboBox.addString("Nothing")
    armsComboBox.selectString("Nothing")
    
    noeWnd.createStatic("Body", 16, 120, 80, 20)
    comboBoxIds.append(noeWnd.createComboBox(16, 140, 224, 64, comboMethod, noewin.CBS_DROPDOWNLIST))
    bodyComboBox = noeWnd.getControlByIndex(comboBoxIds[-1])
    for i in range(sRange,eRange):
        if not (i + 1 ) % 4:
            bodyComboBox.addString(characterName + " body gear " + str(bodyIdx))
            gearNameToTrueIdx[characterName + " body gear " + str(bodyIdx)] = i
            bodyIdx += 1
    bodyComboBox.addString("Nothing")
    bodyComboBox.selectString("Nothing")
    
    noeWnd.createStatic("Legs", 16, 170, 80, 20)
    comboBoxIds.append(noeWnd.createComboBox(16, 190, 224, 64, comboMethod, noewin.CBS_DROPDOWNLIST))
    legsComboBox = noeWnd.getControlByIndex(comboBoxIds[-1])
    for i in range(sRange,eRange):
        if not (i + 2 ) % 4:
            legsComboBox.addString(characterName + " legs gear " + str(legsIdx))
            gearNameToTrueIdx[characterName + " legs gear " + str(legsIdx)] = i
            legsIdx += 1
    legsComboBox.addString("Nothing")
    legsComboBox.selectString("Nothing")
    
    #Texture load option
    matCheckIdx = noeWnd.createCheckBox("Load textures (slower)",16,225,200,16,matCheckMethod)
    
    #Anim stuff
    animateButtonIndex = noeWnd.createButton("Animate", 80, 250, 96, 32, animButtonMethod, True)
    noeWnd.enableControlByIndex(animateButtonIndex, False)
    
    noeWnd.createStatic("First anim", 37, 300, 80, 20)
    animBoxIds.append(noeWnd.createComboBox(20, 320, 100, 64, None, noewin.CBS_DROPDOWNLIST | noewin.WS_VSCROLL))
    animStartBox = noeWnd.getControlByIndex(animBoxIds[-1])
    noeWnd.enableControlByIndex(animBoxIds[-1], False)
            
    noeWnd.createStatic("Last anim", 144, 300, 80, 20)
    animBoxIds.append(noeWnd.createComboBox(130, 320, 100, 64, None, noewin.CBS_DROPDOWNLIST))
    animEndBox = noeWnd.getControlByIndex(animBoxIds[-1])
    noeWnd.enableControlByIndex(animBoxIds[-1], False)    
    
    animDir = os.path.dirname(os.path.dirname(gearBaseFileName)) + os.sep + "Animations" #+ os.sep + "anim_" + str(3) + ".strika"
    animCount = 0
    if os.path.exists(animDir):
        for filename in os.listdir(animDir):
            f = os.path.join(animDir, filename)
            if f.endswith(".strika"):
                animCount+=1
                
    if animCount:
        noeWnd.enableControlByIndex(animBoxIds[0], True)
        noeWnd.enableControlByIndex(animBoxIds[1], True)
        noeWnd.enableControlByIndex(animateButtonIndex, True)
        for i in range(animCount):
            animStartBox.addString("anim_" + str(i))
            animEndBox.addString("anim_" + str(i))
            animStartBox.selectString("anim_0")
            animEndBox.selectString("anim_0")
                
    bLoadAnimations = False
    noesis.openFile(gearBaseFileName)
    bLoadAnimations = oldValue            
                
    # if animCount:  
    
    return 0

def getFileNum(fileNum,bIsGear = False):
    if bIsGear:
        return os.path.dirname(gearModelFolder) + os.sep + "File_Data" + os.sep + "Persistent_" + str(fileNum)
    result = filePath + os.sep + os.path.basename(os.path.dirname(filePath)) + '_' + str(fileNum)
    return result
    
def InitializeFromDict(selFileName):
    dataFileName = selFileName[:-5] + ".data"
    
    #file paths
    global destPath
    global textPath
    global modelPath
    global skelPath
    global animPath
    global animBundlePath
    global filePath
    destPath = os.path.dirname(selFileName) + os.sep + rapi.getLocalFileName(dataFileName)[:-7]
    modelPath = destPath + os.sep + "Models"
    skelPath = destPath + os.sep + "Skeletons"
    textPath = destPath + os.sep + "Textures"
    animPath = destPath + os.sep + "Animations"
    animBundlePath = destPath + os.sep + "AnimationPacks"
    filePath = destPath + os.sep + "File_Data"	
    if not os.path.exists(modelPath):
        os.makedirs(modelPath)
    if not os.path.exists(skelPath):
        os.makedirs(skelPath)
    if not os.path.exists(textPath):
        os.makedirs(textPath)
    if not os.path.exists(animPath):
        os.makedirs(animPath)
    if not os.path.exists(animBundlePath):
        os.makedirs(animBundlePath)	
    if not os.path.exists(filePath):
        os.makedirs(filePath)	

def InitializeFromAsset():
    global textureList
    textureList = []
    global modelList
    modelList = []
    global animationList
    animationList = []
    global textureHashToIndex
    textureHashToIndex = {}

    global rootPath
    rootPath = os.path.dirname(rapi.getInputName())
    rootPath = os.path.dirname(rootPath)
    
    #file paths
    global textPath
    global modelPath
    global skelPath
    global animPath
    global filePath
    modelPath = rootPath + os.sep + "Models"
    skelPath = rootPath + os.sep + "Skeletons"
    textPath = rootPath + os.sep + "Textures"
    animPath = rootPath + os.sep + "Animations"
    animBundlePath = rootPath + os.sep + "AnimationPacks"
    filePath = rootPath + os.sep + "File_Data"
    
    if not os.path.exists(modelPath):
        os.makedirs(modelPath)
    if not os.path.exists(skelPath):
        os.makedirs(skelPath)
    if not os.path.exists(textPath):
        os.makedirs(textPath)
    if not os.path.exists(animPath):
        os.makedirs(animPath)
    if not os.path.exists(animBundlePath):
        os.makedirs(animBundlePath)	
    if not os.path.exists(filePath):
        os.makedirs(filePath)

def InitializeFileStream(num, baseID=0, bufferID=2, animID=3, texDataID=1, bIsGear=False):
    #file streams
    if num == 0:		
        global bs0
        if rapi.checkFileExists(getFileNum(baseID,bIsGear)):
            bs0 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(baseID,bIsGear)))
            bs0.setEndian(NOE_LITTLEENDIAN)
        else:
            print("file 0 not found")
            return False
    elif num == 1:
        global bs1
        if rapi.checkFileExists(getFileNum(texDataID,bIsGear)):
            bs1 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(texDataID,bIsGear)))
            bs1.setEndian(NOE_LITTLEENDIAN)
        else:
            print("file 1 not found")
            return False
    elif num == 2:
        global bs2
        if rapi.checkFileExists(getFileNum(bufferID,bIsGear)):
            bs2 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(bufferID,bIsGear)))
            bs2.setEndian(NOE_LITTLEENDIAN)
        else:
            print("file 2 not found")
            return False
    elif num == 3:
        global bs3
        if rapi.checkFileExists(getFileNum(animID,bIsGear)):
            bs3 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(animID,bIsGear)))
            bs3.setEndian(NOE_LITTLEENDIAN)
        else:
            print("file 3 not found")
            return False
    return True
            

# =================================================================
# Noesis check type
# =================================================================
    
def CheckModelType(data):
    bs = NoeBitStream(data)
    if len(data) < 16:
        print("Invalid model file, too small")
        return 0
    return 1

def CheckTextureType(data):
    return 1

# =================================================================
# Classes
# =================================================================

class ChunkType1:
    def __init__(self):
        self.dataType = None
        self.flags = None
        self.chunkSize = None
        self.chunkOffset = None
    
    def parse(self, bs):
        self.dataType = bs.readUShort()
        self.flags = bs.readUShort()
        self.chunkSize = bs.readUInt()
        self.chunkOffset = bs.readUInt()
        

class ChunkType2:
    def __init__(self):
        self.dataType = None
        self.unk = None
        self.fileID = None
        self.chunkSize = None
        self.chunkOffset = None
    
    def parse(self, bs):
        self.dataType = bs.readUShort()
        self.chunkFlag = bs.readUByte()
        self.fileID = bs.readUByte()
        self.chunkSize = bs.readUInt()
        self.chunkOffset = bs.readUInt()

class STRIKTextureAsset:
    def __init__(self):
        self.hashName = None
        self.headerOffset = None
        self.headerSize = None
        self.dataOffset = None
        self.dataSize = None
        self.textureHeaderFileID = None
        self.textureDataFileID = None

class STRIKModelAsset:
    def __init__(self):
        self.hashName = None
        self.meshAssetList = []
        self.buffersOffset = -1
        self.materialOffsets = []
        self.materialMap = None
        self.pairedTextureFileIndices = []
        self.pairedGlobalTextureFileIndices = []
        self.jointList = []
        self.parentList = []
        self.animationIndices = []
        self.materialsInfo = []
        
        self.boneIDB1ToHash = {}
        self.hashToBoneIDB1 = {}
        self.boneID71ToHash = {}
        self.hashToBoneID71 = {}
        
        
        self.b001Offset = -1
        self.b001Size = -1
        self.b003Offset = -1
        self.b003Size = -1
        self.b004Offset = -1
        self.b004Size = -1
        self.b005Offset = -1
        self.b005Size = -1
        self.b006Offset = -1
        self.b006Size = -1
        self.b007Offset = -1
        self.b007Size = -1
        self.b102Offset = -1
        self.b102Size = -1
        self.b103Offset = -1
        self.b103Size = -1
        self.s7103Offset = -1
        self.s7103Size = -1
        self.s7105Offset = -1
        self.s7105Size = -1
        self.s7106Offset = -1
        self.s7106Size = -1
        self.baseID = -1
        self.bufferID = -1
        self.animID = -1
        
class STRIKSkeletonAsset:
    def __init__(self):
        self.pairedModelHashName = None
        self.s7103Offset = -1
        self.s7103Size = -1
        self.s7105Offset = -1
        self.s7105Size = -1
        self.s7106Offset = -1
        self.s7106Size = -1
        self.animID = -1
        
class STRIKAnimationAsset:
    def __init__(self):
        self.hashName = None
        self.dataOffset = None
        self.dataSize = None
        
class STRIKBoneHeader:
    def __init__(self):
        self.hash = None
        self.index = -1
        self.magic = None
        self.type = -1
        self.opcode = -1
        self.offset = -1

class STRIKMeshAsset:
    def __init__(self):
        self.vertexBufferOffset = -1
        self.skinningBufferOffset = -1
        self.uvBufferOffset = -1
        self.uvBufferStride = -1
        self.indexBufferOffset = -1
        self.indexFormat = None
        
        self.indexCount = -1
        self.vertexCount = -1
        self.isSkinned = None		
    
# =================================================================
# Load texture
# =================================================================

def LoadRGBA(data, texList):
    InitializeFromAsset()
    textureAsset = pickle.load(open( rapi.getInputName(), "rb" ))
    a = InitializeFileStream(0, textureAsset.textureHeaderFileID)
    b = InitializeFileStream(1, 0,0,0,textureAsset.textureDataFileID)
    if not (a and b):
        print("texture file couldn't be located")
        return 1
    processTexture([textureAsset])
    
    for tex in textureList:
        texList.append(tex)
    global bs0, bs1
    del bs0,bs1
    return 1
    
# =================================================================
# Load model
# =================================================================

def LoadDictD(data, mdlList):
    #This is only here to make it displayed by Noesis
    noesis.messagePrompt("You need to extract it by right-clicking, not by opening it.")
    return 1

def LoadModel(data, mdlList):
    global gearIndices
    if not len(noewin.liveWindows):
        gearIndices = [-1 for _ in range(4)]
    ctx = rapi.rpgCreateContext()
    InitializeFromAsset()
    modelAsset = pickle.load(open( rapi.getInputName(), "rb" ))
    processModel([modelAsset], gearIndices)
    for mod in modelList:
        mdlList.append(mod)
    return 1
    
def LoadSkel(data, mdlList):
    ctx = rapi.rpgCreateContext()
    InitializeFromAsset()
    skelAsset = pickle.load(open( rapi.getInputName(), "rb" ))
    processSkel([skelAsset])
    for mod in modelList:
        mdlList.append(mod)
    rapi.setPreviewOption("setSkelToShow", str(1))
    return 1
    
# =================================================================
# Data extraction 
# =================================================================

def ExtractAssets(bs,selFileName):
    InitializeFromDict(selFileName)
    chunkType1List = []
    chunkType2List = []
    
    #Texture 
    textureAssetList = []
    textureHashesToFileIndex = {}
    textureHashesToTextureType = {}
    textureIndex = -1
    #Model
    modelAssetList = []
    modelHashesToFileIndex = {}
    modelIndex = -1
    #Skeleton
    skeletonAssetList = []
    skeletonIndex = -1
    #Animation
    animationAssetList = []
    animationHashesToFileIndex = {}
    #Animation bundle
    animationBundleAssetList = []
    #Material
    materialFlag = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
    
    #Dict header utils
    bs.seek(0x3C)
    Skip1Count = bs.readUByte()
    bs.seek(0x2C)
    ChunkType1Count = bs.readUInt()
    TotalChunkCount = bs.readUInt()
    bs.seek(0x40)
    
    #Read chunk entries from dict
    bs.seek(Skip1Count * 0x1C,1) #skip first entries, we get to chunkType1 (actual chunk)
    for i in range(ChunkType1Count): #parse the "main" chunks
        chunkType1 = ChunkType1()
        chunkType1.parse(bs)
        chunkType1List.append(chunkType1)

    for i in range(TotalChunkCount - ChunkType1Count): #parse the subchunks
        chunkType2 = ChunkType2()
        chunkType2.parse(bs)
        chunkType2List.append(chunkType2)
    
    #At this point, we're at the beginning of the hashDataType + asset hash section.
    #Parsing chunkType1
    for chunk in chunkType1List:
        if chunk.dataType == 0xB000:
            bs.seek(4,1)
            modelAsset = STRIKModelAsset()
            modelAsset.hashName = hex(bs.readUInt())
            modelHashesToFileIndex[modelAsset.hashName] = len(modelAssetList)
            modelAssetList.append(modelAsset)
        elif chunk.dataType == 0x7000:
            bs.seek(4,1)
            animationAsset = STRIKAnimationAsset()
            animationAsset.hashName = hex(bs.readUInt())
            animationAsset.dataOffset = chunk.chunkOffset
            animationAsset.dataSize = chunk.chunkSize
            animationHashesToFileIndex[animationAsset.hashName] = len(animationAssetList)
            animationAssetList.append(animationAsset)
        elif chunk.dataType == 0x7100:
            bs.seek(4,1)
            skeletonAsset = STRIKSkeletonAsset()
            skeletonAsset.pairedModelHashName = hex(bs.readUInt())
            skeletonAssetList.append(skeletonAsset)
        else:
            bs.seek(8,1)
            
    #Processing chunkType2
    
    for chunk in chunkType2List:
        #Texture
        #Texture Info        
        if chunk.dataType == 0xB501:
            textureIndex += 1
            InitializeFileStream(0, chunk.fileID) #not all textures seem to use the first file, send it just in case            
            textureAsset = STRIKTextureAsset()
            bs0.seek(chunk.chunkOffset)
            textureAsset.hashName = hex(bs0.readUInt())
            bs0.readBytes(0x8)
            format = bs0.readUByte()
            # print(format)
            textureAsset.headerOffset = chunk.chunkOffset
            textureAsset.headerSize = chunk.chunkSize
            textureAsset.textureHeaderFileID = chunk.fileID
            textureAssetList.append(textureAsset)
            #necessary because for some reason some textures may have broken duplicates (see maid and Hellen in Shiny)
            if textureAsset.hashName not in textureHashesToFileIndex:
                textureHashesToFileIndex[textureAsset.hashName] = textureIndex
            if textureAsset.hashName not in textureHashesToTextureType:
                textureHashesToTextureType[textureAsset.hashName] = format
        # Texture Data
        elif chunk.dataType == 0xB502:
            textureAssetList[textureIndex].textureDataFileID = chunk.fileID
            textureAssetList[textureIndex].dataOffset = chunk.chunkOffset
            textureAssetList[textureIndex].dataSize = chunk.chunkSize			
            
        #Model
        #Model matrix, used by some models to align to the skeleton
        elif chunk.dataType == 0xB001:
            modelAssetList[modelIndex].b001Size = chunk.chunkSize
            modelAssetList[modelIndex].b001Offset = chunk.chunkOffset
        #Submesh info
        elif chunk.dataType == 0xB003:
            modelAssetList[modelIndex].b003Size = chunk.chunkSize
            modelAssetList[modelIndex].b003Offset = chunk.chunkOffset
        #Vertex data
        elif chunk.dataType == 0xB004:
            modelAssetList[modelIndex].b004Size = chunk.chunkSize
            modelAssetList[modelIndex].b004Offset = chunk.chunkOffset
        #Index buffers
        elif chunk.dataType == 0xB005:
            modelAssetList[modelIndex].bufferID = chunk.fileID
            modelAssetList[modelIndex].b005Size = chunk.chunkSize
            modelAssetList[modelIndex].b005Offset = chunk.chunkOffset
        #Material data 
        elif chunk.dataType == 0xB006:
            modelIndex+=1
            modelAssetList[modelIndex].baseID = chunk.fileID
            modelAssetList[modelIndex].b006Size = chunk.chunkSize
            modelAssetList[modelIndex].b006Offset = chunk.chunkOffset
        #Material additionnal data
        elif chunk.dataType == 0xB007:
            modelAssetList[modelIndex].b007Size = chunk.chunkSize
            modelAssetList[modelIndex].b007Offset = chunk.chunkOffset
        #Incomplete boneset coords
        elif chunk.dataType == 0xB102:
            modelAssetList[modelIndex].b102Size = chunk.chunkSize
            modelAssetList[modelIndex].b102Offset = chunk.chunkOffset
        #Incomplete boneset hashes
        elif chunk.dataType == 0xB103:
            modelAssetList[modelIndex].b103Size = chunk.chunkSize
            modelAssetList[modelIndex].b103Offset = chunk.chunkOffset
            
        #Skeleton
        #Skeleton header
        elif chunk.dataType == 0x7101:
            skeletonIndex += 1
            skeletonAssetList[skeletonIndex].animID  = chunk.fileID
        #Complete boneset coords
        elif chunk.dataType == 0x7103:
            skeletonAssetList[skeletonIndex].s7103Size = chunk.chunkSize
            skeletonAssetList[skeletonIndex].s7103Offset = chunk.chunkOffset
        #Hashes to complete boneset ID
        elif chunk.dataType == 0x7105:
            skeletonAssetList[skeletonIndex].s7105Size = chunk.chunkSize
            skeletonAssetList[skeletonIndex].s7105Offset = chunk.chunkOffset
        #Parenting info
        elif chunk.dataType == 0x7106:
            skeletonAssetList[skeletonIndex].s7106Size = chunk.chunkSize
            skeletonAssetList[skeletonIndex].s7106Offset = chunk.chunkOffset

    #file streams, we're going to assume that all the buffers etc have the same ids
    baseID, bufferID, animID = [-1 for _ in range(3)]
    if len(modelAssetList):
        baseID = modelAssetList[-1].baseID
        bufferID = modelAssetList[-1].bufferID
    if len(skeletonAssetList):
        animID = skeletonAssetList[-1].animID    
    
    global bs0,bs1,bs2,bs3
    if rapi.checkFileExists(getFileNum(baseID)):
        bs0 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(baseID)))
    else:
        print("file 0 not found")
    if rapi.checkFileExists(getFileNum(1)):
        bs1 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(1)))
    else:
        print("file 1 not found")
    if rapi.checkFileExists(getFileNum(bufferID)):
        bs2 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(bufferID)))
    else:
        print("file 2 not found")
    if rapi.checkFileExists(getFileNum(animID)):
        bs3 = NoeBitStream(rapi.loadIntoByteArray(getFileNum(animID)))
    else:
        print("file 3 not found")            
            
    for i,textAsset in enumerate(textureAssetList):
        pickle.dump( textAsset, open( textPath + os.sep + "texture_" + str(i) +".strikt", "wb" ))
    pickle.dump( textureHashesToFileIndex, open( textPath + os.sep + "textureMap.lm3tMap", "wb" ))
    
    for i,modelAsset in enumerate(modelAssetList):
        #B005
        modelAsset.buffersOffset = modelAsset.b005Offset
        #B003 and B004
        meshCount = modelAsset.b003Size//0x40
        checkPoint = modelAsset.b004Offset
        b004Size = modelAsset.b004Offset + modelAsset.b004Size
        for j in range(meshCount):
            bs0.seek(modelAsset.b003Offset+j*0x40)
            meshAsset = STRIKMeshAsset()
            #parse section
            bs0.readUInt() #hashName
            meshAsset.indexBufferOffset = bs0.readUInt()
            indexFlags = bs0.readUInt()
            meshAsset.indexCount = (indexFlags & 0xFFFFFF)
            type = (indexFlags >> 24)
            if (type == 0x80):
                meshAsset.indexFormat = 1
            else:
                meshAsset.indexFormat = 0
            meshAsset.vertexCount = bs0.readUInt()
            bs0.readUInt()
            bs0.readUShort()
            bs0.readUShort()
            bs0.readUInt64()
            bs0.readUInt()
    
            bs0.seek(checkPoint)                
            meshAsset.vertexBufferOffset = bs0.readUInt()
            whateverOffset = bs0.readUInt() 
            assert (whateverOffset - meshAsset.vertexBufferOffset) // 0x30 == meshAsset.vertexCount
            meshAsset.uvBufferOffset = bs0.readUInt()
            meshAsset.isSkinned = True if bs0.readInt() != -1 else False
            if meshAsset.isSkinned:
                bs0.seek(-4,1)
                meshAsset.skinningBufferOffset = bs0.readUInt()
                otherSkinOffset = bs0.readUInt()
                bs0.readUInt()
                meshAsset.uvBufferStride = (meshAsset.skinningBufferOffset - meshAsset.uvBufferOffset) // meshAsset.vertexCount
            else:
                bs0.readUInt()        
                meshAsset.uvBufferStride = (bs0.readUInt()- meshAsset.uvBufferOffset) // meshAsset.vertexCount            

            checkPoint = bs0.tell()			
            modelAsset.meshAssetList.append(meshAsset)
        
        #B006
        #load global textureMap if relevant
        # print(modelAsset.b006Offset, modelAsset.b006Size)
        if globalPath is not None:
            globalTextureHashesToFileIndex = pickle.load(open( globalPath + os.sep + "Textures" + os.sep + "textureMap.lm3tMap", "rb" ))
            
        #process section
        bs0.seek(modelAsset.b006Offset)
        while(bs0.tell() < modelAsset.b006Offset+modelAsset.b006Size):
            temp = hex(bs0.readUInt())
            if temp in textureHashesToFileIndex:
                modelAsset.pairedTextureFileIndices.append(textureHashesToFileIndex[temp])
            elif globalPath is not None:
                if temp in globalTextureHashesToFileIndex:
                    modelAsset.pairedGlobalTextureFileIndices.append(globalTextureHashesToFileIndex[temp])
        modelAsset.pairedTextureFileIndices = list(sorted(set(modelAsset.pairedTextureFileIndices)))
        modelAsset.pairedGlobalTextureFileIndices = list(sorted(set(modelAsset.pairedGlobalTextureFileIndices)))
        
        #B007 #Time for my usual patented material hack for NLG stuff, please don't judge
        bs0.seek(modelAsset.b007Offset)
        # if not i:
            # print(bs0.tell())
        while(len(modelAsset.materialOffsets)<len(modelAsset.meshAssetList)):
            checkPoint = bs0.tell()
            temp = bs0.readBytes(0x1C)
            if temp == materialFlag:
                bs0.seek(checkPoint + 0x10)
                temp2 = bs0.readBytes(0x1C)
                if temp2 == materialFlag:
                    checkPoint += 0x10
                bs0.seek(checkPoint-4)
                # modelAsset.materialOffsets.append(bs0.readUInt())
                modelAsset.materialOffsets.append(bs0.tell() + 0x3C)
            bs0.seek(checkPoint+4)
        modelAsset.materialOffsets.append(modelAsset.b006Offset + modelAsset.b006Size)

        for j,matOffset in enumerate(modelAsset.materialOffsets[:-1]):
            modelAsset.materialsInfo.append([-1,-1])
            bs0.seek(matOffset)
            #diffuse **should** always be there from my observations
            diffOffset = bs0.readUInt()
            bs0.seek(diffOffset + modelAsset.b006Offset)
            diffHash = hex(bs0.readUInt())
            #from what I saw all diffuse textures used ASTC_6_6, use this as a confirm
            if diffHash in textureHashesToFileIndex and diffHash in textureHashesToTextureType and textureHashesToTextureType[diffHash] == 0x1D:
                modelAsset.materialsInfo[-1][0] = textureHashesToFileIndex[diffHash]
            #look for a near normal map based on the type if the asset isn't an eye mesh, to avoid nightmare visions
            if modelAsset.meshAssetList[j].vertexCount > 100:
                for u in range(10):
                    normHash = hex(bs0.readUInt())
                    if normHash in textureHashesToFileIndex and normHash in textureHashesToTextureType and textureHashesToTextureType[normHash] == 0x16:
                        modelAsset.materialsInfo[-1][1] = textureHashesToFileIndex[normHash]    
        
        
    #Skeleton scan + match	
    for i,skeletonAsset in enumerate(skeletonAssetList):
        if skeletonAsset.pairedModelHashName in modelHashesToFileIndex:
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].animID = skeletonAsset.animID
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].s7103Size = skeletonAsset.s7103Size
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].s7103Offset = skeletonAsset.s7103Offset
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].s7105Size = skeletonAsset.s7105Size
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].s7105Offset = skeletonAsset.s7105Offset
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].s7106Size = skeletonAsset.s7106Size
            modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].s7106Offset = skeletonAsset.s7106Offset
            if i < len(animationBundleAssetList):
                modelAssetList[modelHashesToFileIndex[skeletonAsset.pairedModelHashName]].animationIndices = animationBundleAssetList[i].animationIndices
        elif i < len(modelAssetList): #strikers seem to just match skel number with mdl number when no matches
            modelAssetList[i].animID = skeletonAsset.animID
            modelAssetList[i].s7103Size = skeletonAsset.s7103Size
            modelAssetList[i].s7103Offset = skeletonAsset.s7103Offset
            modelAssetList[i].s7105Size = skeletonAsset.s7105Size
            modelAssetList[i].s7105Offset = skeletonAsset.s7105Offset
            modelAssetList[i].s7106Size = skeletonAsset.s7106Size
            modelAssetList[i].s7106Offset = skeletonAsset.s7106Offset
            
    for i,modelAsset in enumerate(modelAssetList):
        if modelAsset.s7105Offset > 0:
            #B103
            bs0.seek(modelAsset.b103Offset)
            for j in range(modelAsset.b103Size//0x4):
                hash = hex(bs0.readUInt())
                modelAsset.boneIDB1ToHash[j] = hash
                modelAsset.hashToBoneIDB1[hash] = j
            #7105
            bs3.seek(modelAsset.s7105Offset)
            for j in range(modelAsset.s7105Size//0x8):
                hash = hex(bs3.readUInt())
                id = bs3.readUInt()
                modelAsset.boneID71ToHash[id] = hash
                modelAsset.hashToBoneID71[hash] = id
        else:
            bs0.seek(modelAsset.b103Offset)
            for j in range(modelAsset.b103Size//0x4):
                hash = hex(bs0.readUInt())
                modelAsset.boneIDB1ToHash[j] = hash
                modelAsset.hashToBoneIDB1[hash] = j
        
    for i,modelAsset in enumerate(modelAssetList):
        # if not i:
            # pprint(vars(modelAsset))
        pickle.dump( modelAsset, open( modelPath + os.sep + "model_" + str(i) +".strikm", "wb" ))	
    pickle.dump( modelHashesToFileIndex, open( modelPath + os.sep + "modelMap.lm3mMap", "wb" ))
    
    for i,modelAsset in enumerate(skeletonAssetList):
        pickle.dump( modelAsset, open( skelPath + os.sep + "skel_" + str(i) +".strikskl", "wb" ))	
    
    for i,animationAsset in enumerate(animationAssetList):
        pickle.dump( animationAsset, open( animPath + os.sep + "anim_" + str(i) +".strika", "wb" ))
    
    for i,animationBundleAsset in enumerate(animationBundleAssetList):
        pickle.dump( animationBundleAsset, open( animBundlePath + os.sep + "animPack_" + str(i) +".lm3ap", "wb" ))
    
def ExtractDict(data, mdlList):
    
    ctx = rapi.rpgCreateContext()
    
    try:
        mdl = rapi.rpgConstructModel()
    except:
        mdl = NoeModel()
    mdlList.append(mdl)
    
    return 1

# =================================================================
# Data processing
# =================================================================

def processTexture(textureAssets):	
    for i,textureAsset in enumerate(textureAssets):
        bs0.seek(textureAsset.headerOffset+4) #skip the hash, not needed
        width = bs0.readUShort()
        height = bs0.readUShort()
        bs0.readBytes(4)
        format = bs0.readUByte()
        bs0.readBytes(3)
        maxBlockHeight = 16
        # print(i)
        # print(hex(format))
        if format == 0x0 or format == 0x1:
            format = "r8g8b8a8"
        elif format == 0x11:
            format = noesis.NOESISTEX_DXT1
        elif format == 0x15:
            format = noesis.FOURCC_ATI2
        elif format == 0x16:
            format = noesis.FOURCC_BC5
        elif format == 0x19:
            format = "ASTC_4_4"			
        elif format == 0x1A:
            format = "ASTC_5_4"
        elif format == 0x1B:
            format = "ASTC_5_5"
        elif format == 0x1C:
            format = "ASTC_6_5"
        elif format == 0x1D:
            format = "ASTC_6_6"
        elif format == 0x1E:
            format = "ASTC_8_5"			
        elif format == 0x1F:
            format = "ASTC_8_6"
        elif format == 0x20:
            format = "ASTC_8_8"
        else:
            print("UNKNOWN TEXTURE FORMAT !" + str(hex(format)))
            format = noesis.NOESISTEX_UNKNOWN
        textureName = str(i) + '.dds'
        bs1.seek(textureAsset.dataOffset)
        textureData = bs1.readBytes(textureAsset.dataSize)
        bRaw = type(format) == str
        if bRaw and format.startswith("ASTC"):
            blockWidth,	blockHeight = list(map(lambda x: int(x), format.split('_')[1:]))
            widthInBlocks = (width + (blockWidth - 1)) // blockWidth
            heightInBlocks = (height + (blockHeight - 1)) // blockHeight			
            blockSize = 16
            log2Val = 3 if height < 360 else 4 #texture 403, front_end
            log2Val = 2 if height < 168 else log2Val #texture 201, front_end
            log2Val = 1 if height < 85 else log2Val #texture 214, front_end
            log2Val = 0 if height < 40 else log2Val
            maxBlockHeight = rapi.callExtensionMethod("untile_blocklineargob_blockheight", height, log2Val)
            #check kboo text9             
            textureData = rapi.callExtensionMethod("untile_blocklineargob", textureData, widthInBlocks, heightInBlocks, blockSize, maxBlockHeight)		
            textureData = rapi.callExtensionMethod("astc_decoderaw32", textureData, blockWidth, blockHeight, 1, width, height, 1)
            format = noesis.NOESISTEX_RGBA32
        elif bRaw:
            blockWidth = blockHeight = 1
            widthInBlocks = (width + (blockWidth - 1)) // blockWidth
            heightInBlocks = (height + (blockHeight - 1)) // blockHeight
            textureData = rapi.callExtensionMethod("untile_blocklineargob", textureData, widthInBlocks, heightInBlocks, 4, 16)
            textureData = rapi.imageDecodeRaw(textureData, width, height, format,2)
            format = noesis.NOESISTEX_RGBA32
        else:
            blockWidth = blockHeight = 4
            blockSize = 8 if format == noesis.NOESISTEX_DXT1 else 16
            widthInBlocks = (width + (blockWidth - 1)) // blockWidth
            heightInBlocks = (height + (blockHeight - 1)) // blockHeight
            maxBlockHeight = 8 if width <= 256 or height <= 256 else 16
            maxBlockHeight = 4 if width <= 128 or height <= 128 else maxBlockHeight
            maxBlockHeight = 2 if width <= 32 or height <= 32 else maxBlockHeight
            textureData = rapi.callExtensionMethod("untile_blocklineargob", textureData, widthInBlocks, heightInBlocks, 16, maxBlockHeight)
            textureData = rapi.imageDecodeDXT(textureData, width, height, format,0.0,2)
            format = noesis.NOESISTEX_RGBA32
        tex = NoeTexture(textureAsset.hashName, width, height, textureData, format)
        textureHashToIndex[textureAsset.hashName]=len(textureList)
        textureList.append(tex)
        
def processSkel(modelAssets):
    for a,modelAsset in enumerate(modelAssets):        
        #Skeleton
        #Parenting info
        InitializeFileStream(3, 0, 0, modelAsset.animID)
        global bs3
        pList = []
        if modelAsset.s7106Offset > 0:
            bs3.seek(modelAsset.s7106Offset)
            for i in range(modelAsset.s7106Size//0x2):
                pList.append(bs3.readUShort())
        #Transform info
        jointList = []
        if modelAsset.s7103Offset > 0:
            bs3.seek(modelAsset.s7103Offset)
            for i in range(modelAsset.s7103Size//0x1C):
                quaternion = [bs3.readFloat() for j in range(4)]
                position = [bs3.readFloat() for j in range(3)]
                boneMatrixTransform = NoeQuat(quaternion).toMat43().inverse()
                boneMatrixTransform[3] = NoeVec3(position)
                # bone = NoeBone(i, 'bone_' + str(i), boneMatrixTransform, None, modelAsset.parentList[i])
                bone = NoeBone(i, 'bone_' + str(i), boneMatrixTransform, None, pList[i])
                jointList.append(bone)
        for bone in jointList:
            parentId = bone.parentIndex
            if parentId != 65535:
                bone.setMatrix(bone.getMatrix() * jointList[parentId].getMatrix())
            else:
                bone.setMatrix(bone.getMatrix()*NoeAngles([90,0,-90]).toMat43())
                
        #Animation
        if bLoadAnimations:
            # animBPath = rapi.loadPairedFileGetPath("animPack file", ".lm3ap")
            # if animBPath is not None:
            if True:
                # animationBundleAsset = pickle.load(open( animBPath[1], "rb" ))
                # animList = modelAsset.animationIndices if bLoadAnimations else []
                # animList = animationBundleAsset.animationIndices
                animList = [_ for _ in range(animStartRange, animEndRange)]
                for n,animationindex in enumerate(animList):
                    if (not rapi.checkFileExists(animPath+os.sep+"anim_" + str(animationindex)+".strika")):
                        continue
                    animationAsset = pickle.load(open( animPath+os.sep+"anim_" + str(animationindex)+".strika", "rb" ))
                    keyframedJointList = []
                    # print(animationAsset.dataOffset)
                    # print(animationAsset.dataSize)
                    bs3.seek(animationAsset.dataOffset)
                    bs3.readUInt() # 0, always ?
                    boneHeaderCount = bs3.readUShort()
                    frameCount = bs3.readUShort()
                    duration = bs3.readFloat()
                    bs3.readUInt() # 0, always ?
                    bs3.seek(0x18,1) # Not sure what the two first chunks mean
                    rotNoeKeyFramedValues = {}
                    posNoeKeyFramedValues = {}
                    scaleNoeKeyFramedValues = {}
                    unknownRotOpcode = {}
                    unknownPosOpcode = {}
                    unknownScaleOpcode = {}
                    for i in range(boneHeaderCount-2): #Sometimes additionnal chunks starting with 0x00000505, don't really care since we have offsets
                        boneHeader = STRIKBoneHeader()
                        boneHeader.hash = hex(bs3.readUInt())
                        boneHeader.index = bs3.readUByte()
                        boneHeader.magic = bs3.readUByte()
                        boneHeader.type = bs3.readUByte()
                        boneHeader.opcode = bs3.readUByte()
                        boneHeader.offset = bs3.readUInt()
                        checkpoint = bs3.tell()
                        if boneHeader.hash in modelAsset.hashToBoneID71:
                            # if boneHeader.magic != 0xC0 and boneHeader.magic != 0xC1 and boneHeader.magic != 0xC2:
                                # print("New magic found")
                                # print(boneHeader.magic)
                            #rotation
                            if boneHeader.type == 1:
                                rotNoeKeyFramedValues[boneHeader.hash] = []
                                if boneHeader.opcode == 0x0F: #confirmed
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        quaternion = NoeQuat([bs3.readFloat() for a in range(4)]).transpose()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/frameCount*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x13: #not sure but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    count = bs3.readUInt()
                                    for j in range(count):
                                        quaternion = NoeQuat([bs3.readFloat() for a in range(4)]).transpose()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/count*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x15: #confirmed
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    quaternion = NoeQuat([bs3.readFloat() for a in range(4)]).transpose()
                                    rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x16: #not sure at all
                                    # flag to say nothing do be done ?
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # quaternion = NoeQuat([bs3.readShort()/0x7FFF for a in range(4)]).transpose()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x17: #not sure at all
                                    # Some weird thing is going on. Normalization or something needed ?							
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    quaternion = NoeAngles([bs3.readShort()/180,0,0]).toQuat()
                                    rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x18: #somewhat confirmed (priestess cloth)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        quaternion = NoeAngles([0,0,bs3.readShort()/180]).toQuat()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/frameCount*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x19: #somewhat confirmed (priestess arms)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        quaternion = NoeAngles([0,bs3.readShort()/180,0]).toQuat()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/frameCount*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x1A: #need confirm, king boo
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # bs3.readShort()
                                    # quaternion = NoeAngles([bs3.readShort()/180,0,0]).toQuat()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x1B: #seen on maid
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # bs3.readShort()
                                    # quaternion = NoeAngles([bs3.readShort()/180,0,0]).toQuat()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x1C: #need confirm (pianist tail)
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # bs3.readShort()
                                    # quaternion = NoeAngles([0,bs3.readShort()/180,0]).toQuat()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                else:
                                    if hex(boneHeader.opcode) in unknownRotOpcode:
                                        unknownRotOpcode[hex(boneHeader.opcode)] += 1
                                    else:
                                        unknownRotOpcode[hex(boneHeader.opcode)] = 1
                            #location
                            elif boneHeader.type == 3:
                                posNoeKeyFramedValues[boneHeader.hash] = []
                                if boneHeader.opcode == 0x6: #confirmed, somewhat (priestess movement)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        position = NoeVec3([bs3.readFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/frameCount*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0x8: #guess
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        position = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/frameCount*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0x9: #to be confirmed but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    count = bs3.readUInt()
                                    for j in range(count):
                                        position = NoeVec3([bs3.readFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xA: #to be confirmed but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    count = bs3.readUShort()
                                    for j in range(count):
                                        position = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xB: #to be confirmed but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    position = NoeVec3([bs3.readFloat() for a in range(3)])
                                    positionKeyFramedValue = NoeKeyFramedValue(0, position)
                                    posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xC: #confirmed (maid stuff)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    position = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                    positionKeyFramedValue = NoeKeyFramedValue(0, position)
                                    posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xD: #confirmed (pianist movement)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    axis = bs3.readUInt()
                                    bs3.readBytes(0x8)
                                    count = bs3.readUInt()
                                    for j in range(count):
                                        data = bs3.readFloat()
                                        if axis == 0:
                                            position = NoeVec3([data,0,0])
                                        elif axis == 1:
                                            position = NoeVec3([0,data,0])
                                        elif axis == 2:
                                            position = NoeVec3([0,0,data])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xE: #confirmed somewhat (Hellen outfit)
                                    bs3.seek(animationAsset.dataOffset+ boneHeader.offset)
                                    a = bs3.readUInt()
                                    bs3.readUShort()
                                    count = bs3.readUShort()
                                    for j in range(count):
                                        position = NoeVec3([bs3.readHalfFloat(),0,0])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                else:
                                    if hex(boneHeader.opcode) in unknownPosOpcode:
                                        unknownPosOpcode[hex(boneHeader.opcode)] += 1
                                    else:
                                        unknownPosOpcode[hex(boneHeader.opcode)] = 1
                            #Not confirmed at all, no clue yet. Probably something other than scale
                            # elif boneHeader.type == 2:
                                # scaleNoeKeyFramedValues[boneHeader.hash] = []
                                # posNoeKeyFramedValues[boneHeader.hash] = []
                                # if boneHeader.opcode == 0x2A: #always of length 12 so either 6 HF or 3 F, don't have any clear example
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # scale = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                    # scaleKeyFramedValue = NoeKeyFramedValue(0, scale)
                                    # scaleNoeKeyFramedValues[boneHeader.hash].append(scaleKeyFramedValue)
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # position = NoeVec3([bs3.readFloat() for a in range(3)])
                                    # positionKeyFramedValue = NoeKeyFramedValue(0, position)
                                    # posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                # else:
                                    # if hex(boneHeader.opcode) in unknownScaleOpcode:
                                        # unknownScaleOpcode[hex(boneHeader.opcode)] += 1
                                    # else:
                                        # unknownScaleOpcode[hex(boneHeader.opcode)] = 1
                        bs3.seek(checkpoint)
                    # print("anim " + str(animationindex))
                    # print(unknownRotOpcode)
                    # print(unknownPosOpcode)
                    for hash in modelAsset.hashToBoneID71:
                        if hash in posNoeKeyFramedValues or hash in rotNoeKeyFramedValues or hash in scaleNoeKeyFramedValues:
                            actionBone = NoeKeyFramedBone(modelAsset.hashToBoneID71[hash])
                            #root bone rotation ignored as it seem to screw up some stuff
                            if hash in rotNoeKeyFramedValues and hash != "0x2e51a3":
                                actionBone.setRotation(rotNoeKeyFramedValues[hash], noesis.NOEKF_ROTATION_QUATERNION_4)
                            if hash in posNoeKeyFramedValues:
                                actionBone.setTranslation(posNoeKeyFramedValues[hash], noesis.NOEKF_TRANSLATION_VECTOR_3)
                            if hash in scaleNoeKeyFramedValues:
                                actionBone.setScale(scaleNoeKeyFramedValues[hash], noesis.NOEKF_SCALE_VECTOR_3)
                            keyframedJointList.append(actionBone)
                    anim = NoeKeyFramedAnim("anim_"+str(animationindex), modelAsset.jointList, keyframedJointList, 30)
                    animationList.append(anim)
        mdl = NoeModel()
        if len(jointList) > 0:
            mdl.setBones(jointList)
        if len(animationList) > 0:
            mdl.setAnims(animationList)
        modelList.append(mdl)    

def CommitMeshTris(bs0, bs2, modelAsset, modelIndex,i, mesh, s7103Offset, hashToBoneID71):
    bs0.seek(modelAsset.b001Offset)
    modelMatrix = NoeMat44.fromBytes(bs0.readBytes(0x40))
    #vertices
    bs2.seek(modelAsset.buffersOffset + mesh.vertexBufferOffset)
    # bs2.seek(mesh.vertexBufferOffset)
    finalVertexBuffer = bs2.readBytes(0x30*mesh.vertexCount)
    
    #uv attempt
    bs2.seek(modelAsset.buffersOffset + mesh.uvBufferOffset)
    finalUVBuffer = bs2.readBytes(mesh.uvBufferStride*mesh.vertexCount)
    
    #indices
    bs2.seek(modelAsset.buffersOffset + mesh.indexBufferOffset)
    multiplier = 1 if mesh.indexFormat else 2
    finalIndicesBuffer = bs2.readBytes(mesh.indexCount * multiplier)
    #skinning, don't care about non animated stuff for now so we ignore objects with only B1 info
    if mesh.isSkinned and s7103Offset > 0:
        bs2.seek(modelAsset.buffersOffset)
        bs2.seek(mesh.skinningBufferOffset,1)				
        checkpoint = bs2.tell()
        #Indices, need to be taken from B1 to 71
        finalBlendIndicesBuffer = bytes()
        for j in range(mesh.vertexCount):
            bs2.seek(checkpoint+j*0x14)
            temp = [bs2.readUByte() for j in range(4)]
            a = []
            for t in temp:
                h = modelAsset.boneIDB1ToHash[t]
                if h not in hashToBoneID71:
                    print("Wrong gear or skeleton, ignoring skinning")
                    mesh.isSkinned = False
                    break
                f = hashToBoneID71[h]
                finalBlendIndicesBuffer+=struct.pack('<B', f)
        bs2.seek(checkpoint)
        finalBlendWeightsBuffer = noesis.deinterleaveBytes(bs2.readBytes(0x14*mesh.vertexCount),0x4,0x10,0x14)
    
    meshName = 'model_' + str(modelIndex) + '_submesh_' + str(i)
    rapi.rpgSetMaterial(meshName)
    rapi.rpgSetName(meshName)		
    rapi.rpgClearBufferBinds()
    rapi.rpgBindPositionBufferOfs(finalVertexBuffer, noesis.RPGEODATA_FLOAT, 0x30,0x0)
    rapi.rpgBindNormalBufferOfs(finalVertexBuffer, noesis.RPGEODATA_FLOAT, 0x30,0x10)
    rapi.rpgBindTangentBufferOfs(finalVertexBuffer, noesis.RPGEODATA_FLOAT, 0x30,0x20)
    rapi.rpgBindUV1Buffer(finalUVBuffer, noesis.RPGEODATA_FLOAT, mesh.uvBufferStride)
    if mesh.isSkinned and s7103Offset > 0:
        rapi.rpgBindBoneIndexBuffer(finalBlendIndicesBuffer, noesis.RPGEODATA_UBYTE, 0x4, 0x4)
        rapi.rpgBindBoneWeightBuffer(finalBlendWeightsBuffer, noesis.RPGEODATA_FLOAT,0x10, 0x4)
    correctionMatrix = skelRotCorrection.toMat43()
    correctionMatrix[3] = skelPosCorrection
    transfMatrix = modelMatrix.toMat43() * NoeAngles([90,0,0]).toMat43() * correctionMatrix
    rapi.rpgSetTransform(transfMatrix)
    rapi.rpgCommitTriangles(finalIndicesBuffer,noesis.RPGEODATA_UBYTE if mesh.indexFormat else noesis.RPGEODATA_USHORT, mesh.indexCount,noesis.RPGEO_TRIANGLE, 1)
       
def processModel(modelAssets, gearIndices):
    for a,modelAsset in enumerate(modelAssets):
        baseID, bufferID, animID = modelAsset.baseID, modelAsset.bufferID, modelAsset.animID

        if bLoadMaterials:
            materialList = []
            texFileIDToListIndex = {}
			#Grab textures
            # for k, matInfo in enumerate(modelAsset.materialsInfo):
                # diffID = matInfo[0]
                # if diffID != -1:
                    # textureAsset = pickle.load(open( textPath+os.sep+"texture_" + str(diffID)+".strikt", "rb" ))
                    # a = InitializeFileStream(0, textureAsset.textureHeaderFileID)
                    # b = InitializeFileStream(1, 0,0,0,textureAsset.textureDataFileID)
                    # if not (a and b):
                        # print("texture file couldn't be located")
                        # continue
                    # processTexture([textureAsset])

                    # Create materials            
                    # material = NoeMaterial('model_0_submesh_' + str(k), "")
                    # material.setTexture(textureList[textureHashToIndex[textureAsset.hashName]].name)
                    # materialList.append(material)
            
            for k, fileIdx in enumerate(modelAsset.pairedTextureFileIndices):
                texFileIDToListIndex[fileIdx] = len(textureList)
                textureAsset = pickle.load(open( textPath+os.sep+"texture_" + str(fileIdx)+".strikt", "rb" ))
                a = InitializeFileStream(0, textureAsset.textureHeaderFileID)
                b = InitializeFileStream(1, 0,0,0,textureAsset.textureDataFileID)
                if not (a and b):
                    print("texture file couldn't be located")
                    continue
                processTexture([textureAsset])
            
            #Create materials
            for k, matInfo in enumerate(modelAsset.materialsInfo):
                material = NoeMaterial('model_0_submesh_' + str(k), "")
                material.setDefaultBlend(0)
                # material.setAlphaTest(False)
                if matInfo[0] >= 0:
                    material.setTexture(textureList[texFileIDToListIndex[matInfo[0]]].name)
                if matInfo[1] >= 0:
                    material.setNormalTexture(textureList[texFileIDToListIndex[matInfo[1]]].name)
                materialList.append(material)
            
        else:
            materialList = []
        #Skeleton
        #Parenting info
        InitializeFileStream(3, baseID, bufferID, animID)
        global bs3
        if modelAsset.s7106Offset > 0:
            bs3.seek(modelAsset.s7106Offset)
            for i in range(modelAsset.s7106Size//0x2):
                modelAsset.parentList.append(bs3.readUShort())
        #Transform 
        jointList = []
        if modelAsset.s7103Offset > 0:
            bs3.seek(modelAsset.s7103Offset)
            for i in range(modelAsset.s7103Size//0x1C):
                quaternion = [bs3.readFloat() for j in range(4)]
                position = [bs3.readFloat() for j in range(3)]
                boneMatrixTransform = NoeQuat(quaternion).toMat43().inverse()
                boneMatrixTransform[3] = NoeVec3(position)
                # bone = NoeBone(i, 'bone_' + str(i), boneMatrixTransform, None, modelAsset.parentList[i])
                bone = NoeBone(i, 'bone_' + str(i), boneMatrixTransform, None, modelAsset.parentList[i])
                jointList.append(bone)
        for bone in jointList:
            parentId = bone.parentIndex
            if parentId != 65535:
                bone.setMatrix(bone.getMatrix() * jointList[parentId].getMatrix())
            else:
                bone.setMatrix(bone.getMatrix()*NoeAngles([90,0,-90]).toMat43())
                
        #Animation
        if bLoadAnimations:
        # animBPath = rapi.loadPairedFileGetPath("animPack file", ".lm3ap")
            # if animBPath is not None:
            if True:
                # animationBundleAsset = pickle.load(open( animBPath[1], "rb" ))
                # animList = modelAsset.animationIndices if bLoadAnimations else []
                # animList = animationBundleAsset.animationIndices
                animList = [_ for _ in range(animStartRange, animEndRange)]
                for n,animationindex in enumerate(animList):
                    if (not rapi.checkFileExists(animPath+os.sep+"anim_" + str(animationindex)+".strika")):
                        continue
                    animationAsset = pickle.load(open( animPath+os.sep+"anim_" + str(animationindex)+".strika", "rb" ))
                    keyframedJointList = []
                    # print(animationAsset.dataOffset)
                    # print(animationAsset.dataSize)
                    bs3.seek(animationAsset.dataOffset)
                    bs3.readUInt() # 0, always ?
                    boneHeaderCount = bs3.readUShort()
                    frameCount = bs3.readUShort()
                    duration = bs3.readFloat()
                    bs3.readUInt() # 0, always ?
                    bs3.seek(0x18,1) # Not sure what the two first chunks mean
                    rotNoeKeyFramedValues = {}
                    posNoeKeyFramedValues = {}
                    scaleNoeKeyFramedValues = {}
                    unknownRotOpcode = {}
                    unknownPosOpcode = {}
                    unknownScaleOpcode = {}
                    for i in range(boneHeaderCount-2): #Sometimes additionnal chunks starting with 0x00000505, don't really care since we have offsets
                        boneHeader = STRIKBoneHeader()
                        boneHeader.hash = hex(bs3.readUInt())
                        boneHeader.index = bs3.readUByte()
                        boneHeader.magic = bs3.readUByte()
                        boneHeader.type = bs3.readUByte()
                        boneHeader.opcode = bs3.readUByte()
                        boneHeader.offset = bs3.readUInt()
                        checkpoint = bs3.tell()
                        if boneHeader.hash in modelAsset.hashToBoneID71:
                            # if boneHeader.magic != 0xC0 and boneHeader.magic != 0xC1 and boneHeader.magic != 0xC2:
                                # print("New magic found")
                                # print(boneHeader.magic)
                            #rotation
                            if boneHeader.type == 1:
                                rotNoeKeyFramedValues[boneHeader.hash] = []
                                if boneHeader.opcode == 0x0F: #confirmed
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        quaternion = NoeQuat([bs3.readFloat() for a in range(4)]).transpose()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/frameCount*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x13: #not sure but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    count = bs3.readUInt()
                                    for j in range(count):
                                        quaternion = NoeQuat([bs3.readFloat() for a in range(4)]).transpose()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/count*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x15: #confirmed
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    quaternion = NoeQuat([bs3.readFloat() for a in range(4)]).transpose()
                                    rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x16: #not sure at all
                                    # flag to say nothing do be done ?
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    quaternion = NoeQuat([bs3.readShort()/0x7FFF for a in range(4)]).transpose()
                                    rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x17: #not sure at all
                                    # Some weird thing is going on. Normalization or something needed ?							
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    quaternion = NoeAngles([bs3.readShort()/180,0,0]).toQuat()
                                    rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x18: #somewhat confirmed (priestess cloth)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        quaternion = NoeAngles([0,0,bs3.readShort()/180]).toQuat()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/frameCount*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                elif boneHeader.opcode == 0x19: #somewhat confirmed (priestess arms)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        quaternion = NoeAngles([0,bs3.readShort()/180,0]).toQuat()
                                        rotationKeyframedValue = NoeKeyFramedValue(duration/frameCount*j,quaternion)
                                        rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x1A: #need confirm, king boo
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # bs3.readShort()
                                    # quaternion = NoeAngles([bs3.readShort()/180,0,0]).toQuat()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x1B: #seen on maid
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # bs3.readShort()
                                    # quaternion = NoeAngles([bs3.readShort()/180,0,0]).toQuat()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                # elif boneHeader.opcode == 0x1C: #need confirm (pianist tail)
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # bs3.readShort()
                                    # quaternion = NoeAngles([0,bs3.readShort()/180,0]).toQuat()
                                    # rotationKeyframedValue = NoeKeyFramedValue(0,quaternion)
                                    # rotNoeKeyFramedValues[boneHeader.hash].append(rotationKeyframedValue)
                                else:
                                    if hex(boneHeader.opcode) in unknownRotOpcode:
                                        unknownRotOpcode[hex(boneHeader.opcode)] += 1
                                    else:
                                        unknownRotOpcode[hex(boneHeader.opcode)] = 1
                            #location
                            elif boneHeader.type == 3:
                                posNoeKeyFramedValues[boneHeader.hash] = []
                                if boneHeader.opcode == 0x6: #confirmed, somewhat (priestess movement)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        position = NoeVec3([bs3.readFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/frameCount*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0x8: #guess
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    for j in range(frameCount):
                                        position = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/frameCount*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0x9: #to be confirmed but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    count = bs3.readUInt()
                                    for j in range(count):
                                        position = NoeVec3([bs3.readFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xA: #to be confirmed but makes sense
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    count = bs3.readUShort()
                                    for j in range(count):
                                        position = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                # elif boneHeader.opcode == 0xB: #to be confirmed but makes sense
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # position = NoeVec3([bs3.readFloat() for a in range(3)])
                                    # positionKeyFramedValue = NoeKeyFramedValue(0, position)
                                    # posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xC: #confirmed (maid stuff)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    position = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                    positionKeyFramedValue = NoeKeyFramedValue(0, position)
                                    posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xD: #confirmed (pianist movement)
                                    bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    axis = bs3.readUInt()
                                    bs3.readBytes(0x8)
                                    count = bs3.readUInt()
                                    for j in range(count):
                                        data = bs3.readFloat()
                                        if axis == 0:
                                            position = NoeVec3([data,0,0])
                                        elif axis == 1:
                                            position = NoeVec3([0,data,0])
                                        elif axis == 2:
                                            position = NoeVec3([0,0,data])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                elif boneHeader.opcode == 0xE: #confirmed somewhat (Hellen outfit)
                                    bs3.seek(animationAsset.dataOffset+ boneHeader.offset)
                                    a = bs3.readUInt()
                                    bs3.readUShort()
                                    count = bs3.readUShort()
                                    for j in range(count):
                                        position = NoeVec3([bs3.readHalfFloat(),0,0])
                                        positionKeyFramedValue = NoeKeyFramedValue(duration/count*j, position)
                                        posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                else:
                                    if hex(boneHeader.opcode) in unknownPosOpcode:
                                        unknownPosOpcode[hex(boneHeader.opcode)] += 1
                                    else:
                                        unknownPosOpcode[hex(boneHeader.opcode)] = 1
                            #Not confirmed at all, no clue yet. Probably something other than scale
                            # elif boneHeader.type == 2:
                                # scaleNoeKeyFramedValues[boneHeader.hash] = []
                                # posNoeKeyFramedValues[boneHeader.hash] = []
                                # if boneHeader.opcode == 0x2A: #always of length 12 so either 6 HF or 3 F, don't have any clear example
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # scale = NoeVec3([bs3.readHalfFloat() for a in range(3)])
                                    # scaleKeyFramedValue = NoeKeyFramedValue(0, scale)
                                    # scaleNoeKeyFramedValues[boneHeader.hash].append(scaleKeyFramedValue)
                                    # bs3.seek(animationAsset.dataOffset + boneHeader.offset)
                                    # position = NoeVec3([bs3.readFloat() for a in range(3)])
                                    # positionKeyFramedValue = NoeKeyFramedValue(0, position)
                                    # posNoeKeyFramedValues[boneHeader.hash].append(positionKeyFramedValue)
                                # else:
                                    # if hex(boneHeader.opcode) in unknownScaleOpcode:
                                        # unknownScaleOpcode[hex(boneHeader.opcode)] += 1
                                    # else:
                                        # unknownScaleOpcode[hex(boneHeader.opcode)] = 1
                        bs3.seek(checkpoint)
                    # print("anim " + str(animationindex))
                    # print(unknownRotOpcode)
                    # print(unknownPosOpcode)
                    for hash in modelAsset.hashToBoneID71:
                        if hash in posNoeKeyFramedValues or hash in rotNoeKeyFramedValues or hash in scaleNoeKeyFramedValues:
                            actionBone = NoeKeyFramedBone(modelAsset.hashToBoneID71[hash])
                            #root bone rotation ignored as it seem to screw up some stuff
                            if hash in rotNoeKeyFramedValues:# and hash != "0x2e51a3":
                                actionBone.setRotation(rotNoeKeyFramedValues[hash], noesis.NOEKF_ROTATION_QUATERNION_4)
                            if hash in posNoeKeyFramedValues:
                                actionBone.setTranslation(posNoeKeyFramedValues[hash], noesis.NOEKF_TRANSLATION_VECTOR_3)
                            if hash in scaleNoeKeyFramedValues:
                                actionBone.setScale(scaleNoeKeyFramedValues[hash], noesis.NOEKF_SCALE_VECTOR_3)
                            keyframedJointList.append(actionBone)
                    anim = NoeKeyFramedAnim("anim_"+str(animationindex), jointList, keyframedJointList, 30)
                    animationList.append(anim)        
        
        #Geometry
        InitializeFileStream(0, baseID, bufferID, animID)
        InitializeFileStream(2, baseID, bufferID, animID)
        s7103Offset = modelAsset.s7103Offset
        hashToBoneID71 = modelAsset.hashToBoneID71
        for i,mesh in enumerate(modelAsset.meshAssetList):
            CommitMeshTris(bs0, bs2, modelAsset, 0,i, mesh, s7103Offset, hashToBoneID71)
        #Then add all the gears if relevant
        # print()
        for i, gearIndex in enumerate(gearIndices):        
            if gearIndex < 0:
                continue
            texFileIDToListIndex = {}
            dupAsset = pickle.load(open( gearModelFolder + os.sep + "model_" + str(gearIndex) +".strikm", "rb" ))
            baseID, bufferID, animID = dupAsset.baseID, dupAsset.bufferID, dupAsset.animID
            if bLoadMaterials:
                geartextPath = os.path.dirname(gearModelFolder) + os.sep + "Textures"
                for k, fileIdx in enumerate(dupAsset.pairedTextureFileIndices):
                    texFileIDToListIndex[fileIdx] = len(textureList)
                    textureAsset = pickle.load(open( geartextPath+os.sep+"texture_" + str(fileIdx)+".strikt", "rb" ))
                    a = InitializeFileStream(0, textureAsset.textureHeaderFileID,0,0,0,True)
                    b = InitializeFileStream(1, 0,0,0,textureAsset.textureDataFileID,True)
                    if not (a and b):
                        print("texture file couldn't be located")
                        continue
                    processTexture([textureAsset])
                
                #Create materials
                for k, matInfo in enumerate(dupAsset.materialsInfo):
                    material = NoeMaterial('model_' + str(i+1) + '_submesh_' + str(k), "")
                    material.setDefaultBlend(0)
                    # material.setAlphaTest(False)
                    if matInfo[0] >= 0:
                        material.setTexture(textureList[texFileIDToListIndex[matInfo[0]]].name)
                    if matInfo[1] >= 0:
                        material.setNormalTexture(textureList[texFileIDToListIndex[matInfo[1]]].name)
                    materialList.append(material)
            InitializeFileStream(0, baseID, bufferID, animID, 0,True)
            InitializeFileStream(2, baseID, bufferID, animID, 0,True)            
            for j,mesh in enumerate(dupAsset.meshAssetList):
                CommitMeshTris(bs0, bs2,dupAsset, i + 1,j, mesh, s7103Offset, hashToBoneID71)
        try:
            mdl = rapi.rpgConstructModel()
        except:
            mdl = NoeModel()
        mdl.setModelMaterials(NoeModelMaterials(textureList, []))
        if len(jointList) > 0:
            mdl.setBones(jointList)
        if len(animationList) > 0:
            mdl.setAnims(animationList)
            rapi.setPreviewOption("setAnimSpeed", str(30))
        mdl.setModelMaterials(NoeModelMaterials(textureList, materialList))        
        modelList.append(mdl)
            
    
    