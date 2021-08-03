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

WGS84=(6378137,1/298.25722)
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def BlockPathDict(pathDir, bId):
    '''
    Create a dictonary with all needed path related to the block name
    
    pathDir (str): path repository with all blocks in
    dId (str): block ID (name)
    out:
        dicOut (dict): dictionary with path as value
            pB:
            pDem:
            pData:
            pProcData:
            l: product level
            lTup: 
            baKP:
            baEO:
            baIO:


    '''
    from ASfM import nameProcData
    from PCT import nameBucket, dicLevel

    lstFolder=glob(os.path.join(pathDir, bId, nameBucket.format('*','*')))
    if not lstFolder: 
        SubLogger(logging.ERROR, 'Data are not found locally')
        return True
    lstFolder.sort()
    pathData=lstFolder[0]
    pathProcData=nameProcData.format(pathData)
    if not os.path.exists(pathProcData): os.mkdir(pathProcData)

    level=pathData.split('_')[-1]
    if not level in dicLevel.keys():
        SubLogger(logging.ERROR, 'Level unknown')
        return True

    dicOut= {'pB': os.path.join(pathDir, bId),
            'pData': pathData,
            'pProcData': pathProcData,
            #'pPairs': os.path.join(pathDir, bId, bId+'_KPpairs.txt'),
            'l': level,
            'lTup': dicLevel[level],
            'pDm': os.path.join(pathDir, bId, 'ASP-DenseMatch', 'DM')
            }

    return dicOut

def Geo2Cart_Elli(ptGeo,elliAF=WGS84):
    lam, phi, h=ptGeo
    phi=phi*pi/180
    lam=lam*pi/180
    a,f=elliAF
    
    e2=2*f-f**2
    n=a/(1-e2*sin(phi)**2)**0.5
    
    x=(n+h)*cos(phi)*cos(lam)
    y=(n+h)*cos(phi)*sin(lam)
    z=((1-e2)*n+h)*sin(phi)
    
    return np.array([x,y,z]).reshape(3,1)

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

def StereoParam(lstImg, lstTsai, prefOut):
    # Arguments
    subArgs=['--skip-rough-homography',
            '-t', 'nadirpinhole',
            #'-e', '1', # starting point into the full (Preprocessing), (Disparity), (Blend), (Sub-pixel Refinement), (Outlier Rejection and Hole Filling), (Triangulation)
            '--alignment-method', 'affineepipolar', # affineepipolar|homography|epipolar|none: makes uses of initial adjustmet
            '--stereo-algorithm', '1', # 1:SGM (needs parallel_stereo), 2:MGM
            #'--corr-tile-size',
            '--individually-normalize',
            '--ip-detect-method', '1', # stereo_corr coarse correlation: key point algo
            #'--prefilter-mode',
            #'disparity map initialization' #1:box filter-like accumulator; 2:coarse-to-fine pyramid based; 3:disparity search space into sub-regions with similar values of disparity
            ]
    subArgs+=lstImg
    subArgs+=lstTsai
    subArgs.append(prefOut)

    return subArgs

def P2DParam(pathPCIn):
    # Arguments
    subArgs=['--transverse-mercator',
            '--nodata-value', '-32767',
            '--t_srs', 'EPSG:32611',
            ' ', 
            pathPCIn,
            ]
    return subArgs

def P2LParam(pathPCIn):
    # Arguments
    subArgs=['--datum', 'WGS84', 
            '--t_srs', 'EPSG:32611', 
            pathPCIn,
            '-o', pathPCIn.replace('.tif','.las')
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
        
