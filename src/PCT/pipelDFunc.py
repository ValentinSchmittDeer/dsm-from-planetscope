#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json

from OutLib.LoggerFunc import *
from VarCur import *
from PCT.dataFunc import CheckPC

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['ExtractDisto']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def ExtractDisto(hardwId, modType):
    '''
    Read distortion model from planet_common config file

    hardwId (str): satellite ID (last number of scene ID)
    modType ('photometrix'|'tsai'): distortion type (add/remove, normalisation)
    out:
        lstDisto (tuple): parameter tuple
    '''
    if CheckPC():
        from planet_common.maths import camera
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

        elif hardwId in ('1002', ):
            telescope='PS2'
            dicConfig=ps2.DEFAULT_CONFIG
            lstPP=(ps2.CAMERA_CENTER_X, ps2.CAMERA_CENTER_Y)
            lstSize=(camera.PS2_CAMERA.width, camera.PS2_CAMERA.height)
            
        else:
            SubLogger('CRITICAL', 'config info not found for satellite id, check and add exception: %s'% hardwId)
        

    else:
        # From Dove-C 1003
        dicConfig={ 'format': '',
                    'chroma': '',
                    'add': {'k1': -3.94502713e-10, 'k2': 0.0},
                    'rem': {'k1': 4.00255009e-10, 'k2': 0.0},
                    'center': {'x': 3300.0 - (-29.87738), 'y': 2200.0 - (11.29096)}
                    }
        lstPP=(3300.0, 2200.0)
        lstSize=(6600.0, 4400.0)

    # objCamInter=Photometrix, objCamOut=Tsai
    if modType=='photometrix':
        # Photometrix, remove distortion in [mm]
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
    elif modType=='tsai':
        # Tsai model, add distortion in normalised coords [pxl/c]
        return (    ('distoType', 'TSAI'), 
                    ('k1', dicConfig['rem']['k1']*camFocal**2/camPitch**2),
                    ('k2', dicConfig['rem']['k2']*camFocal**4/camPitch**4), #dicConfig['rem']['k2']*camFocal**4/camPitch**4
                    ('p1', 0.0),
                    ('p2', 0.0),
                    ('cu', dicConfig['center']['x']*camPitch),
                    ('cv', dicConfig['center']['y']*camPitch),
                )
    elif modType=='pixel_addD':
        # no ASP model, add distortion in [pxl]
        return {    'k1': dicConfig['rem']['k1'],
                    'k2': dicConfig['rem']['k2'],
                    'p1': 0.0,
                    'p2': 0.0,
                }
    elif modType=='pixel_remD':
        # no ASP model, remove distortion in [pxl]
        return {    'k1': dicConfig['add']['k1'],
                    'k2': dicConfig['add']['k2'],
                    'p1': 0.0,
                    'p2': 0.0,
                }
    else:
        SubLogger('CRITICAL', 'Unknown distortion model type (\'photometrix\'|\'tsai\'): %s'% modType)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
