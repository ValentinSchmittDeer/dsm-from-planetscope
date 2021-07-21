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
from pprint import pprint

from PVL.PVL_Logger import SetupLogger, SubLogger

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =[]
SetupLogger(name=__name__)

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

def OverlapMask(descrip, pathImg, pathCam, pathDem, pathOut, margin=10):
    '''
    Caution: image unit is assumed to be pixel, check in case of mm camera model
    '''
    if not os.path.exists(pathImg): SubLogger(logging.CRITICAL, 'Image not found: %s'% pathImg)
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

    # Image part
    with rasterio.open(pathImg) as srcImg:
        profileOut = srcImg.profile
    profileOut['dtype']=np.dtype('uint8')
    profileOut['driver']='tiff'
    shapeOut=(profileOut['height'], profileOut['width'])
    
    matMask=features.geometry_mask((geomMask,), shapeOut, profileOut['transform'], all_touched=True, invert=True)
    matMaskLarg=binary_dilation(matMask, np.ones([2*margin+1,2*margin+1])).astype(int)
    
    try:
        with rasterio.open(pathOut, 'w', **profileOut) as dstImg:
            dstImg.write(matMaskLarg*255,1)
    except :
        pass # this is due to georeferencement used by GDAL and rasterio
    
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
            '--alignment-method', 'none', # skip the additionall alignement
            '--stereo-algorithm', '1', # 1:SGM, 2:MGM
            #'--corr-tile-size', 
            lstImg[0],
            lstImg[1],
            lstTsai[0],
            lstTsai[1],
            prefOut,
            ]
    return subArgs

def P2DParam(pathPCIn):
    # Arguments
    subArgs=['--transverse-mercator',
            '--nodata-value', '-32767',
            '--t_srs', 'EPSG:32611',
            '--errorimage', 
            pathPCIn,
            ]
    return subArgs

SubLogger(logging.WARNING, 'jojo')

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
