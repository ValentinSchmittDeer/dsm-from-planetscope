#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

'''
All variables gathered in one place
'''
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =[# SSBP
          'urlSearch',
          'pageSize',
          'methodB',
          'methodF',
          'rdpEpsi',
          'dicTolerance',
          'nameBlock',
          'extSceneIn',
          'tempGeojson',
          'tempDescripPair',
          'profileCoverTif',
          'dicUnits',
          'imageGsd',
          'fileAoi',
          'fileSearchFull',
          'fileSelec',
          'fileStereo',
          'fileSceneId',
          'fileCov',
          'fileBHfTrack',
          'satAz_Val',
          'satAz_Name',
          'satAz_Tol',
          # PCT
          'lstLevel',
          'lstAction',
          'dicLevel',
          'nameFeat',
          'nameBucket',
          'nameJobFile',
          # BlockProc
          'PathCur',
          # ASfM
          'camCentre',
          'camFocal',
          'camPitch',
          #'camDistBa',
          #'camDistExp',
          #'factConstSat',
          'tolPairArea',
          'tolAxisAngle',
          'tolDispDiff',
          'gsdOrth',
          ## MSS
          'gsdDsm',

          ]

import os, json
from glob import glob
from OutLib.LoggerFunc import SetupLogger, SubLogger
SetupLogger(name=__name__)
        
## SSBP
# Search variables
urlSearch= 'https://api.planet.com/data/v1/searches'
pageSize=5

# Block variables
methodB=('one','month','dir') # Block creation method
methodF=('fp','bh') # Filter method
rdpEpsi=1e-2 # Douglas peuker epsilon
dicTolerance={'geom': 0.8, # percentage of overlap
              'quali': ('standard','test'), # list of quality (best to worst)
              'satAz': 10, # similarity angle
              'bhAreaPair': 1e-3, # minimum pair area for BH filtering
              'bhAreaInter': 1e-7, # minimum intersection area for BH filtering: must be small
              'bhBadGeom': ('Point', 'MultiPoint', 'LineString', 'MultiLineString') # bad intresection geometry to discard
                }

# Desciptor variables
nameBlock='B{}'
extSceneIn='.cmo'
tempGeojson={"type": "FeatureCollection",
                "name": "",
                "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
                "Features": []
                }
tempDescripPair={"type": "Feature",
            "id": -1,
            "properties":{'id': 0, 'type':'stereo', 'nbScene': '','scenes':'', 'scenesI': '', 'area':0 },
            "geometry": {"type": "Polygon", "coordinates":[]}}
profileCoverTif={'driver': 'GTiff', 'dtype': 'uint16', 'nodata': 0, 'width': 0, 'height': 0, 'count': 1, 'compress': 'lzw', 'crs': 0, 'transform': 0}
dicUnits={'alt': 'km',
                 'lat': 'deg',
                 'lng': 'deg',
                 'off_nadir': 'deg',
                 'satellite_azimuth_mean': 'deg',
                 }
imageGsd=1e-4 # outcoming image gsd 1e-4[°]=[m]/6371e3*180/pi ~10[m]
fileAoi='{}_AOI.geojson'
fileSearchFull='{}_FullSearch.json'
fileSelec='{}_Select.geojson'
fileStereo='{}_Stereo.geojson'
fileSceneId='{}_SceneId.txt'
fileCov='{}_Coverage.tif'
fileBHfTrack='{}_BHfTrack.geojson'

# Orbits
satAz_Val=(-180, -110, -83, 85, 100, 110, 277, 180)
satAz_Name=('descending', 'ascending', 'descending', 'ascending', 'descending', 'descending', 'descending', 'descending')
satAz_Tol=10

## PCT
lstLevel=('L0','L1A','L1B')
lstAction=('info', 'create','list','match','download')

#  Creation variables
dicLevel={'L1A': ('L1A','{}_1A_Analytic_DN.tif','Multistripe_L1A_DN')}
nameFeat='{}.cmo'
nameBucket='valintern_dsmps_{}_{}_{}'


# Job system variables
nameJobFile='{}_BucketNBatch-{}.txt'

## BlockProc
class PathCur:
    '''
    Create and store needed path
    
    pathDir (str): path repository with all blocks in
    bId (str): block ID (name)
    out:
        PathCur (obj): Object holding paths
            pB: block folder
            pDem: DEM path
            pData: downloaded data directory
            pProcData: data for processing directory
            l: product level
            extFeat: scene name extrension
            baKP: Key point folder
            baEO: EO folder
            baIO: IO folder
    '''
    def __init__(self, pathDir, bId, nameAoi, checkRoutine=True):
        # Folder
        self.pB=os.path.join(pathDir, bId)
        lstFolder=glob(os.path.join(self.pB, nameBucket.format(nameAoi, bId,'???')))
        if checkRoutine and not len(lstFolder)==1: SubLogger('CRITICAL', 'Local data folder not (or several exist)')
        self.pData=lstFolder[0] if len(lstFolder)==1 else 'Fake_L1A'
        self.pProcData='{}_ProcData'.format(self.pData)
        if checkRoutine and not os.path.exists(self.pProcData): os.mkdir(self.pProcData)
        self.pPdalDir=os.path.join(pathDir, bId, 'PDAL_Json')
        if checkRoutine and not os.path.exists(self.pPdalDir): os.mkdir(self.pPdalDir)
        self.pPcFullDir=os.path.join(pathDir, bId, 'PDAL_PC-Full-Tiles')
        if checkRoutine and not os.path.exists(self.pPcFullDir): os.mkdir(self.pPcFullDir)
        self.pPcFltDir=os.path.join(pathDir, bId, 'PDAL_PC-Filtered-Tiles')
        if checkRoutine and not os.path.exists(self.pPcFltDir): os.mkdir(self.pPcFltDir)
        self.pDsmDir=os.path.join(pathDir, bId, 'PDAL_DSM-Tiles')
        if checkRoutine and not os.path.exists(self.pDsmDir): os.mkdir(self.pDsmDir)

        # Level
        self.l=self.pData.split('_')[-1]
        if checkRoutine and not self.l in dicLevel.keys(): SubLogger('CRITICAL', 'Level unknown')

        # Files
        #   ASfM
        self.pDemGrad=os.path.join(self.pB, 'DEM_Gradient_DoG.tif')
        self.pStereoLst=os.path.join(self.pB, '{}_Stereo.txt'.format(bId))
        #self.pOrbit=os.path.join(self.pB,'%s_InitialCam.kml'% bId)
        self.pOrtho=os.path.join(self.pB, 'ASP_Ortho{1}', '{0}_Ortho{1}.tif')
        #   MSS
        self.pStereoDM=os.path.join(self.pB, '{}_StereoDM.geojson'.format(bId))
        self.pJsonSource=os.path.join(self.pPdalDir, 'Pdal_SourceID.json')
        self.pJsonRast_WA=os.path.join(self.pPdalDir, 'Pdal_Rasterize-WeightedAve.json')
        self.pJsonFilter=os.path.join(self.pPdalDir, 'Pdal_Filter.json')
        self.pPcFullTile=os.path.join(self.pPcFullDir, 'PC-Full-Tile_#.las')
        self.pPcFullList=os.path.join(self.pPcFullDir, 'PC-Full-List.txt')
        self.pPcFltTile=os.path.join(self.pPcFltDir, 'PC-Filtered-Tile_{}.las')
        self.pDsmTile=os.path.join(self.pDsmDir, 'DSM-Tile_{}.tif')
        self.pDsmFinal=os.path.join(self.pDsmDir, 'DSM-Final.tif')

        # Extention
        #   ASfM
        self.extFeat=dicLevel[self.l][1]
        self.extRpc='{}_RPC.TXT'.format(self.extFeat[:-4])
        self.extRpcNdisto='{}_RPCnoDisto.TXT'.format(self.extFeat[:-4])
        self.extFeat1B='{}_1b.tif'#.format(self.extFeat[:-4])
        self.extRpc1B='{}_RPC.TXT'.format(self.extFeat1B[:-4])
        self.extRpc1Bx='{}.XML'.format(self.extFeat1B[:-4])
        self.extFeatKP='{}_KP.tif'#.format(self.extFeat[:-4])
        self.extRpcKP='{}_RPC.TXT'.format(self.extFeatKP[:-4])
        self.nTsai=('{}_0Rough.tsai', 
                    '{}_1Init.tsai',
                    '{}_2Adj.tsai')
        #   MSS
        self.extPC='-PC_{}.las'


        # Prefix
        #   ASfM
        self.prefStereoKP= os.path.join(pathDir, bId, 'ASP_StereoKeyPoints','SKP')
        self.prefKP= os.path.join(pathDir, bId, 'ASP_KeyPoints','KP')
        self.prefEO= os.path.join(pathDir, bId, 'ASP_Extrinsic','EO')
        self.prefIO= os.path.join(pathDir, bId, 'ASP_Intrinsic','IO')
        self.prefFix=os.path.join(pathDir, bId, 'ASP_Fix','FIX')
        #   MSS
        self.prefStereoDM= os.path.join(pathDir, bId, 'ASP_StereoDenseMatch', 'SDM')
        self.prefProcDM= os.path.join(pathDir, bId, 'ASP_StereoDenseMatch', 'DMproc')  


    def __str__(self):
      return json.dumps(self.__dict__, indent='\t', separators=(',', ':'))

## ASfM
# Dove-C, in  pxl: f=127090.909, c=3300 2200, p=1
# Dove-C, in  mm: f=699, c=18.15 12.1, p=5.5e-3
camCentre=(18.15, 12.1)
camFocal=699
camPitch=5.5e-3
#<TsaiLensDistortion|BrownConradyDistortion|RPC (default: TsaiLensDistortion)>
#camDistBa='TsaiLensDistortion'
#camDistExp='BrownConradyDistortion'
#factConstSat=1e-9

tolPairArea=1e-4
tolAxisAngle=80
tolDispDiff=1
gsdOrth=4

## MSS
gsdDsm=4


