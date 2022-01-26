#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import numpy as np
from pprint import pprint

from importlib.util import find_spec
checkPlanetCommon=find_spec('planet_opencv3') is not None
if checkPlanetCommon:
    from planet_opencv3 import cv2 as cv
else:
    import cv2 as cv

from OutLib.LoggerFunc import *
from VarCur import *
from PCT.dataFunc import CheckPC
from BlockProc import GeomFunc

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['ExtractOriOffeset', 'ExtractDisto']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')

gdInfo='gdalinfo'

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def ExtractFrameOffset(pathIn, rpcIn=None, nbTile=1):
    '''
    Return the origin offset (top-left) because Dove-Clasic L1A products 
    are not all cropped the same. Offset = L0_origin (top-left) w.r.t. 
    cropped scene origin.
    From tif input, hard coded and known scene height select 
    the right offset.
    It can be replaced by RPC reading (offset)
    

    pathIn (str): input path (tif)
    nbTile (int):  [x,y] tile repeat number, always flat array (default:1)=> [x,y](x1) 
    out:
        matOffset (array): [x (width), y (height)] offsets in pixels
    '''
    if rpcIn:
        objRpc=GeomFunc.RPCin(rpcIn)
        matOffset=np.array([objRpc.sampOffset-objRpc.sampScale, objRpc.lineOffset-objRpc.lineScale], dtype=int)
        
    else:
        SubLogger('CRITICAL', 'Error in recorded offset, RPC method is the only faithfull')
        # sizeImg=[height, width]
        imgIn=cv.imread(pathIn, cv.IMREAD_UNCHANGED)
        sizeImg=imgIn.shape[:2]
        del imgIn
        
        if sizeImg[0] in (2134, 2118, 2140, 2124, 2108):
            matOffset=np.array([0, -8])
        elif sizeImg[0] in (2126, 2136):
            matOffset=np.array([0, -22])
        elif sizeImg[0] in (2132,):
            matOffset=np.array([0, -10])
        elif sizeImg[0] in (2142, 2112):
            matOffset=np.array([0, -17])
        else:
            SubLogger('CRITICAL', 'Unknown scene size (%i %i): %s'% (sizeImg[0], sizeImg[1], os.path.basename(pathIn)))
    
    return np.tile(matOffset, nbTile)

def ExtractDisto(sceneId, modType, rpcPath=None):
    '''
    Read distortion model from planet_common config file

    sceneId (str): scene ID (dddddddd_hhhhhh_iii)
    modType ('photometrix'|'tsai'): distortion type (add/remove, normalisation)
    rpcPath (str): RPC scene path used for origin offset in cu/cv (Tsai model)
    out:
        lstDisto (tuple): parameter tuple
    '''
    hardwId=sceneId.split('_')[-1]
    lstUnknownId=('1002', '1024', '0f2d', '0e16', '0f12')
    if CheckPC():
        from planet_common.maths import camera
        from planet_common.utils._frozendict import frozendict
        from planet_common.calibration.optical_distortion.configs import psblue, ps2
        from planet_common.calibration.optical_distortion.configs import (FORMAT_OPENCV, CHROMA_MONO)

        if hardwId in ps2.PER_SAT_CONFIG:
            telescope='PS2'
            dicConfig=ps2.PER_SAT_CONFIG[hardwId]
            lstPP=(ps2.CAMERA_CENTER_X, ps2.CAMERA_CENTER_Y)
            lstSize=(camera.PS2_CAMERA.width, camera.PS2_CAMERA.height)
            
        elif hardwId in psblue.PER_SAT_CONFIG:
            telescope='PSBlue'
            dicConfig=ps2.PER_SAT_CONFIG[hardwId]
            lstPP=(ps2.CAMERA_CENTER_X, ps2.CAMERA_CENTER_Y)
            lstSize=(camera.PS2_CAMERA.width, camera.PS2_CAMERA.height)

        elif hardwId in lstUnknownId:
            telescope='PS2'
            dicConfig=dict(ps2.DEFAULT_CONFIG)
            for key in dicConfig:
                if not type(dicConfig[key])==frozendict: continue
                dicConfig[key]=dict(dicConfig[key])
            lstPP=(ps2.CAMERA_CENTER_X, ps2.CAMERA_CENTER_Y)
            lstSize=(camera.PS2_CAMERA.width, camera.PS2_CAMERA.height)
            dicConfig['center']['x']+=lstUnknownId.index(hardwId)
            dicConfig['center']['y']+=lstUnknownId.index(hardwId)
            
        else:
            SubLogger('CRITICAL', 'config info not found for satellite id, check and add exception: %s'% hardwId)
        

    else:
        # From Dove-C 1003
        dicConfig={ 'format': '',
                    'chroma': '',
                    'add': {'k1': -3.94502713e-10, 'k2': 0.0},
                    'rem': {'k1': 4.00255009e-10, 'k2': 0.0},
                    'center': {'x': 3300.0 - (0), 'y': 2200.0 - (0)}
                    }
        lstPP=(3300.0, 2200.0)
        lstSize=(6600.0, 4400.0)
    
    # Photometrix, remove distortion in [mm]
    if modType=='photometrix': 
        return (    ('distoType', 'Photometrix'), 
                    ('xp', (dicConfig['center']['x']-lstPP[0])*camPitch), #(lstSize[0]-dicConfig['center']['x'])*camPitch
                    ('yp', (dicConfig['center']['y']-lstPP[1])*camPitch), #(lstSize[1]-dicConfig['center']['y'])*camPitch
                    ('k1', dicConfig['add']['k1']/camPitch**2),
                    ('k2', dicConfig['add']['k2']/camPitch**4),
                    ('k3', 0.0),
                    ('p1', 0.0),
                    ('p2', 0.0),
                    ('b1', 0.0),
                    ('b2', 0.0),
                )
    # Tsai model, add distortion in normalised coords [pxl/c]
    elif modType=='tsai':
        # Include origin offset (cropped L1A)
        if rpcPath:
            objRpc=GeomFunc.RPCin(rpcPath)
            matOffset=np.array([objRpc.sampOffset-objRpc.sampScale, objRpc.lineOffset-objRpc.lineScale], dtype=int)
            del objRpc
        elif scenePath:
            matOffset=ExtractFrameOffset(scenePath)
        else:
            matOffset=np.zeros(2)

        return (    ('distoType', 'TSAI'), 
                    ('k1', dicConfig['rem']['k1']*camFocal**2/camPitch**2),
                    ('k2', dicConfig['rem']['k2']*camFocal**4/camPitch**4), #dicConfig['rem']['k2']*camFocal**4/camPitch**4
                    ('p1', 0.0),
                    ('p2', 0.0),
                    ('cu', (dicConfig['center']['x']+matOffset[0])*camPitch),
                    ('cv', (dicConfig['center']['y']+matOffset[1])*camPitch),
                )
    # no ASP model, add distortion in [pxl]
    elif modType=='pixel_addD':
        return {    'k1': dicConfig['rem']['k1'],
                    'k2': dicConfig['rem']['k2'],
                    'p1': 0.0,
                    'p2': 0.0,
                    'xp': dicConfig['center']['x']-lstPP[0],
                    'yp': dicConfig['center']['y']-lstPP[1],
                }
    elif modType=='pixel_remD':
        # no ASP model, remove distortion in [pxl]
        return {    'k1': dicConfig['add']['k1'],
                    'k2': dicConfig['add']['k2'],
                    'p1': 0.0,
                    'p2': 0.0,
                    'xp': dicConfig['center']['x']-lstPP[0],
                    'yp': dicConfig['center']['y']-lstPP[1],
                }
    else:
        SubLogger('CRITICAL', 'Unknown distortion model type (\'photometrix\'|\'tsai\'): %s'% modType)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
