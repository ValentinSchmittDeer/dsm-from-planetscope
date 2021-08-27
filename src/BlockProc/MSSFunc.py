#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from math import pi, sin, cos, ceil
from glob import glob
import numpy as np
from numpy.linalg import inv
import rasterio
from shapely.geometry import Polygon

from pprint import pprint

from OutLib.LoggerFunc import *
from VarCur import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =[]
SetupLogger(name=__name__)
#SubLogger(logging.WARNING, 'jojo')

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def OverlapMask(descrip, pathMask, pathCam, pathDem, margin=10):
    '''
    Caution: image unit is assumed to be pixel, check in case of mm camera model
    '''
    if not os.path.exists(pathMask): SubLogger(logging.CRITICAL, 'Mask image not found: %s'% pathMask)
    if not os.path.exists(pathCam): SubLogger(logging.CRITICAL, 'Camera file not found: %s'% pathCam)
    
    from rasterio import features
    from scipy.ndimage.morphology import binary_dilation
    from MSS.MSSlib_asp import ObjTsai

    # Read DTM
    imgDem=rasterio.open(pathDem)
    if not imgDem.crs=='EPSG:4326': SubLogger(logging.CRITICAL, 'DEM mustr be in 4326, not %s'% imgDem.crs)
    frameDem=imgDem.read(1)
    
    # Read Camera
    camIn=ObjTsai(pathCam)

    # Vector reading
    if not descrip['geometry']['type']=='Polygon': SubLogger(logging.CRITICAL, 'Such geometry is not managed yet: %s'% descrip['geometry']['type'])
    geomIn=descrip['geometry']['coordinates'][0]
    
    # Vector projection
    geomImg=[]
    for ptIn in geomIn:
        ptZ=frameDem[imgDem.index(ptIn[0], ptIn[1])]
        pt3D=Geo2Cart_Elli(ptIn+[ptZ])
        pt3D_h=np.vstack((pt3D, 1))
        
        ptImg_h=camIn['matP_h']@pt3D_h
        ptImg=(ptImg_h[:2]/ptImg_h[2]).flatten()
        geomImg.append(list(ptImg))

    del frameDem
    imgDem.close()
    geomMask={"type": 'Polygon', 'coordinates': [list(geomImg)]}

    # Image part: using rasterio for not georef image returns warnings
    with rasterio.open(pathMask) as srcImg:
        profileOut = srcImg.profile
    shapeOut=(profileOut['height'], profileOut['width'])
    
    matMask=features.geometry_mask((geomMask,), shapeOut, profileOut['transform'], all_touched=True, invert=True)
    matMaskLarg=binary_dilation(matMask, np.ones([2*margin+1,2*margin+1])).astype('uint8')
    
    with rasterio.open(pathMask, 'w', **profileOut) as dstImg:
        dstImg.write(matMaskLarg*255,1)
    
    # Correlation tile size
    bbox=features.bounds(geomMask)
    tileSize=(ceil(min(bbox[3]+margin,shapeOut[0])-max(bbox[1]-margin,0)), # height,
              ceil(min(bbox[2]+margin,shapeOut[1])-max(bbox[0]-margin,0))) # width

    return tileSize

def SubArgs_Stereo(lstImg, lstTsai, prefOut):
    # Arguments
    subArgs=['-t', 'nadirpinhole', # mode
             #'-e', '1', # starting point 1:Preprocessing, 2:Disparity, 3:Blend, 4:Sub-pixel Refinement, 5:Outlier Rejection and Hole Filling, 6:Triangulation
             ## Preprocessing
             '--alignment-method', 'epipolar', # transformation method affineepipolar|homography|epipolar|none: see "Preparation" in mss_main
             #'--individually-normalize', # image radio normalisation
             #'ip-per-tile', '1000' # key point extraction number per tile (case of alignement method)
             '--ip-detect-method', '1', # key point algorithm 0:OBAlgG, 1:SIFT, 2:ORB (case of alignement method)
             #'--no-data', '0',
             '--force-reuse-match-files', # # use former match file: ?using -o prefix?
             '--skip-rough-homography', # avoid the datum-based homography 
             ## Correlation
             #'--prefilter-mode', '2', # Preprocessing method 
             #'corr-seed-mode', '1', # correltion method
             '--min-num-ip', '10', # quit the process based on number of key point. 
             #'cost-mode', '2', # # correlation cost function method
             #'--stereo-algorithm', '1', # 1:SGM (needs parallel_stereo), 2:MGM
             #'--corr-tile-size', '6400 ', # Value of --corr-tile-size is 1024 but image size is Vector2(1337,1295).
                 #Increase --corr-tile-size so the entire image fits in one tile, or use parallel_stereo. Not that making --corr-tile-size larger than 9000 or so may cause GDAL to crash.
            #'disparity map initialization' #1:box filter-like accumulator; 2:coarse-to-fine pyramid based; 3:disparity search space into sub-regions with similar values of disparity
             ## Subpixel Refinement
             #'--subpixel-mode', '1' # subprixel function fitted
             #'--phase-subpixel-accuracy', '20' # max pixel division denominator (1/x)
             ## Filtering
             #'--filter-mode', '1' # filtering mode 
             ## Triangulation
             #'--universe-center', 'None' # point cloud filtering based on distance to "universe", None|Camera|Zero
             #'--bundle-adjust-prefix', str #
             #'--min-triangulation-angle', '0.0' # angle in ° fullfilled for triangulation
             #'--point-cloud-rounding-error', '0.0' # point cloud rounding value in m, 1/20**10 = 1mm
             #'--compute-error-vector', # Save the error vectore rather than just its legnth, Stored in -PC
            ]
    subArgs+=lstImg
    subArgs+=lstTsai
    subArgs.append(prefOut)

    return subArgs

def SubArgs_P2D(pathPCIn):
    # Arguments
    subArgs=['--transverse-mercator',
            '--nodata-value', '-32767',
            '--t_srs', 'EPSG:32611',
            ' ', 
            pathPCIn,
            ]
    return subArgs

def SubArgs_P2L(pathPCIn):
    # Arguments
    subArgs=['--datum', 'WGS84', 
            '--t_srs', 'EPSG:32611', 
            pathPCIn,
            '-o', pathPCIn.replace('.tif','')
            ]
    return subArgs

def MvsAddImg(descrip, lstDescrip):
    # Vector reading
    geomIn=Polygon(descrip['geometry']['coordinates'][0])
    lstIdIn=[descrip['properties'][key] for key in descrip['properties'] if key.startswith('scene')]
    
    lstIdNew=[]
    for descripCur in lstDescrip:
        if not descripCur['geometry']['type']=='Polygon': continue
        geomNew=Polygon(descripCur['geometry']['coordinates'][0])
        if not geomNew.intersects(geomIn): continue
        newId=[descripCur['properties'][key] for key in descrip['properties'] if key.startswith('scene')]
        lstIdNew+=[idCur for idCur in newId if not idCur in lstIdIn and not idCur in lstIdNew]
    
    return lstIdNew



#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
