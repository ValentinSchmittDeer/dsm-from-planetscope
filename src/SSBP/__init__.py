#!/usr/bin/env python
# -*- coding: UTF-8 -*-'''

'''
Stereo-Scene Block Parsing
'''
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['SSBPlib_search', 'SSBPlib_block','lstBMethod','lstBFilter','nameAoi','nameOutFull','basicGeojson']

# Search variables
urlSearch= 'https://api.planet.com/data/v1/searches'
pageSize=5

# Block variables
lstBMethod=('one','month','dir') # Block creation method
lstBFilter=('fp',) # Filter method
rdpEpsi=1e-2 # Douglas peuker epsilon
dicTolerance={'geom': 0.9, # percentage of overlap
              'quali': ('standard','test'), # list of quality (best to worst)
              'satAz': 10 # similarity angle
                }

# New Component variable
dicCouple={"type": "Couple",
            "properties":{'Scene1':'', 'Scene2':'', 'area':0 },
            "geometry": {"type": "Polygon", "coordinates":[]}}

# Writing variable
nameAoi='{}_AOI'
nameOutFull='{}_FullSearch'
nameBlock='B{}'
nameBlockFile='{}_{}'
sceneIdExt='.cmo'
basicGeojson={"type": "FeatureCollection",
                "name": "",
                "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
                "features": []
                }
profileCoverTif={'driver': 'GTiff', 'dtype': 'uint8', 'nodata': 0, 'width': 0, 'height': 0, 'count': 1, 'compress': 'lzw', 'crs': 0, 'transform': 0}
imageGsd=1e-4 # outcoming image gsd 1e-4[°]=[m]/6371e3*180/pi ~10[m]