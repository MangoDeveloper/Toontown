import sys
import zlib

from pandac.PandaModules import *
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from direct.showbase import Loader
from direct.stdpy.file import *

import DNAAnimBuilding
import DNAAnimProp
import DNABattleCell
import DNACornice
import DNADoor
import DNAError
import DNAFlatBuilding
import DNAFlatDoor
import DNAGroup
import DNAInteractiveProp
import DNALandmarkBuilding
import DNANode
import DNAProp
import DNASign
import DNASignBaseline
import DNASignGraphic
import DNASignText
import DNAStreet
import DNASuitPoint
import DNAUtil
import DNAVisGroup
import DNAWall
import DNAWindows

sys.setrecursionlimit(10000)

compClassTable = {
1: DNAGroup.DNAGroup,
2: DNAVisGroup.DNAVisGroup,
3: DNANode.DNANode,
4: DNAProp.DNAProp,
5: DNASign.DNASign,
6: DNASignBaseline.DNASignBaseline,
7: DNASignText.DNASignText,
8: DNASignGraphic.DNASignGraphic,
9: DNAFlatBuilding.DNAFlatBuilding,
10: DNAWall.DNAWall,
11: DNAWindows.DNAWindows,
12: DNACornice.DNACornice,
13: DNALandmarkBuilding.DNALandmarkBuilding,
14: DNAAnimProp.DNAAnimProp,
15: DNAInteractiveProp.DNAInteractiveProp,
16: DNAAnimBuilding.DNAAnimBuilding,
17: DNADoor.DNADoor,
18: DNAFlatDoor.DNAFlatDoor,
19: DNAStreet.DNAStreet
}

childlessComps = (
7, # DNASignText
11, # DNAWindows
12, # DNACornice
17, # DNADoor
18, # DNAFlatDoor
19 # DNAStreet
)

class DNALoader(Loader.Loader):

    def __init__(self, base):
        Loader.Loader.__init__(self, base)
        self.dnaStorage = None
        self.prop = None

    def destroy(self):
        del self.dnaStorage
        del self.prop

    def pdnaModel(self, *args, **kw):
        ret = Loader.Loader.loadModel(self, *args, **kw)
        if ret:
            gsg = base.win.getGsg()
            if gsg:
                ret.prepareScene(gsg)
        return ret

    def pdnaTexture(self, texturePath, alphaPath = None, okMissing = False):
        return Loader.Loader.loadTexture(self, texturePath, alphaPath, okMissing=okMissing)

    def pdnaFont(self, *args, **kw):
        return Loader.Loader.loadFont(self, *args, **kw)

    def loadDNAFile(self, dnaStorage, kill):
        self.loadDNAFileBase(dnaStorage, kill)
        nodePath = NodePath(PandaNode('dna'))
        self.prop.traverse(nodePath, self.dnaStorage)
        return nodePath

    def loadDNAFileBase(self, dnaStorage, kill):
        self.dnaStorage = dnaStorage
        dnaFile = open(kill, 'rb')
        dnaData = dnaFile.read()
        dg = PyDatagram(dnaData)
        dgi = PyDatagramIterator(dg)
        dnaFile.close()
        header = dgi.extractBytes(5)
        if header != 'PDNA\n':
            raise DNAError.DNAError('Invalid header: %s' % (header))
        compressed = dgi.getBool()
        dgi.skipBytes(1)
        if compressed:
            data = dgi.getRemainingBytes()
            data = zlib.decompress(data)
            dg = PyDatagram(data)
            dgi = PyDatagramIterator(dg)
        self.handleStorageData(dgi)
        self.handleCompData(dgi)

    def handleCompData(self, dgi):
        while True:
            propCode = dgi.getUint8()
            if propCode == 255:
                if self.prop == None:
                    raise DNAError.DNAError('Unexpected 255 found.')
                prop = self.prop.getParent()
                if prop is not None:
                    self.prop = prop
                else:
                    assert self.prop.getName() == 'root'
            elif propCode in compClassTable:
                propClass = compClassTable[propCode]
                if propClass.__init__.func_code.co_argcount > 1:
                    newComp = propClass('unnamed_comp')
                else:
                    newComp = propClass()
                if propCode == 2:
                    newComp.makeFromDGI(dgi, self.dnaStorage)
                    self.dnaStorage.storeDNAVisGroup(newComp)
                else:
                    newComp.makeFromDGI(dgi)
            else:
                raise DNAError.DNAError('Invalid prop code: %d' % propCode)
            if dgi.getRemainingSize():
                if propCode != 255:
                    if self.prop is not None:
                        newComp.setParent(self.prop)
                        self.prop.add(newComp)
                    if propCode not in childlessComps:
                        self.prop = newComp
                continue
            break

    def handleStorageData(self, dgi):
        # Catalog Codes
        numRoots = dgi.getUint16()
        for _ in xrange(numRoots):
            root = DNAUtil.dgiExtractString8(dgi)
            numCodes = dgi.getUint8()
            for i in xrange(numCodes):
                code = DNAUtil.dgiExtractString8(dgi)
                self.dnaStorage.storeCatalogCode(root, code)

        # Textures
        numTextures = dgi.getUint16()
        for _ in xrange(numTextures):
            code = DNAUtil.dgiExtractString8(dgi)
            filename = DNAUtil.dgiExtractString8(dgi)
            self.dnaStorage.storeTexture(code, self.pdnaTexture(filename, okMissing=True))

        # Fonts
        numFonts = dgi.getUint16()
        for _ in xrange(numFonts):
            code = DNAUtil.dgiExtractString8(dgi)
            filename = DNAUtil.dgiExtractString8(dgi)
            self.dnaStorage.storeFont(code, self.pdnaFont(filename))

        # Nodes
        self.handleNode(dgi, target=self.dnaStorage.storeNode)
        self.handleNode(dgi, target=self.dnaStorage.storeHoodNode)
        self.handleNode(dgi, target=self.dnaStorage.storePlaceNode)

        # Blocks
        numBlocks = dgi.getUint16()
        for _ in xrange(numBlocks):
            number = dgi.getUint8()
            zone = dgi.getUint16()
            title = DNAUtil.dgiExtractString8(dgi)
            article = DNAUtil.dgiExtractString8(dgi)
            bldgType = DNAUtil.dgiExtractString8(dgi)
            self.dnaStorage.storeBlock(number, title, article, bldgType, zone)

        # Suit Points
        numPoints = dgi.getUint16()
        for _ in xrange(numPoints):
            index = dgi.getUint16()
            pointType = dgi.getUint8()
            x, y, z = (dgi.getInt32() / 100.0 for i in xrange(3))
            graph = dgi.getUint8()
            landmarkBuildingIndex = dgi.getInt8()
            self.dnaStorage.storeSuitPoint(
                DNASuitPoint.DNASuitPoint(index, pointType, LVector3f(x, y, z), landmarkBuildingIndex))

        # Suit Edges
        numEdges = dgi.getUint16()
        for _ in xrange(numEdges):
            index = dgi.getUint16()
            numPoints = dgi.getUint16()
            for i in xrange(numPoints):
                endPoint = dgi.getUint16()
                zoneId = dgi.getUint16()
                self.dnaStorage.storeSuitEdge(index, endPoint, zoneId)

        # Battle Cells
        numCells = dgi.getUint16()
        for _ in xrange(numCells):
            w = dgi.getUint8()
            h = dgi.getUint8()
            x, y, z = (dgi.getInt32() / 100.0 for i in xrange(3))
            self.dnaStorage.storeBattleCell(DNABattleCell.DNABattleCell(w, h, LVector3f(x, y, z)))

    def handleNode(self, dgi, target=None):
        if target is None:
            return
        numNodes = dgi.getUint16()
        for _ in xrange(numNodes):
            code = DNAUtil.dgiExtractString8(dgi)
            file = DNAUtil.dgiExtractString8(dgi)
            node = DNAUtil.dgiExtractString8(dgi)
            np = NodePath(self.pdnaModel(file))
            if node:
                newNode = np.find('**/' + node).copyTo(NodePath())
                np.removeNode()
                np = newNode
            np.setTag('DNACode', code)
            np.setTag('DNARoot', node)
            target(np, code)