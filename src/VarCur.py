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
          'camDistBa',
          'camDistExp',
          'factConstSat',
          'gsdOrth',
          ## MSS
          'methodDM',

          ]

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
profileCoverTif={'driver': 'GTiff', 'dtype': 'uint8', 'nodata': 0, 'width': 0, 'height': 0, 'count': 1, 'compress': 'lzw', 'crs': 0, 'transform': 0}
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

## PCT
lstLevel=('L0','L1A','L1B')
lstAction=('info', 'create','list','match','download')

#  Creation variables
dicLevel={'L1A': ('L1A','{}_1A_Analytic_DN.tif','Multistripe_L1A_DN')}
nameFeat='{}.cmo'
nameBucket='valintern_dsmps_{}_{}'


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
    def __init__(self, pathDir, bId, pathDem, checkRoutine=True):
      import os
      from glob import glob
      from OutLib.LoggerFunc import SetupLogger, SubLogger
      SetupLogger(name=__name__)

      self.pB=os.path.join(pathDir, bId)
      self.pDem=pathDem
      self.pStereoLst=os.path.join(self.pB, '{}_Stereo.txt'.format(bId))
      self.pOrbit=os.path.join(self.pB,'%s_InitialCam.kml'% bId)

      lstFolder=glob(os.path.join(self.pB, nameBucket.format('*','???')))
      
      if checkRoutine and not len(lstFolder)==1: SubLogger('CRITICAL', 'Local data folder not (or several exist)')
      self.pData=lstFolder[0] if len(lstFolder)==1 else 'Fake_L1A'

      self.pProcData='{}_ProcData'.format(self.pData)
      if checkRoutine and not os.path.exists(self.pProcData): os.mkdir(self.pProcData)

      #'pPairs': os.path.join(pathDir, bId, bId+'_KPpairs.txt'),

      self.l=self.pData.split('_')[-1]
      if checkRoutine and not self.l in dicLevel.keys(): SubLogger('CRITICAL', 'Level unknown')

      self.extFeat=dicLevel[self.l][1]

      self.prefStereoKP= os.path.join(pathDir, bId, 'ASP_StereoKeyPoints','SKP')
      self.prefKP= os.path.join(pathDir, bId, 'ASP_KeyPoints','KP')
      self.prefEO= os.path.join(pathDir, bId, 'ASP_Extrinsic','EO')
      ### Std KP
      self.prefKP_std= os.path.join(pathDir, bId, 'ASP_KeyPoints-Std','KP')
      self.prefEO_std= os.path.join(pathDir, bId, 'ASP_Extrinsic-Std','EO')

      self.prefIO= os.path.join(pathDir, bId, 'ASP_Intrinsic','IO')
      self.prefFix=os.path.join(pathDir, bId, 'ASP_Fix','FIX')

      self.prefDM= os.path.join(pathDir, bId, 'ASP_DenseMatch', 'DM')

      self.extFeat1B='{}_1b.tif'.format(self.extFeat[:-4])
      self.nTsai=('{}_0Rough.tsai', 
                  '{}_1Init.tsai',
                  '{}_2Adj.tsai',
                )
      
      self.pOrtho=os.path.join(self.pB, 'ASP_Ortho{1}', '{0}_Ortho{1}.tif')

    def __str__(self):
      return str(self.__dict__)

## ASfM
# Dove-C, in  pxl: f=127090.909, c=3300 2178, p=1
# Dove-C, in  mm: f=699, c=18.15 12.1, p=5.5e-3
camCentre=(18.15, 12.1)
camFocal=699
camPitch='5.5e-3'
#<TsaiLensDistortion|BrownConradyDistortion|RPC (default: TsaiLensDistortion)>
camDistBa='TsaiLensDistortion'
camDistExp='BrownConradyDistortion'
factConstSat=1e-6

gsdOrth=4

## MSS
methodDM=('PW', 'MVS')