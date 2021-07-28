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
__all__ =['urlSearch',
          'pageSize',
          'methodB',
          'methodF',
          'rdpEpsi',
          'dicTolerance',
          'nameAoi',
          'nameSearchFull',
          'nameBlock',
          'nameBFile',
          'extSceneIn',
          'tempGeojson',
          'tempDescripPair',
          'profileCoverTif',
          'imageGsd',
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
              'satAz': 10 # similarity angle
                }

# Desciptor variables
nameAoi='{}_AOI'
nameSearchFull='{}_FullSearch'
nameBlock='B{}'
nameBFile='{}_{}'
extSceneIn='.cmo'
tempGeojson={"type": "FeatureCollection",
                "name": "",
                "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
                "features": []
                }
tempDescripPair={"type": "Feature",
            "id": -1,
            "properties":{'type':'', 'nbScene': '','scenes':'', 'area':0 },
            "geometry": {"type": "Polygon", "coordinates":[]}}
profileCoverTif={'driver': 'GTiff', 'dtype': 'uint8', 'nodata': 0, 'width': 0, 'height': 0, 'count': 1, 'compress': 'lzw', 'crs': 0, 'transform': 0}
imageGsd=1e-4 # outcoming image gsd 1e-4[°]=[m]/6371e3*180/pi ~10[m]

## PCT
lstLevel=('L0','L1A','L1B')
lstAction=('create','list','match','download')

#  Creation variables
dicLevel={'L1A': ('L1A','{}_1A_Analytic_DN.tif','Multistripe_L1A_DN')}
nameFeat='{}.cmo'
nameBucket='valintern_dsmps_{}_{}'



# Job system variables
nameJobFile='{}_BucketNBatch-{}.txt'

## ASfM
# Camera parameter variable
nameProcData='{}_ProcData'
nameProcDataImg='{}_gB.tif' # matching with ASfMlib_ba.SingleBandImg process

nameTsai0='{}_Dist0No.tsai'
nameTsai1='{}_Dist1Rpc.tsai'
nameTsai2='{}_Dist2Adj.tsai'

namePairDescip='{}_StereoPairs.txt'

## MSS