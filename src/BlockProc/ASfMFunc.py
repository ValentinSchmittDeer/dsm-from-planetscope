#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, time
import json, csv
import logging
from glob import glob
from math import sin, cos, asin, acos, pi, ceil
import numpy as np
from numpy.linalg import norm, inv, lstsq, det, svd, matrix_rank
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import rasterio

from pprint import pprint
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D

from importlib.util import find_spec
checkPlanetCommon=find_spec('planet_opencv3') is not None
if checkPlanetCommon:
    from planet_opencv3 import cv2 as cv
else:
    import cv2 as cv


from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc import GeomFunc

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =[]
SetupLogger(name=__name__)
#SubLogger('ERROR', 'jojo')

gdInfo='gdalinfo'
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def SingleBandImg(pathIn, pathOut, imgType='green'):
    '''
    Convert image to a single band image for further process.
    The single band is extracted accroting to the type argument.
    The RPC metadata is also removed to force provided one.

    pathIn (str): input path
    pathOut (str): output path
    imgType ('green'|'hls'): extraction mode (default: green)
    out:
        process output
    '''
    if not imgType in ('green','hls'): SubLogger('CRITICAL', 'Unknown imgType')
    if imgType=='green':
        cmd='gdal_translate -b 2 -of GTiff -co PROFILE=BASELINE -q %s %s'% (pathIn, pathOut)
        cmd+=' ; rm %s/*.RPB'% os.path.dirname(pathOut)
        return os.system(cmd)
    else:
        SubLogger('CRITICAL', '"hls" imgType is not ready')

def SubArgs_Ortho(pathImgIn, pathRpcIn, pathDemIn, pathOrthoOut, epsg=4326):
    '''
    Create a list of mapproject parameters
    
    pathImgIn (str): input image
    pathRpcIn (str): input RPC
    pathDemIn (str): input DEM
    pathOrthoOut (str): Output ortho
    epsg (int): epsg code of the projected ortho (default: 4326)
    out:
        subArgs (list): argument list
    '''
    # Output folder
    dirOut=os.path.dirname(pathOrthoOut)
    if not os.path.exists(dirOut): os.mkdir(dirOut)

    # Copy model
    pathRpcTemp=pathImgIn[:-4]+'_RPC.TXT'
    os.system('cp %s %s'% (pathRpcIn, pathRpcTemp))

    # Arguments
    subArgs=[pathDemIn,
            pathImgIn,
            #pathRpcTemp,
            pathOrthoOut,
            '--t_srs', 'EPSG:'+str(epsg), 
            '-t', 'rpc',
            '--tr', str(gsdOrth),
            '--ot', 'UInt16',
            ]

    subArgs+=['; rm', pathRpcTemp] # remove RPC file after

    return subArgs

def SubArgs_StereoKP_RPC(pathObj, lstSceneID, softness=0):
    '''
    Create a list of stereo_pprc parameters for key point extraction per pair

    pathObj (obj): PathCur class from VarCur
    lstSceneID (list): list of scene ID
    softness (int [0-2]): interger designing feature filtering parameter set hardness, 0:hard 2:soft (release freedom)
    out:
        subArgs (list): argument list
    '''
    # Feature matching hardness
    # (ip-per-tile, ip-uniqueness-threshold, epipolar-threshold, disable-tri-ip-filter)
    lstHard=(('1000', '0.3', '2', '0'), # Hard
             ('1000', '0.4', '5', '0'), 
             ('1000', '0.3', '5', '1'), # Soft
             )
    
    if not -1<softness<len(lstHard): SubLogger('CRITICAL', 'Feature extraction and matching hardness out of range, not enough features (key points)')

    dirOut=os.path.dirname(pathObj.prefStereoKP)
    if os.path.exists(dirOut): os.system('rm -r %s'% dirOut)
    
    subArgs=[]

    for idCur in sorted(lstSceneID):
        pathImg=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idCur))
        if not os.path.exists(pathImg): SubLogger('CRITICAL', 'Image not found: %s'% idCur)
        subArgs.append(pathImg)
        pathRpcIn=os.path.join(pathObj.pData, pathObj.extRpc.format(idCur))
        if not os.path.exists(pathRpcIn): SubLogger('CRITICAL', 'Rpc not found: %s'% idCur)
        pathRpcTemp=os.path.join(pathObj.pProcData, pathObj.extRpc1B.format(idCur))
        cmd='cp %s %s'% (pathRpcIn, pathRpcTemp)
        os.system(cmd)

    subArgs.append(pathObj.prefStereoKP)

    # Arguments
    subArgs+=[## Basics
                '-t', 'rpc', # set stereo session pinhole OR nadirpinhole
                '--datum', 'WGS_1984', # set datum
                '--nodata-value', '0', # nodata, do not process <= x
                '--skip-rough-homography', # Skip datum-based rough homography
                '--skip-image-normalization', # 
                #'--ip-debug-images', '1', # Print image with key points on: written at process root (in docker)
                ## Feature extraction
                '--alignment-method', 'affineepipolar', # transformation method affineepipolar|homography|epipolar|none: see "Preparation" in mss_main
                '--ip-detect-method','1', # algo (0=OBA-loG, 1=SIFT, 2=ORB)
                '--ip-per-tile', lstHard[softness][0], # key point number per sub frame
                #'--individually-normalize', # normalisation param per image not global
                ## Feature matching
                #'--ip-inlier-factor', '1e-4', # key point creation filtering (x>1/15 -> more points but worse)
                '--ip-uniqueness-threshold', lstHard[softness][1], # key point creation filtering (x>0.7 -> more points but less unique)
                '--epipolar-threshold', lstHard[softness][2], # key point matching, Max distance to the epipolar line in camera unit
                ## Feature filtering
                '--ip-num-ransac-iterations', '1000', # number of RANSAC iteration
                '--disable-tri-ip-filter', lstHard[softness][3], # disable the triangulation filtering
                #'--ip-triangulation-max-error', '1000', # filter out key point based on triangulation
                #'--stddev-mask-thresh', '0.01', # mask (filter) key point whether the local standard deviation is less
                #'--stddev-mask-kernel', '51', # size of the local standard deviation computation
                ##
                #'--num-matches-from-disparity', '100', # create key point grid after disparity computation (needs full stereo process)
                '--num-matches-from-disp-triplets', '1000', # same linking multiview points
                #'--min-triangulation-angle', '0.01'
                '--filter-mode', '0', # Avoid filtering: spare time
                ]

    subArgs+=['; rm', pathRpcTemp] # remove RPC file after

    return subArgs

def SubArgs_Adj2Rpc(pathImgIn, pathRpcIn, pathDemIn, pathRpcOut, prefBA=None):
    '''
    Create a list of cam2rpc parameters
    
    pathImgIn (str): input image
    pathRpcIn (str): input RPC
    pathDemIn (str): input DEM
    pathRpcOut (str): output RPC
    prefBA (str): BA prefix to pick up adjust file (defaut: None)
    out:
        subArgs (list): argument list
    '''
    # Copy model
    pathRpcTemp=pathImgIn[:-4]+'_RPC.TXT'
    os.system('cp %s %s'% (pathRpcIn, pathRpcTemp))

    # Arguments
    subArgs=[pathImgIn,
            #pathRpcTemp,
            pathRpcOut,
            '-t', 'rpc',
            '--dem-file', pathDemIn, 
            '--no-crop',
            ]

    if prefBA: subArgs+=['--bundle-adjust-prefix', prefBA]
    
    subArgs+=['; rm', pathRpcTemp] # remove RPC file after
    
    return subArgs

def SubArgs_Camgen(pathImgIn, pathRpcIn, pathDemIn, pathCamOut, pattern='circle'):
    '''
    Create a list of cam_gen parameters

    pathImgIn (str): input image
    pathRpcIn (str): input RPC
    pathDemIn (str): input DEM
    pathCamOut (str): output camera file
    pattern (circle|grid): point pattern (default: circle)
    out:
        subArgs (list): argument list
    '''
    ptSpace=100
    ptRadiusFact=15
    if not pattern in ('circle', 'grid'): SubLogger('CRITICAL', 'grid argument must be circle|grid')
    
    pathGcp=pathCamOut.split('.')[0]+'.gcp'

    # Copy model
    pathRpcTemp=pathImgIn[:-4]+'_RPC.TXT'
    os.system('cp %s %s'% (pathRpcIn, pathRpcTemp))

    # Point distribution
    txtGdal=os.popen('%s %s'% (gdInfo,pathImgIn)).readlines()
    strSize=[lineCur.strip('\nSize is').split(',') for lineCur in txtGdal if lineCur.startswith('Size')][0]
    imgShape=(int(strSize[1]), int(strSize[0]))

    if imgShape[0]==2134:
        heightPxlPts=(-8, 4392+1)
    elif imgShape[0]==2126:
        heightPxlPts=(-22, 4378+1)
    else:
        SubLogger('CRITICAL', 'Unknown scene height (%i): %s'% (imgShape[0], os.path.basename(pathImgIn)))
    
    # Circle grid
    if pattern=='circle':
        x0,y0=[int(i/camPitch) for i in camCentre]
        lstPxlPts=[(x0,y0),]
        for rCur in range(ptSpace,ptRadiusFact*ptSpace+1, ptSpace):
            lstPxlPts.append((x0+rCur, y0))
            dAlpha=2*asin(ptSpace/2/rCur)
            lstPxlPts+=[(x0+int(rCur*cos(alpha)), y0+int(rCur*sin(alpha))) for alpha in np.arange(dAlpha, 2*pi, dAlpha)]
    # Grid  
    else:
        lstPxlPts=[(wi, hei) for wi in range(0, 6600+1, ptSpace) for hei in range(heightPxlPts[0],heightPxlPts[1]+1,ptSpace)]
    
    strPxlPts=','.join(['%i %i'% (i,j) for i,j in lstPxlPts])
    
    # Arguments
    subArgs=[pathImgIn,
            '--input-camera',pathRpcIn,
            '-t', 'rpc',
            '--camera-type', 'pinhole',
            '--reference-dem', pathDemIn,
            '--optical-center', ' '.join([str(k) for k in camCentre]),
            '--focal-length', str(camFocal),
            '--pixel-pitch', str(camPitch),
            '--pixel-values', '{!r}'.format(strPxlPts), 
            '-o', pathCamOut,
            '--refine-camera',
            '--gcp-file', pathGcp,
            ]

    subArgs+=['; rm', pathRpcTemp] # remove RPC file after
    
    return subArgs

def StereoDescriptor(pathObj, lstPairs):
    '''
    Create a txt file with stereo pair per lines. It is used by bundle_adjust

    pathObj (obj): PathCur class from VarCur
    featCur (json): current couple desciptor
    out:
        0 : pathObj.pStereoLst file created
    '''
    # Availability
    grepImg=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format('*'))
    lstImgAvai=[os.path.basename(pathCur) for pathCur in glob(grepImg)]
    lstImgAvai.sort()
    
    lstOut=[]
    nbComb=len(lstPairs)
    for i in range(nbComb):
        comb=lstPairs[i]
        if not comb['properties']['nbScene']==2: continue

        lstSceneCur=[pathObj.extFeat1B.format(scenId) for scenId in comb['properties']['scenes'].split(';')]
        if not all([sceneName in lstImgAvai for sceneName in lstSceneCur]): continue
        
        lstScenePath=[os.path.join(pathObj.pProcData,sceneName) for sceneName in lstSceneCur]
        lstOut.append(' '.join(lstScenePath)+'\n')
    
    if not lstOut: SubLogger('CRITICAL', 'stereo list is empty, no scene is available')
    with open(pathObj.pStereoLst, 'w') as fileOut:
                    fileOut.writelines(lstOut)
    return 0

def AjustPM(sceneId, pathRpcIn, pathCamIn, pathCamOut, outGraph=False):
    '''
    Adjust physical model using distortion model (e.g. Rough to Initial).

    ##
    Compute a distortion model from gcp files (Grid & Rough). The Rough file
    was used during the RPC 2 PM transformation (should be a circle) and 
    the Grid file provides ground coordinates used to fit the distortion model. 
        _h stands for homogeneous coordinates
        _n stands for normalized [mm]

    pathObj (obj): PathCur clas from VarCur
    featCur (json): current feature desciptor
    distModel ('photometrix'|'tsai'|'drpc'): choose distortion model (default: photometrix)
    outGraph (bool): Plot a distortion graph in image space and stop the process (default: False)
    out:
        0 (int): write gcp2disto file (process log) and new camera file
    '''
    print()
    if not type(outGraph)==bool: SubLogger('CRITICAL', 'outGraph must be a boolean')

    # Input gcp
    pathGcp=pathCamOut.split('.')[0]+'.gcp'
    if not os.path.exists(pathGcp): SubLogger('CRITICAL', 'Gcp file not found, %s'% pathGcp)
    with open(pathGcp) as fileIn:
        lstIn=[l.strip().split() for l in fileIn.readlines()]
    matPtsGeo=np.array([(float(l[2]), float(l[1]), float(l[3])) for l in lstIn])
    matPtsCart=GeomFunc.Geo2Cart_Elli(matPtsGeo)
    nbPts=matPtsGeo.shape[0]

    # Create objects
    objRpcIn=GeomFunc.RPCin(pathRpcIn)
    objCamIn=GeomFunc.TSAIin(pathCamIn)
    
    matPtsImg=objRpcIn.Obj2Img(matPtsGeo)
    objCamOut=GeomFunc.TSAIin(pathCamIn)

    # Extract distortion model
    if 0:
        if not checkPlanetCommon: SubLogger('CRITICAL', 'must run in planet_common env')
        from planet_common.maths import camera
        from planet_common.calibration.optical_distortion.configs import psblue, ps2
        hardwId=sceneId.split('_')[-1]

        if hardwId in ps2.PER_SAT_CONFIG:
            dicConfig=dict(ps2.PER_SAT_CONFIG[hardwId].copy())
            dicConfig['telescope']='PS2'
            dicConfig['distoCentre']=dicConfig['center']
            dicConfig['frameCentre']={'x': ps2.CAMERA_CENTER_X, 'y': ps2.CAMERA_CENTER_Y}
            dicConfig['frameSize']={'x': camera.PS2_CAMERA.width, 'y': camera.PS2_CAMERA.height}

        elif hardwId in psblue.PER_SAT_CONFIG:
            dicConfig=dict(ps2.PER_SAT_CONFIG[hardwId].copy())
            dicConfig['telescope']='PSBlue'
            dicConfig['distoCentre']=dicConfig['center'].copy()
            dicConfig['frameCentre']={'x': psblue.CAMERA_CENTER_X,'y': psblue.CAMERA_CENTER_Y}
            dicConfig['frameSize']={'x': camera.IMPERX47MP_CAMERA.width,'y': camera.IMPERX47MP_CAMERA.height}

        else:
            SubLogger('CRITICAL', 'config info not found for hardware id: %s'% hardwId)
        del dicConfig['center']

    else:
        dicConfig={'rem': {'k1': 4.00255009e-10, 'k2': 0.0}, 
                   'distoCentre': {'x': 3329.87738, 'y': 2188.70904}, 
                   'add': {'k1': -3.94502713e-10, 'k2': 0.0}, 
                   'frameSize': {'x': 6600, 'y': 4400}, 
                   'telescope': 'PS2', 
                   'chroma': 'mono', 
                   'frameCentre': {'x': 3300.0, 'y': 2200.0}, 
                   'format': 'opencv'}
    
    # Update distortion file
    distKind=1 # 0=Photometrix, 1=Tsai
    tupUpdate=( (   ('distoType', 'Photometrix'), # Photometrix, remove distortion in mm
                    ('xp', (dicConfig['frameCentre']['x']-dicConfig['distoCentre']['x'])*objCamOut.pitch),
                    ('yp', (dicConfig['frameCentre']['y']-dicConfig['distoCentre']['y'])*objCamOut.pitch),
                    ('k1', dicConfig['add']['k1']/objCamOut.pitch**2),
                    ('k2', dicConfig['add']['k2']/objCamOut.pitch**4),
                    ('k3', 0.0),
                    ('p1', 0.0),
                    ('p2', 0.0),
                    ('b1', 0.0),
                    ('b2', 0.0),
                ),
                (   ('distoType', 'TSAI'), # Tsai model, add distortion in normalised coords
                    ('k1', dicConfig['rem']['k1']*objCamOut.fu**2/objCamOut.pitch**2),
                    ('k2', dicConfig['rem']['k2']*objCamOut.fu**4/objCamOut.pitch**4),
                    ('p1', 0.0),
                    ('p2', 0.0),
                )
            )[distKind]

    for keyNew, valNew in tupUpdate:
        setattr(objCamOut, keyNew, valNew)
    objCamOut.Update()

    with open(pathCamOut, 'w') as fileOut:
        fileOut.writelines(objCamOut.__write__())

    return 0

    # Update extrinsic
    # matPtsImg, objCamOut, matPtsCart
    pt0=np.append(matPtsCart, np.ones([nbPts, 1]), axis=1)
    print('pt0\n', pt0[:5])
    matO=np.append(objCamOut.matO, [[0, 0, 0, 1]], axis=0)
    #matO=objCamOut.matO
    #print('matO\n', matO)
    pt1=(matO@pt0.T).T
    print('pt1\n', pt1[:5])
    matK=np.append(objCamOut.matK, [[0], [0], [0]], axis=1)
    #matK=objCamOut.matK
    #print('matK\n', matK)
    pt2_h=(matK@pt1.T).T
    pt2=pt2_h[:,:2]/pt2_h[:,[2]]
    print('pt2\n', pt2[:5])
    pt3=objCamOut.ApplyDisto('add', pt2)
    print('pt3\n', pt3[:5])
    print('ptImg\n', matPtsImg[:5])
    ###### Caution pt3=matPtsImg
    ptImg_n=pt3-objCamOut.vectPP/objCamOut.pitch
    rad_n=norm(ptImg_n, axis=1)[:,np.newaxis]
    pt12=pt3+ptImg_n*(dicConfig['add']['k1']*rad_n**2+dicConfig['add']['k2']*rad_n**4) # in pixel
    print('pt12\n', pt12[:5])
    matKinv=matK.T@inv(matK@matK.T)
    #print('matK inv\n', matKinv)
    pt11=(matKinv@np.append(pt12, np.ones([nbPts, 1]), axis=1).T).T
    print('pt11\n', pt11[:5])
    pt10=(inv(matO)@pt11.T).T
    print('pt10\n', pt10[:5])
    for i in range(5):
        ptInf=pt10[i,:3]
        matSkew=np.array([[0, -ptInf[2], ptInf[1]], [ptInf[2], 0, -ptInf[0]], [-ptInf[1], ptInf[0], 0]])
        vect=matSkew@objCamOut.vectX0
        pt3D=pt0[i,:3]
        print('Cross prod', np.sum((-vect*pt3D)[:2])/vect[2])
        print('Pt inf', np.sum((-pt10[i,:]*pt0[i,:])[[0,1,3]])/pt0[i,2])
        print(pt3D[2])
    

    sys.exit()
    with open(pathCamOut, 'w') as fileOut:
        fileOut.writelines(objCamOut.__write__())

    return 0


class SubArgs_BunAdj:
    '''
    Bundle_adjust parameters object

    pathObj (obj): PathCur class from VarCur
    lstPairs (list): list of image ID
    out:
        SubArgs_BunAdj (obj):
            KeyPoints (funct):
    '''
    argsInit=[  ## Basics
                '--datum', 'WGS_1984', # set datum
                '--nodata-value', '0', # nodata, do not process <= x
                '--threads', '1', # make deterministic bundle adjustment 
                #'--input-adjustments-prefix', path # initial camera transform
                # : read "adjust" files with that prefix
                # Caution cannot be coupled with --inline-adj (so no distortion)
                
                ## Key points
                '--min-matches', '10', # min key point pairs
                
                ## Model: 'Any weight set in the model must balance another one (never a single weight)'
                '--disable-pinhole-gcp-init', # do initialise camera from GCP files

                ## Intrinsic imporvement
                
                ## Least square
                '--num-passes', '1', # iteration number
                
                ## Storage
                '--report-level', '20',
                '--save-cnet-as-csv', # Save key points in gcp point format
                ]

    def __init__(self, pathObj, lstId, mode):
        # Mode
        if mode=='rpc':
            self.argsInit+=['-t', 'rpc', # set stereo session pinhole OR nadirpinhole
                            ]
        if mode=='pm':
            self.argsInit+=['-t', 'nadirpinhole', # set stereo session pinhole OR nadirpinhole
                            '--inline-adjustments', # Store result in .tsai, not in adjsut
                            ]
        self.pathDem=pathObj.pDem

        # Stereo list
        self.argsInit+=['--overlap-list', pathObj.pStereoLst,] # stereopair file for key point extraction
            #OR
        #self.argsInit+=['--position-filter-dist', 'XXm',] # image couple for key point based on centre distance
        
        # Scenes
        if not type(lstId)==list : SubLogger('CRITICAL', 'Image list (lstId) must be a list of image id')
        lstId.sort()
        lstImgPath=[os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idCur)) 
                        for idCur in lstId]
        if not all([os.path.exists(pathCur) for pathCur in lstImgPath]): SubLogger('CRITICAL', 'Image(s) not found' )
        self.nbScene=len(lstImgPath)
        self.argsInit+=lstImgPath

        # RPC
        lstRPCPath=[os.path.join(pathObj.pData, pathObj.extRpc.format(idCur)) 
                            for idCur in lstId]
        if not all([os.path.exists(pathCur) for pathCur in lstRPCPath]): SubLogger('CRITICAL', 'RPC(s) not found' )
        lstRPCUse=[os.path.join(pathObj.pProcData, pathObj.extRpc1B.format(idCur)) 
                            for idCur in lstId]
        self.zipRPC=tuple(zip(lstRPCPath, lstRPCUse))

        # Cameras
        self.lstTsaiName=[pathObj.nTsai[1].format(pathObj.extFeat1B.format(idCur).split('.')[0]) 
                                for idCur in lstId]       

    def KP_RPC(self, prefIn, prefOut):
        '''
        Feature extraction merging bundle adjustment. It compute a fixed bundle adjustment
        using the existing .match file and returns the initial coordinates.
        '''
        strInd=' '.join([str(i) for i in range(self.nbScene)])

        # RPC copy
        #if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        [os.system('cp %s %s'% couple) for couple in self.zipRPC]

        args=self.argsInit.copy()
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                '--camera-weight', '1', # EO weight (x>1 -> stiffer)
                '--fixed-camera-indices', "'%s'"% strInd, # fixed camera i
                ## Least square
                '--max-iterations', '1', # in non-linear least square (per pass)
                ]

        # Clear RPC
        args+=['; rm']+[fPocData for fData,fPocData in self.zipRPC]

        return args

    def Adjust_RPC(self, prefIn, prefOut):
        '''
        Adjust RPC and return .adjust file
        '''
        # RPC copy
        #if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        [os.system('cp %s %s'% couple) for couple in self.zipRPC]

        args=self.argsInit.copy()
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                '--camera-weight', '0.1', # EO weight (x>1 -> stiffer)
                ## Least square
                '--max-iterations', '200', # in non-linear least square (per pass)
                ]

        # Clear RPC
        args+=['; rm']+[fPocData for fData,fPocData in self.zipRPC]

        return args

    def ImageAdjust_RPC(self, prefIn, prefOut, pathObj, outGraph=False):
        '''
        !!! In development !!!
        Compute polynomial transformation in image plane to adjust 
        relative positions (RPC-BA). It does not return arguments. 
        It stores resulting coefficients into an .adjsutImg file (ASCII).
        if not .adjust files exists (RPC-BA with ASP), there is no ground 
        transfomation.

        prefIn (str): 
        prefOut (str):
        pathObj (obj):
        outGraph (bool):
        out:
            ???
        '''
        # List of stereo pair
        lstArgPath=[a for a in self.argsInit if a.startswith('/')]
        with open(lstArgPath[0]) as fileIn:
            lstStereoPath=[lineCur.strip().split() for lineCur in fileIn.readlines()]

        # dict of RPC
        dicRpc={}
        extImg=pathObj.extFeat1B.replace('{}', '')
        for pathTif in lstArgPath[1:]:
            sceneId=os.path.basename(pathTif).replace(extImg, '')
            
            # Initial RPC
            pathRPCIn=os.path.join(pathObj.pData, pathObj.extRpc.format(sceneId))
            if not os.path.exists(pathRPCIn): SubLogger('CRITICAL', 'RPC file not found: %s'% sceneId)
            objRpcInit=GeomFunc.RPCin(pathRPCIn)
            #objRPC.Comput_InvRPC()

            # ASP RPC
            pathRPCIn=prefIn+'-'+pathObj.extRpc1Bx.format(sceneId)
            if not os.path.exists(pathRPCIn): SubLogger('CRITICAL', 'RPC file not found: %s'% sceneId)
            objRpcAsp=GeomFunc.RPCin(pathRPCIn)
            #objRPC.Comput_InvRPC()
            
            dicRpc[sceneId]=(objRpcInit, objRpcAsp)
        lstId=sorted(list(dicRpc.keys()))

        # Read key points ground coords
        pathKP=prefIn+'-final_residuals_no_loss_function_pointmap_point_log.csv'
        if not os.path.exists(pathKP): SubLogger('CRITICAL', 'Key point file not found: %s'% pathKP)
        with open(pathKP) as fileIn:
            lstKP=[[float(wordCur.strip()) for wordCur in lineCur.strip().split(',')[:3]] for lineCur in fileIn.readlines() if not lineCur.startswith('#')]

        matGrdKP=np.array(lstKP)
        lstIdGrdKP=[]
        
        # Read key points image coords
        pathKP=prefIn+'-cnet.csv'
        if not os.path.exists(pathKP): SubLogger('CRITICAL', 'Feature file not found: %s'% pathKP)
        
        lstKP=[]
        with open(pathKP) as fileIn:
            for i, lineCur in enumerate(fileIn):
                wordCur=lineCur.strip().split()
                ptsGeoOld=np.array([[float(wordCur[2]), float(wordCur[1]), float(wordCur[3])]])
                ptsGeo=matGrdKP[[i],:]

                if norm(ptsGeoOld-ptsGeo)>1: SubLogger('CRITICAL', 'Feature correspondances issue')
                # Id1'+'Id2'+'...
                lstIdGrdKP.append('')
                # Id1, x1, y1, x1', y1', Id2, x2, y2, x2', y2'
                lineKP=[]
                for i in range(7, len(wordCur), 5):
                    sceneId=os.path.basename(wordCur[i]).replace(extImg, '')

                    ptsImg=np.array([[float(wordCur[i+1]), float(wordCur[i+2]) ]])
                    ptsImgProj=dicRpc[sceneId][1].Obj2Img(ptsGeo)

                    # Id, x1, y1, x1', y1'
                    lineKP+=[sceneId]+list(ptsImg[0])+list(ptsImgProj[0])
                    lstIdGrdKP[-1]+=sceneId+'+'
                
                lstKP.append(lineKP)
                lstIdGrdKP[-1]=lstIdGrdKP[-1].strip('+')

        # Graph management
        if outGraph:
            import matplotlib.colors as mcolors
            lstColours=list(mcolors.BASE_COLORS.values())[:-1]
            lstColours+=list(mcolors.TABLEAU_COLORS.values())
            lstColours+=[mcolors.CSS4_COLORS[nC]  for nC in ('tomato', 'coral', 'peru', 'darkorange', 'gold', 'olive', 'springgreen', 'teal', 'dodgerblue', 'royalblue', 'indigo', 'fuchsia')]

        # Adjustment per image
        for idCur in lstId:            
            matPt=np.array([tup[j+1:j+5] for tup in lstKP  for j in range(0, len(tup), 5) if tup[j]==idCur])
            matAffi=GeomFunc.AffineTransfo(matPt[:,2:], matPt[:,:2])
            matPtAffi=(np.append(matPt[:,2:], np.ones([matPt.shape[0], 1]), axis=1)@matAffi.T)[:,:-1]

            objRpcNew=GeomFunc.RPCin.InputNorm(GeomFunc.RPCin(), dicRpc[sceneId][0].Offset(), dicRpc[sceneId][0].Scale())
            
            iPts3D=[i for i in range(len(lstIdGrdKP)) if idCur in lstIdGrdKP[i]]
            matPts3D=matGrdKP[iPts3D,:]
            
            objRpcNew.Comput_RPC(matPts3D, matPtAffi)
            pathRPCOut=prefOut+'-'+pathObj.extRpc1B.format(idCur)
            with open(pathRPCOut, 'w') as fileOut:
                fileOut.writelines(objRpcNew.__write__())
            
            # Graph plot
            if not outGraph: continue
            fig, graph = plt.subplots()
            graph.add_patch(Rectangle([0,0], 6600, -2134, fill=False, color='b'))
            
            print('\n'+idCur+':')
            print(' Mean   (full): %.2f %.2f'% tuple(np.mean(matPt[:,2:]-matPt[:,:2], axis=0)))
            print(' StdDev (full): %.2f %.2f'% tuple(np.std(matPt[:,2:]-matPt[:,:2], axis=0)))
            print(' Mean   (affi): %.2f %.2f'% tuple(np.mean(matPtAffi-matPt[:,:2], axis=0)))
            print(' StdDev (affi): %.2f %.2f'% tuple(np.std(matPtAffi-matPt[:,:2], axis=0)))
            print('-----------')
            
            # Colour per pair
            dicPt=dict(zip(lstId,[False]*len(lstId)))
            # Colour per obs nb
            #dicPt=dict(zip(['2','3','4','5'],[False]*4))
            # Colour per comb
            #dicPt={}
            for tup in lstKP:
                if not idCur in tup: continue
                iCur=tup.index(idCur)
                
                # Colour per pair
                for iName in range(0, len(tup), 5):
                    if tup[iName]==idCur: continue
                    keyCur=tup[iName]
                # Colour per obs nb
                #keyCur=str(len(tup)//5)
                # Colour per comb
                #keyCur='/'.join([tup[iName][13:] for iName in range(0, len(tup), 5) if not iName==iCur])
                    if keyCur in dicPt and dicPt[keyCur]:
                        dicPt[keyCur].append(tup[iCur+1:iCur+5])
                    else:
                        dicPt[keyCur]=[tup[iCur+1:iCur+5], ]

            for i,codeId in enumerate(dicPt):
                if not dicPt[codeId]: continue
                matPt=np.array(dicPt[codeId])
                
                print('with', codeId+':')
                print(' Mean   (init): %.2f %.2f'% tuple(np.mean(matPt[:,2:]-matPt[:,:2], axis=0)))
                print(' StdDev (init): %.2f %.2f'% tuple(np.std(matPt[:,2:]-matPt[:,:2], axis=0)))
                
                matPlot=matPt*np.array([1, -1, 1, -1])
                graph.quiver(matPlot[:,0],
                             matPlot[:,1], 
                             matPlot[:,2]-matPlot[:,0],
                             matPlot[:,3]-matPlot[:,1], 
                             color=lstColours[i], 
                             label=codeId,
                             width=1e-3) 
            
            graph.set_title(idCur)
            graph.set_xlabel('x')
            graph.set_ylabel('y')
            graph.legend()
            graph.axis('equal')
            fig.suptitle('Feature residuals in image plane')
            plt.show()
        
        return 0
        
    def Fixed(self, prefIn, prefOut):
        SubLogger('CRITICAL', 'Not ready')

def KpCsv2Geojson(prefIn):
    '''
    Convert CSV files with key points from ASP to geojson files.

    prefIn (str): bundle adjustment prefix
    out:
        0
    '''
    from copy import deepcopy

    for nameCur in ('-initial_residuals_no_loss_function_pointmap_point_log.csv', '-final_residuals_no_loss_function_pointmap_point_log.csv'):  
        pathIn=prefIn+nameCur
        if not os.path.exists(pathIn): 
            SubLogger('ERROR', '%s file not found'% nameCur)
            continue
        pathOut=pathIn.replace('csv','geojson')
        if os.path.exists(pathOut): continue

        jsonOut=deepcopy(tempGeojson)
        jsonOut['name']=os.path.basename(pathIn).split('_')[0]

        with open(pathIn) as fileIn:
            for i,lineCur in enumerate(fileIn):
                if lineCur.startswith('#'): continue
                wordsCur=lineCur.strip().split(', ')

                dicOut={"type": "Feature", "id": i}
                dicOut["properties"]={'id': i,
                                      'Long': float(wordsCur[0]),
                                      'Lat': float(wordsCur[1]),
                                      'Height': float(wordsCur[2]),
                                      'Res': float(wordsCur[3]),
                                      'NbObs': int(wordsCur[4].replace(' # GCP', '')),
                                      'GCP': wordsCur[-1].endswith('GCP'),
                                      }
                dicOut["geometry"]= {"type": "Point", "coordinates":[float(wordsCur[0]), float(wordsCur[1]), float(wordsCur[2])]}
                jsonOut['Features'].append(dicOut)

        with open(pathOut, 'w') as fileOut:
            fileOut.write(json.dumps(jsonOut, indent=2))
    
    return 0

def CopyPrevBA(prefIn, prefOut, existBool=True, img=True, kp='match'):
    '''
    Copy BA files (stats and matches) from a folder to another.
    It is used to propagate bundle adjsutment.

    prefIn (str): path prefix input
    prefOut (str): path prefix output
    kp ('match'|'clean'|'disp'|'none'): copy key point behaviour (default: match)
    out:
        0|1 (int): created folder | existing folder
    '''
    if not kp in ('match', 'clean', 'disp', 'none'): SubLogger('CRITICAL', 'KP copy mode unknown')
    
    dirOut=os.path.dirname(prefOut)
    if existBool and os.path.exists(dirOut):  
        SubLogger('ERROR', '%s folder already exists'% os.path.basename(prefOut))
        return 1
    elif existBool and not os.path.exists(dirOut):
        os.mkdir(dirOut)

    # Copy tif
    if img:
        for pathCur in glob(prefIn+'*-stats.tif'):
            cmd='cp %s %s'% (pathCur, pathCur.replace(prefIn,prefOut))
            os.system(cmd)
    
    # Copy match
    if kp=='disp' and glob(prefIn+'-disp-*.match'):
        extIn='-disp-*.match'
    elif kp=='clean' and glob(prefIn+'*-clean.match'):
        extIn='*-clean.match'
    elif kp=='match' and glob(prefIn+'*.match'):
        extIn='-????????_*.match'
    elif kp=='none':
        return 0
    else:
        return 1
    
    lstPathIn=glob(prefIn+extIn)
    for pathIn in lstPathIn:
        pathOut=pathIn.replace(prefIn,prefOut).replace('-disp','').replace('-clean','')
        cmd='cp %s %s'% (pathIn, pathOut)
        os.system(cmd)
    
    return 0


##########################################

def SubArgs_ConvertCam(pathObj, featCur):
    '''
    Create a list of convert_pinhole_model parameters

    prefIn (str): last BA prefix
    pathObj (obj): PathCur clas from VarCur
    featCur (json): current feature desciptor
    out:
        subArgs (list): argument list
    '''
    # Initial files
    prefix=''.join([os.path.basename(getattr(pathObj,key)) for key in pathObj.__dict__ if key.startswith('pref')])
    prefix+='-'

    idImg=featCur['id']
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    if not os.path.exists(pathImg1B): SubLogger('CRITICAL', 'Initial image file not found, %s'% pathImg1B)

    pathTsai1=pathObj.nTsai[1].format(pathImg1B.split('.')[0])
    if not os.path.exists(pathTsai1): SubLogger('CRITICAL', 'Initial tsai file not found %s'% idImg)

    # New files
    pathTsai2=pathObj.nTsai[2].format(pathImg1B.split('.')[0])
    if os.path.exists(pathTsai2): return 1
    
    # Arguments
    subArgs=[ pathImg1B,
            pathTsai1,
            '--output-type', 'TsaiLensDistortion', # distortion model
            # <TsaiLensDistortion|BrownConradyDistortion|RPC (default: TsaiLensDistortion)>
            '--sample-spacing', '100', # number of pixel for distortion modeling 
            '-o', pathTsai2,
            ]
    
    return subArgs

def SubArgs_ExportCam(prefIn, pathObj, featCur):
    '''
    Create a list of convert_pinhole_model parameters

    prefIn (str): last BA prefix
    pathObj (obj): PathCur clas from VarCur
    featCur (json): current feature desciptor
    out:
        subArgs (list): argument list
    '''
    # Initial files
    prefix=''.join([os.path.basename(getattr(pathObj,key)) for key in pathObj.__dict__ if key.startswith('pref')])
    prefix+='-'

    idImg=featCur['id']
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    if not os.path.exists(pathImg1B): SubLogger('CRITICAL', 'Initial image file not found, %s'% pathImg1B)

    lstTsai1=glob('{}*{}*{}'.format(prefIn,idImg,'.tsai'))
    if not len(lstTsai1)==1: SubLogger('CRITICAL', 'Initial tsai file not found (or several), %s'% idImg)
    pathTsai1=lstTsai1[0]

    # New files
    nameTsai2=pathObj.nTsai[2].format(pathObj.extFeat1B.format(idImg).split('.')[0])
    pathTsai2=os.path.join(pathObj.pProcData, nameTsai2)
    #if os.path.exists(pathTsai2): return 0
    
    # Arguments
    subArgs=[ pathImg1B,
            pathTsai1,
            '--output-type', camDistExp, # distortion model
            # <TsaiLensDistortion|BrownConradyDistortion|RPC (default: TsaiLensDistortion)>
            '--sample-spacing', '100', # number of pixel for distortion modeling 
            '-o', pathTsai2,
            ]
    
    return subArgs

def SubArgs_StereoKP_PM(pathObj, pairCur, softness=0):
    '''
    Create a list of stereo_pprc parameters for key point extraction per pair

    pathObj (obj): PathCur class from VarCur
    featCur (json): current stereo pair desciptor
    softness (int [0-2]): interger designing feature filtering parameter set hardness, 0:hard 2:soft (release freedom)
    out:
        subArgs (list): argument list
    '''
    # Feature matching hardness
    # (ip-per-tile, ip-uniqueness-threshold, epipolar-threshold, disable-tri-ip-filter)
    lstHard=(('200', '0.2', '3', '1'), # Hard
             ('200', '0.4', '3', '1'), 
             ('1000', '0.4', '3', '0'), # Soft
             )
    
    if not -1<softness<len(lstHard): SubLogger('CRITICAL', 'Feature extraction and matching hardness out of range, not enough features (key points)')

    dirOut=os.path.dirname(pathObj.prefStereoKP)
    if os.path.exists(dirOut): os.system('rm -r %s'% dirOut)
    
    lstPaths=[[],[]]

    for idCur in sorted(pairCur['properties']['scenes'].split(';')):
        pathImg=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idCur))
        if not os.path.exists(pathImg): SubLogger('CRITICAL', 'Image not found: %s'% idCur)
        lstPaths[0].append(pathImg)

        pathTsai= pathObj.nTsai[1].format(pathImg.split('.')[0])
        if not os.path.exists(pathTsai): SubLogger('CRITICAL', 'Tsai not found: %s'% idCur)
        lstPaths[1].append(pathTsai)
    
    subArgs=lstPaths[0]+lstPaths[1]
    subArgs.append(pathObj.prefStereoKP)

    # Arguments
    subArgs+=[## Basics
                '-t', 'nadirpinhole', # set stereo session pinhole OR nadirpinhole
                '--datum', 'WGS_1984', # set datum
                '--nodata-value', '0', # nodata, do not process <= x
                '--skip-rough-homography', # Skip datum-based rough homography
                '--skip-image-normalization', # 
                #'--ip-debug-images', '1', # Print image with key points on: written at process root (in docker)
                ## Feature extraction
                '--alignment-method', 'affineepipolar', # transformation method affineepipolar|homography|epipolar|none: see "Preparation" in mss_main
                '--ip-detect-method','1', # algo (0=OBA-loG, 1=SIFT, 2=ORB)
                '--ip-per-tile', lstHard[softness][0], # key point number per sub frame
                #'--individually-normalize', # normalisation param per image not global
                ## Feature matching
                #'--ip-inlier-factor', '1e-4', # key point creation filtering (x>1/15 -> more points but worse)
                '--ip-uniqueness-threshold', lstHard[softness][1], # key point creation filtering (x>0.7 -> more points but less unique)
                '--epipolar-threshold', lstHard[softness][2], # key point matching, Max distance to the epipolar line in camera unit
                ## Feature filtering
                '--ip-num-ransac-iterations', '1000', # number of RANSAC iteration
                '--disable-tri-ip-filter', lstHard[softness][3], # disable the triangulation filtering
                #'--ip-triangulation-max-error', '1000', # filter out key point based on triangulation
                #'--stddev-mask-thresh', '0.01', # mask (filter) key point whether the local standard deviation is less
                #'--stddev-mask-kernel', '51', # size of the local standard deviation computation
                ##
                #'--num-matches-from-disparity', '100', # create key point grid after disparity computation (needs full stereo process)
                '--num-matches-from-disp-triplets', '1000', # same linking multiview points
                #'--min-triangulation-angle', '0.01'
                '--filter-mode', '0', # Avoid filtering: spare time
                ]


    return subArgs

class SubArgs_BunAdj_old:
    '''
    Bundle_adjust parameters
    '''
    argsInit=[  ## Basics
                '-t', 'nadirpinhole', # set stereo session pinhole OR nadirpinhole
                '--datum', 'WGS_1984', # set datum
                '--nodata-value', '0', # nodata, do not process <= x
                #'--input-adjustments-prefix', path # initial camera transform
                # : read "adjust" files with that prefix
                # Caution cannot be coupled with --inline-adj (so no distortion)
                
                ## Key points
                '--min-matches', '10', # min key point pairs
                
                ## Model: 'Any weight set in the model must balance another one (never a single weight)'
                '--disable-pinhole-gcp-init', # do initialise camera from GCP files

                ## Intrinsic imporvement
                
                ## Least square
                '--num-passes', '1', # iteration number
                
                ## Storage
                '--report-level', '20',
                '--save-cnet-as-csv', # Save key points in gcp point format
                '--inline-adjustments', # Store result in .tsai, not in adjsut
                ]

    def __init__(self, pathObj, lstId):
        self.pathDem=pathObj.pDem
        
        # Stereo
        self.argsInit+=['--overlap-list', pathObj.pStereoLst,] # stereopair file for key point extraction
            #OR
        #self.argsInit+=['--position-filter-dist', 'XXm',] # image couple for key point based on centre distance
        
        # Scenes
        if not type(lstId)==list : SubLogger('CRITICAL', 'Image list (lstId) must be a list of image id')
        lstId.sort()
        lstImgPath=[os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idCur)) for idCur in lstId]
        if False in [os.path.exists(pathCur) for pathCur in lstImgPath]: SubLogger('CRITICAL', 'Image(s) not found' )
        self.nbScene=len(lstImgPath)
        self.argsInit+=lstImgPath

        
        # Cameras
        self.lstTsaiName=[pathObj.nTsai[1].format(pathObj.extFeat1B.format(idCur).split('.')[0]) 
                                for idCur in lstId]
           
    def KeyPoints(self, prefIn, prefOut):
        '''
        Parameters for key point extraction
        '''
        strInd=' '.join([str(i) for i in range(self.nbScene)])
        
        args=self.argsInit.copy()
        if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        args+=['-o', prefOut]
        args+=[## Key points
                '--ip-detect-method','0', # algo (0=OBA-loG, 1=SIFT, 2=ORB)
                '--ip-per-tile', '100', # key point number
                '--ip-inlier-factor', '5e-3', # key point creation filtering (x>1/15 -> more points but worse): 
                '--ip-uniqueness-threshold', '0.1', # key point creation filtering (x>0.7 -> more points but less unique)
                #'--individually-normalize', # normalisation param per image not global 
                '--epipolar-threshold', '5', # key point matching, Max distance to the epipolar line in camera unit
                '--ip-num-ransac-iterations', '1000', # number of RANSAC iteration 
                '--enable-tri-ip-filter', # filter out key point based on triangulation
                #'--min-triangulation-angle', '0.2', # filtering min angle [°]: KP fails if bad RPC
                #'--forced-triangulation-distance', '450e3', # force distance to the camera if not trian fails: useless
                #'--stop-after-matching', # stop after matching key point: do not provide initial residuals
                ## Model
                '--fixed-camera-indices', "'%s'"% strInd, # fixed camera i
                #'--fix-gcp-xyz', # turn GCP to fixed: useless whether fixed-camera-indices in
                #'--max-disp-error', '10', # ??
                #'--remove-outliers-params', '"90.0 1.0 0.3 1.0"', # outlier filtering param
                #'--remove-outliers-by-disparity-params', '70.0 1.5', # outlier filtering param
                #'--elevation-limit', '0.0 4000.0 ' # outlier filtering param
                ## Least square
                '--max-iterations', '10', # in non-linear least square (per pass)
                #'--parameter-tolerance', '1e-6', # least square limite 
                ]
        
        return args

    def Init(self, prefIn, prefOut):
        '''
        Parameters with no freedom and not adjustment
        '''
        strInd=' '.join([str(i) for i in range(self.nbScene)])

        args=self.argsInit.copy()
        if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                '--camera-weight', '1', # EO weight (x>1 -> stiffer)
                '--fixed-camera-indices', "'%s'"% strInd, # fixed camera i
                ## Least square
                '--max-iterations', '1', # in non-linear least square (per pass)
                ]
        #args[args.index('--min-matches')+1]='1'
        
        return args

    def EO(self, prefIn, prefOut):
        '''
        Parameters which involve DEM to solve extrinsic cameras
        '''
        args=self.argsInit.copy()
        if os.path.isdir(prefIn):
            if not prefIn.endswith('/'): prefIn+='/'
        else:
            if not prefIn.endswith('-'): prefIn+='-'        
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        args.append(prefOut+'*.gcp')
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                #'--heights-from-dem', self.pathDem, # fix key point height from DSM
                #'--heights-from-dem-weight', '0.1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                #'--reference-terrain', self.pathDem, # When using a reference terrain, must specify a list of disparities.
                ## Model
                #'--rotation-weight', '0.01', 
                #'--translation-weight', '0.1', # EO weight (x>0 -> stiffer)
                # OR
                '--camera-weight', '1', # EO weight (x>1 -> stiffer)
                ## Least square
                #'--robust-threshold', '1000', # set cost function threshold
                #'--max-disp-error', '1', # with ref DSM
                ## Least square
                '--max-iterations', '200', # in non-linear least square (per pass)  
                #'--parameter-tolerance', '1e-5', # least square limit 
                ]

        return args

    def IO(self, prefIn, prefOut):
        '''
        Parameters which involve DEM to solve intrinsic cameras
        '''
        args=self.argsInit.copy()
        if os.path.isdir(prefIn):
            if not prefIn.endswith('/'): prefIn+='/'
        else:
            if not prefIn.endswith('-'): prefIn+='-'        
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: alternative to --overlap-list
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM
                ## Model
                #'--rotation-weight', '0', '--translation-weight', '0', # EO weight (x>0 -> stiffer)
                # OR
                '--camera-weight', '2', # EO weight (x>1 -> stiffer)
                ## Intrinsic imporvement
                '--solve-intrinsics', # include IO in BA (default=False) 
                '--intrinsics-to-float', "'focal_length' "# "'focal_length optical_center other_intrinsics' ", # list of IO param to solve
                #'--intrinsics-to-share', "'focal_length' "# "'focal_length optical_center other_intrinsics' ", # list of common IO param
                #'--reference-terrain', pathDict['pDem'], # intrinsic imporvement
                #'--reference-terrain-weight' # weight of the DEM in IO resolution (x>1 -> more impact)
                ## Least square
                #'--parameter-tolerance', '1e-2', # least square limite 
                ]
        args+=['-o', prefOut]
        args.remove('--save-cnet-as-csv')

        return args

    def Fix(self, prefIn, prefOut):
        '''
        Parameters with no freedom and not adjustment
        '''
        strInd=' '.join([str(i) for i in range(self.nbScene)])

        args=self.argsInit.copy()
        if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                '--fixed-camera-indices', "'%s'"% strInd, # fixed camera i
                ## Least square
                '--max-iterations', '1', # in non-linear least square (per pass)
                ]
        args[args.index('--num-passes')+1]='1'
        #args[args.index('--min-matches')+1]='1'
        
        return args




def Correct_DistoCam(pathObj, featCur):
    '''
    Correct camera files by changing 0 to a very small value (distortion only)

    pathObj (obj): PathCur clas from VarCur
    featCur (json): current feature desciptor
    out:
        
    '''
    # Initial files
    idImg=featCur['id']
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    pathTsai=pathObj.nTsai[1].format(pathImg1B.split('.')[0])
    if not os.path.exists(pathTsai): SubLogger('ERROR', 'Initial tsai file not found, %s'% pathTsai)

    # Read file
    with open(pathTsai) as fileIn:
        txtIn=fileIn.readlines()
    
    if not txtIn[12]=='TSAI\n': SubLogger('CRITICAL', 'Function not read for such distortion, please adjust it')

    fileOut=open(pathTsai, 'w')
    fileOut.writelines(txtIn[:13])
    for i in range(13,len(txtIn)):
        lineCur=txtIn[i].split('=')
        if not len(lineCur)>1: 
            fileOut.write(txtIn[i])
            continue
        
        if lineCur[-1].strip()=='0': 
            fileOut.write(txtIn[i].replace('0', '1e-20'))
        else:
            fileOut.write(txtIn[i])
    fileOut.close()
    
def CtlCam(pathObj, featCur):
    '''
    Compare centre coordinates to extended MD
    '''
    idImg=featCur['id']
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    pathTsai=pathObj.nTsai[1].format(pathImg1B.split('.')[0])
    if not os.path.exists(pathTsai): SubLogger('ERROR', 'Camera not found %s'% pathTsai)

    camPt=GeomFunc.ObjTsai(pathTsai)['matC'].flatten()

    pathSelect=os.path.join(pathObj.pB, fileSelec.format(os.path.basename(pathObj.pB)))
    if not os.path.exists(pathSelect): SubLogger('ERROR', 'Select file not found %s'% pathSelect)
    with open(pathSelect) as fileIn:
        jsonIn=json.load(fileIn)
    
    key=('Features'*('Features' in jsonIn) or 'features'*('features' in jsonIn))
    featProp=[feat for feat in jsonIn[key] if feat['id']==idImg][0]['properties']
    mdPt=np.array([featProp['ecefX_m'], featProp['ecefY_m'], featProp['ecefZ_m']])
    
    return camPt-mdPt

def CtlCamStat(lstIn):
    '''
    Summarize CtlCam results
    '''
    mat=np.array(lstIn)
    SubLogger('INFO', 'Camera position Statistics')
    print('ECEF [m]:\tX\tY\tZ\t3D')
    ave=np.round(np.average(mat, axis=0), 1)
    print('Average :', ave, np.round(np.sqrt(np.sum(np.square(ave))), 1))
    rms=np.round(np.sqrt(np.average(np.square(mat), axis=0)), 1)
    print('RMS     :', rms, np.round(np.sqrt(np.sum(np.square(rms))), 1))
    std=np.round(np.std(mat, axis=0), 1)
    print('Std Dev :', std, np.round(np.sqrt(np.sum(np.square(std))), 1))
    maxCur=np.round(np.amax(mat, axis=0), 1)
    print('Maximum :', maxCur, np.round(np.sqrt(np.sum(np.square(maxCur))), 1))
    minCur=np.round(np.amin(mat, axis=0), 1)
    print('Minimum :', minCur, np.round(np.sqrt(np.sum(np.square(minCur))), 1))

def KpCsv2Geojson(prefIn):
    '''
    Convert CSV files with key points from ASP to geojson files.

    prefIn (str): bundle adjustment prefix
    out:
        0
    '''
    from copy import deepcopy

    for nameCur in ('-initial_residuals_no_loss_function_pointmap_point_log.csv', '-final_residuals_no_loss_function_pointmap_point_log.csv'):  
        pathIn=prefIn+nameCur
        if not os.path.exists(pathIn): 
            SubLogger('ERROR', '%s file not found'% nameCur)
            continue
        pathOut=pathIn.replace('csv','geojson')
        if os.path.exists(pathOut): continue

        jsonOut=deepcopy(tempGeojson)
        jsonOut['name']=os.path.basename(pathIn).split('_')[0]

        with open(pathIn) as fileIn:
            for i,lineCur in enumerate(fileIn):
                if lineCur.startswith('#'): continue
                wordsCur=lineCur.strip().split(', ')

                dicOut={"type": "Feature", "id": i}
                dicOut["properties"]={'id': i,
                                      'Long': float(wordsCur[0]),
                                      'Lat': float(wordsCur[1]),
                                      'Height': float(wordsCur[2]),
                                      'Res': float(wordsCur[3]),
                                      'NbObs': int(wordsCur[4].replace(' # GCP', '')),
                                      'GCP': wordsCur[-1].endswith('GCP'),
                                      }
                dicOut["geometry"]= {"type": "Point", "coordinates":[float(wordsCur[0]), float(wordsCur[1]), float(wordsCur[2])]}
                jsonOut['Features'].append(dicOut)

        with open(pathOut, 'w') as fileOut:
            fileOut.write(json.dumps(jsonOut, indent=2))
    
    return 0

def KpCsv2Gcp(pathIn, prefOut, accuXY=1, accuZ=1, accuI=1):
    '''
    Read a cnet.csv file, change of point accuracy (Std Dev),
    save it to the Ba folder with gcp extention.

    Useful for BA-EO with GCP but the function does not 
    read DEM Height !!!
    '''
    descGound=('id', 'Lat', 'Long', 'H', 'sigX', 'sigY', 'sigZ')
    lenG=len(descGound)
    descImg=('path', 'x', 'y', 'sigx', 'sigy')
    lenI=len(descImg)
    
    # Read
    with open(pathIn) as fileIn:
        lstIn=[lineCur.strip().split() for lineCur in fileIn.readlines()]

    # Update and write
    pathOut=prefOut+'-KP2GCP_XY%i_Z%i_I%i.gcp'% (accuXY, accuZ, accuI)
    fileOut=open(pathOut, 'w')

    for ptIn in lstIn:
        ptOut=[]
        
        # Ground
        for i in range(lenG):
            if not i in (4, 5, 6):
                ptOut.append(ptIn[i])
                continue
            if i==6:
                ptOut.append(str(accuZ))
            else:
                ptOut.append(str(accuXY))
                
            
        # Image
        nbImg=(len(ptIn)-lenG)//lenI
        for j in range(nbImg):  
            # Image Path
            ptOut.append(ptIn[lenG+j*lenI]) 
            
            # Coords
            for i in (1, 2):
                coord=float(ptIn[lenG+j*lenI+i])
                ptOut.append(str(round(coord, 3)))

            # StdDev
            for i in (3,4):
                coord=float(ptIn[lenG+j*lenI+i-2])
                ptOut.append(str(accuI))
                #if coord%1:
                #    ptOut.append(str(accuI*0.1))
                #else:
                #    ptOut.append(str(accuI))
                
        fileOut.write(' '.join(ptOut)+'\n')
    
    fileOut.close()
    return 0

def DisplayMat(mat):
    from PIL import Image
    print('Matrix (%ix%i, rk=%i):'% (mat.shape[0],mat.shape[1],matrix_rank(mat)))
    print(np.abs(mat).astype(bool).astype(int))
    matDisp=(mat==0).astype(int)*255
    print('Image: White=0; Black=full (±)')
    imgMat=Image.fromarray(matDisp.astype(float))
    imgMat.show()
    sys.exit()

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
'''
Usage: /app/StereoPipeline/libexec/bundle_adjust <images> 
                                                <cameras> 
                                                <optional ground control points> 
                                                -o <output prefix> 
                                                [options]
  -o [ --output-prefix ] arg            Prefix for output filenames.
  --cost-function arg (=Cauchy)         Choose a cost function from: Cauchy, 
                                        PseudoHuber, Huber, L1, L2, Trivial.
  --robust-threshold arg (=0.5)         Set the threshold for robust cost 
                                        functions. Increasing this makes the 
                                        solver focus harder on the larger 
                                        errors.
  --inline-adjustments                  If this is set, and the input cameras 
                                        are of the pinhole or panoramic type, 
                                        apply the adjustments directly to the 
                                        cameras, rather than saving them 
                                        separately as .adjust files.
  --approximate-pinhole-intrinsics      If it reduces computation time, 
                                        approximate the lens distortion model.
  --solve-intrinsics                    Optimize intrinsic camera parameters.  
                                        Only used for pinhole cameras.
  --intrinsics-to-float arg             If solving for intrinsics and desired 
                                        to float only a few of them, specify 
                                        here, in quotes, one or more of: 
                                        focal_length, optical_center, 
                                        other_intrinsics.
  --intrinsics-to-share arg             If solving for intrinsics and desired 
                                        to share only a few of them, specify 
                                        here, in quotes, one or more of: 
                                        focal_length, optical_center, 
                                        other_intrinsics.
  --intrinsics-limits arg               Specify minimum and maximum ratios for 
                                        the intrinsic parameters. Values must 
                                        be in min max pairs and are applied in 
                                        the order [focal length, optical 
                                        center, other intrinsics] until all of 
                                        the limits are used. Check the 
                                        documentation to dermine how many 
                                        intrinsic parameters are used for your 
                                        cameras.
  --camera-positions arg                Specify a csv file path containing the 
                                        estimated positions of the input 
                                        cameras.  Only used with the 
                                        inline-adjustments option.
  --disable-pinhole-gcp-init            Don't try to initialize the positions 
                                        of pinhole cameras based on input GCPs.
  --transform-cameras-using-gcp         Use GCP, even those that show up in 
                                        just an image, to transform cameras to 
                                        ground coordinates. Need at least two 
                                        images to have at least 3 GCP each. If 
                                        at least three GCP each show up in at 
                                        least two images, the transform will 
                                        happen even without this option using a
                                        more robust algorithm.
  --input-adjustments-prefix arg        Prefix to read initial adjustments 
                                        from, written by a previous invocation 
                                        of this program.
  --initial-transform arg               Before optimizing the cameras, apply to
                                        them the 4x4 rotation + translation 
                                        transform from this file. The transform
                                        is in respect to the planet center, 
                                        such as written by pc_align's 
                                        source-to-reference or 
                                        reference-to-source alignment 
                                        transform. Set the number of iterations
                                        to 0 to stop at this step. If 
                                        --input-adjustments-prefix is 
                                        specified, the transform gets applied 
                                        after the adjustments are read.
  --fixed-camera-indices arg            A list of indices, in quotes and 
                                        starting from 0, with space as 
                                        separator, corresponding to cameras to 
                                        keep fixed during the optimization 
                                        process.
  --fix-gcp-xyz                         If the GCP are highly accurate, use 
                                        this option to not float them during 
                                        the optimization.
  --csv-format arg                      Specify the format of input CSV files 
                                        as a list of entries 
                                        column_index:column_type (indices start
                                        from 1). Examples: '1:x 2:y 3:z', 
                                        '2:file 5:lon 6:lat 7:radius_m', '3:lat
                                        2:lon 1:height_above_datum 5:file', 
                                        '1:easting 2:northing 
                                        3:height_above_datum' (need to set 
                                        --csv-proj4). Can also use radius_km 
                                        for column_type.
  --csv-proj4 arg                       The PROJ.4 string to use to interpret 
                                        the entries in input CSV files.
  --reference-terrain arg               An externally provided trustworthy 3D 
                                        terrain, either as a DEM or as a lidar 
                                        file, very close (after alignment) to 
                                        the stereo result from the given images
                                        and cameras that can be used as a 
                                        reference, instead of GCP, to optimize 
                                        the intrinsics of the cameras.
  --max-num-reference-points arg (=100000000)
                                        Maximum number of (randomly picked) 
                                        points from the reference terrain to 
                                        use.
  --disparity-list arg                  The unaligned disparity files to use 
                                        when optimizing the intrinsics based on
                                        a reference terrain. Specify them as a 
                                        list in quotes separated by spaces. 
                                        First file is for the first two images,
                                        second is for the second and third 
                                        images, etc. If an image pair has no 
                                        disparity file, use 'none'.
  --max-disp-error arg (=-1)            When using a reference terrain as an 
                                        external control, ignore as outliers 
                                        xyz points which projected in the left 
                                        image and transported by disparity to 
                                        the right image differ by the 
                                        projection of xyz in the right image by
                                        more than this value in pixels.
  --reference-terrain-weight arg (=1)   How much weight to give to the cost 
                                        function terms involving the reference 
                                        terrain.
  --heights-from-dem arg                If the cameras have already been 
                                        bundle-adjusted and aligned to a known 
                                        high-quality DEM, in the triangulated 
                                        xyz points replace the heights with the
                                        ones from this DEM, and fix those 
                                        points unless --heights-from-dem-weight
                                        is positive.
  --heights-from-dem-weight arg (=-1)   How much weight to give to keep the 
                                        triangulated points close to the DEM if
                                        specified via --heights-from-dem. If 
                                        the weight is not positive, keep the 
                                        triangulated points fixed.
  --heights-from-dem-robust-threshold arg (=0)
                                        If positive, the robust threshold to 
                                        use keep the triangulated points close 
                                        to the DEM if specified via 
                                        --heights-from-dem. This is applied 
                                        after the point differences are 
                                        multiplied by --heights-from-dem-weight
                                        .
  --datum arg                           Use this datum. Needed only for ground 
                                        control points, a camera position file,
                                        or for RPC sessions. Options: WGS_1984,
                                        D_MOON (1,737,400 meters), D_MARS 
                                        (3,396,190 meters), MOLA (3,396,000 
                                        meters), NAD83, WGS72, and NAD27. Also 
                                        accepted: Earth (=WGS_1984), Mars 
                                        (=D_MARS), Moon (=D_MOON).
  --semi-major-axis arg (=0)            Explicitly set the datum semi-major 
                                        axis in meters (see above).
  --semi-minor-axis arg (=0)            Explicitly set the datum semi-minor 
                                        axis in meters (see above).
  -t [ --session-type ] arg             Select the stereo session type to use 
                                        for processing. Options: nadirpinhole 
                                        pinhole isis dg rpc spot5 aster 
                                        opticalbar csm. Usually the program can
                                        select this automatically by the file 
                                        extension.
  --min-matches arg (=30)               Set the minimum  number of matches 
                                        between images that will be considered.
  --ip-detect-method arg (=0)           Interest point detection algorithm (0: 
                                        Integral OBALoG (default), 1: OpenCV 
                                        SIFT, 2: OpenCV ORB.
  --epipolar-threshold arg (=-1)        Maximum distance from the epipolar line
                                        to search for IP matches. Default: 
                                        automatic calculation. A higher values 
                                        will result in more matches.
  --ip-inlier-factor arg (=0.20000000000000001)
                                        A higher factor will result in more 
                                        interest points, but perhaps also more 
                                        outliers. This is used only with 
                                        homography alignment, such as for the 
                                        pinhole session.
  --ip-uniqueness-threshold arg (=0.80000000000000004)
                                        A higher threshold will result in more 
                                        interest points, but perhaps less 
                                        unique ones.
  --ip-side-filter-percent arg (=-1)    Remove matched IPs this percentage from
                                        the image left/right sides.
  --normalize-ip-tiles                  Individually normalize tiles used for 
                                        IP detection.
  --num-obalog-scales arg (=-1)         How many scales to use if detecting 
                                        interest points with OBALoG. If not 
                                        specified, 8 will be used. More can 
                                        help for images with high frequency 
                                        artifacts.
  --nodata-value arg (=nan)             Pixels with values less than or equal 
                                        to this number are treated as no-data. 
                                        This overrides the no-data values from 
                                        input images.
  --num-iterations arg (=1000)          Set the maximum number of iterations.
  --max-iterations arg (=1000)          Set the maximum number of iterations.
  --parameter-tolerance arg (=1e-08)    Stop when the relative error in the 
                                        variables being optimized is less than 
                                        this.
  --overlap-limit arg (=0)              Limit the number of subsequent images 
                                        to search for matches to the current 
                                        image to this value.  By default match 
                                        all images.
  --overlap-list arg                    A file containing a list of image 
                                        pairs, one pair per line, separated by 
                                        a space, which are expected to overlap.
                                        Matches are then computed only among 
                                        the images in each pair.
  --auto-overlap-buffer arg (=-1)       Try to automatically guess which images
                                        overlap with the provided buffer in 
                                        lonlat degrees.
  --position-filter-dist arg (=-1)      Set a distance in meters and don't 
                                        perform IP matching on images with an 
                                        estimated camera center farther apart 
                                        than this distance.  Requires 
                                        --camera-positions.
  --rotation-weight arg (=0)            A higher weight will penalize more 
                                        rotation deviations from the original 
                                        configuration.
  --translation-weight arg (=0)         A higher weight will penalize more 
                                        translation deviations from the 
                                        original configuration.
  --camera-weight arg (=1)              The weight to give to the constraint 
                                        that the camera positions/orientations 
                                        stay close to the original values (only
                                        for the Ceres solver).  A higher weight
                                        means that the values will change less.
                                        The options --rotation-weight and 
                                        --translation-weight can be used for 
                                        finer-grained control and a stronger 
                                        response.
  --overlap-exponent arg (=0)           If a feature is seen in n >= 2 images, 
                                        give it a weight proportional with 
                                        (n-1)^exponent.
  --ip-per-tile arg (=0)                How many interest points to detect in 
                                        each 1024^2 image tile (default: 
                                        automatic determination).
  --num-passes arg (=2)                 How many passes of bundle adjustment to
                                        do. If more than one, outliers will be 
                                        removed between passes using 
                                        --remove-outliers-params and 
                                        --remove-outliers-by-disparity-params, 
                                        and re-optimization will take place. 
                                        Residual files and a copy of the match 
                                        files with the outliers removed will be
                                        written to disk.
  --num-random-passes arg (=0)          After performing the normal bundle 
                                        adjustment passes, do this many more 
                                        passes using the same matches but 
                                        adding random offsets to the initial 
                                        parameter values with the goal of 
                                        avoiding local minima that the 
                                        optimizer may be getting stuck in.
  --remove-outliers-params arg (='pct factor err1 err2')
                                        Outlier removal based on percentage, 
                                        when more than one bundle adjustment 
                                        pass is used. Triangulated points (that
                                        are not GCP) with reprojection error in
                                        pixels larger than min(max('pct'-th 
                                        percentile * 'factor', err1), err2) 
                                        will be removed as outliers. Hence, 
                                        never remove errors smaller than err1 
                                        but always remove those bigger than 
                                        err2. Specify as a list in quotes. 
                                        Default: '75.0 3.0 2.0 3.0'.
  --remove-outliers-by-disparity-params arg (=pct factor)
                                        Outlier removal based on the disparity 
                                        of interest points (difference between 
                                        right and left pixel), when more than 
                                        one bundle adjustment pass is used. For
                                        example, the 10% and 90% percentiles of
                                        disparity are computed, and this 
                                        interval is made three times bigger. 
                                        Interest points (that are not GCP) 
                                        whose disparity falls outside the 
                                        expanded interval are removed as 
                                        outliers. Instead of the default 90 and
                                        3 one can specify pct and factor, 
                                        without quotes.
  --elevation-limit arg (=auto)         Remove as outliers interest points 
                                        (that are not GCP) for which the 
                                        elevation of the triangulated position 
                                        (after cameras are optimized) is 
                                        outside of this range. Specify as two 
                                        values: min max.
  --lon-lat-limit arg (=auto)           Remove as outliers interest points 
                                        (that are not GCP) for which the 
                                        longitude and latitude of the 
                                        triangulated position (after cameras 
                                        are optimized) are outside of this 
                                        range. Specify as: min_lon min_lat 
                                        max_lon max_lat.
  --enable-rough-homography             Enable the step of performing 
                                        datum-based rough homography for 
                                        interest point matching. This is best 
                                        used with reasonably reliable input 
                                        cameras and a wide footprint on the 
                                        ground.
  --skip-rough-homography               Skip the step of performing datum-based
                                        rough homography. This obsolete option 
                                        is ignored as is the default.
  --enable-tri-ip-filter                Enable triangulation-based interest 
                                        points filtering. This is best used 
                                        with reasonably reliable input cameras.
  --disable-tri-ip-filter               Disable triangulation-based interest 
                                        points filtering. This obsolete option 
                                        is ignored as is the default.
  --no-datum                            Do not assume a reliable datum exists, 
                                        such as for irregularly shaped bodies.
  --individually-normalize              Individually normalize the input images
                                        instead of using common values.
  --ip-triangulation-max-error arg (=-1)
                                        When matching IP, filter out any pairs 
                                        with a triangulation error higher than 
                                        this.
  --ip-num-ransac-iterations arg (=1000)
                                        How many RANSAC iterations to do in 
                                        interest point matching.
  --min-triangulation-angle arg (=0.10000000000000001)
                                        The minimum angle, in degrees, at which
                                        rays must meet at a triangulated point 
                                        to accept this point as valid.
  --forced-triangulation-distance arg (=-1)
                                        When triangulation fails, for example, 
                                        when input cameras are inaccurate, 
                                        artificially create a triangulation 
                                        point this far ahead of the camera, in 
                                        units of meter.
  --use-lon-lat-height-gcp-error        When having GCP, interpret the three 
                                        standard deviations in the GCP file as 
                                        applying not to x, y, and z, but rather
                                        to latitude, longitude, and height.
  --force-reuse-match-files             Force reusing the match files even if 
                                        older than the images or cameras.
  --mapprojected-data arg               Given map-projected versions of the 
                                        input images, the DEM they were 
                                        mapprojected onto, and IP matches among
                                        the mapprojected images, create IP 
                                        matches among the un-projected images 
                                        before doing bundle adjustment. Specify
                                        the mapprojected images and the DEM as 
                                        a string in quotes, separated by 
                                        spaces. An example is in the 
                                        documentation.
  --save-cnet-as-csv                    Save the control network containing all
                                        interest points in the format used by 
                                        ground control points, so it can be 
                                        inspected.
  --gcp-from-mapprojected-images arg    Given map-projected versions of the 
                                        input images, the DEM the were 
                                        mapprojected onto, and interest point 
                                        matches among all of these created in 
                                        stereo_gui, create GCP for the input 
                                        images to align them better to the DEM.
                                        This is experimental and not 
                                        documented.
  --instance-count arg (=1)             The number of bundle_adjustment 
                                        processes being run in parallel.
  --instance-index arg (=0)             The index of this parallel bundle 
                                        adjustment process.
  --stop-after-statistics               Quit after computing image statistics.
  --stop-after-matching                 Quit after writing all match files.
  --skip-matching                       Only use image matches which can be 
                                        loaded from disk.
  --ip-debug-images [=arg(=1)] (=0)     Write debug images to disk when 
                                        detecting and matching interest points.
  -r [ --report-level ] arg (=10)       Use a value >= 20 to get increasingly 
                                        more verbose output.

  --threads arg (=0)                    Select the number of processors 
                                        (threads) to use.
  --tile-size arg (=256, 256)           Image tile size used for multi-threaded
                                        processing.
  --no-bigtiff                          Tell GDAL to not create bigtiffs.
  --tif-compress arg (=LZW)             TIFF Compression method. [None, LZW, 
                                        Deflate, Packbits]
  -v [ --version ]                      Display the version of software.
  -h [ --help ]                         Display this help message.

'''



