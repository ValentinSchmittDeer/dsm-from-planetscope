#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, time
import json, csv
import logging
from glob import glob
from math import sin, cos, asin, acos, tan, atan2, pi, ceil
import numpy as np
from numpy.linalg import norm, inv, lstsq, det, svd, matrix_rank, qr
from scipy.linalg import expm
from scipy.optimize import least_squares
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
from PCT import pipelDFunc

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['SubArgs_Ortho', 'SubArgs_StereoKP_RPC', 'SubArgs_Adj2Rpc', 'SubArgs_BunAdj', 'SingleBandImg', 'StereoDescriptor', 'MaskedImg_KP', 'AspPnP_RPCwithoutDisto', 'AspPnP_SubArgs_Camgen', 'AspPnP_ConvertPM', 'PnP_OCV', 'KpCsv2Geojson', 'CopyPrevBA', 'KpCsv2Gcp']
SetupLogger(name=__name__)
#SubLogger('ERROR', 'jojo')

gdInfo='gdalinfo'
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------            
def SubArgs_Ortho(pathImgIn, pathModIn, pathDemIn, pathOrthoOut, epsg=4326):
    '''
    Create a list of mapproject parameters
    
    pathImgIn (str): input image
    pathModIn (str): input location model
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
    if pathModIn.endswith('_RPC.TXT'):
        pathModComput=pathImgIn[:-4]+'_RPC.TXT'
        os.system('cp %s %s'% (pathModIn, pathModComput))
        typeCur='rpc'
    elif pathModIn.endswith('.tsai'):
        pathModComput=pathModIn
        typeCur='nadirpinhole'

    # Arguments
    subArgs=[pathDemIn,
            pathImgIn,
            pathModComput,
            pathOrthoOut,
            '--t_srs', 'EPSG:'+str(epsg), 
            '-t', typeCur,
            '--tr', str(gsdOrth),
            '--ot', 'UInt16',
            ]

    # Delete RPC file after
    if pathModIn.endswith('_RPC.TXT'): subArgs+=['; rm', pathModComput] 

    return subArgs

def SubArgs_StereoKP_RPC(prefOut, lstPath, softness=0):
    '''
    Create a list of stereo_pprc parameters for key point extraction per pair

    prefOut (str): output prefix
    lstPath ([(ImgPath, RpcPath), (ImgPath, RpcPath)]): list of path after mask
    softness (int [0-2]): interger designing feature filtering parameter set hardness, 0:hard 2:soft (release freedom)
    out:
        subArgs (list): argument list
    '''
    # Softness parameters
    # 0: ip-uniqueness-threshold
    # 1: epipolar-threshold
    # 2: disable-tri-ip-filter
    lstSoft=(('0.4', '2', '0'), # Hard
             ('0.7', '5', '0'), 
             ('0.6', '3', '1'),
             ('0.7', '3', '1'), # Soft
             )[softness]

    subArgs=[imgPath for imgPath, rpcPath in lstPath]
    
    dirOut=os.path.dirname(prefOut)
    
    if os.path.exists(dirOut): os.system('rm -r %s'% dirOut)
    subArgs.append(prefOut)
    
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
                #'--ip-per-tile', '1000', # key point number per sub frame
                '--individually-normalize', # normalisation param per image not global
                ## Feature matching
                #'--ip-inlier-factor', '1e-4', # key point creation filtering (x>1/15 -> more points but worse)
                '--ip-uniqueness-threshold', lstSoft[0], # key point creation filtering (x>0.7 -> more points but less unique)
                '--epipolar-threshold', lstSoft[1], # key point matching, Max distance to the epipolar line in camera unit
                ## Feature filtering
                '--ip-num-ransac-iterations', '1000', # number of RANSAC iteration
                '--disable-tri-ip-filter', lstSoft[2], # disable the triangulation filtering
                #'--ip-triangulation-max-error', '1000', # filter out key point based on triangulation
                #'--stddev-mask-thresh', '0.01', # mask (filter) key point whether the local standard deviation is less
                #'--stddev-mask-kernel', '51', # size of the local standard deviation computation
                ##
                #'--num-matches-from-disparity', '100', # create key point grid after disparity computation (needs full stereo process)
                '--num-matches-from-disp-triplets', '500', # same linking multiview points
                #'--min-triangulation-angle', '0.01'
                '--filter-mode', '0', # Avoid filtering: spare time
                #'--stop-point', '2', # Stop the stereo pipeline 
                ]
    if softness==3: subArgs+= ['--ip-per-tile', '1000'] # key point number per sub frame

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

class SubArgs_BunAdj:
    '''
    Create a list of bundle_adjust parameters. Several cases are available as functions.

    pathObj (obj): PathCur class from VarCur
    lstPairs (list): list of image ID
    out:
        SubArgs_BunAdj (obj):
            KeyPoints (funct):
    '''
    def __init__(self, pathOverlap, dirProcData, dirData, lstId, extImg, extRpc, extRpc1b, extTsai, mode):
        self.argsInit=[ ## Basics
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
                        #'--report-level', '20',
                        '--save-cnet-as-csv', # Save key points in gcp point format
                        ]

        # Mode
        if mode=='rpc':
            self.argsInit+=['-t', 'rpc', # set stereo session pinhole OR nadirpinhole
                            ]
        if mode=='pm':
            self.argsInit+=['-t', 'nadirpinhole', # set stereo session pinhole OR nadirpinhole
                            '--inline-adjustments', # Store result in .tsai, not in adjsut
                            ]

        # Stereo list
        self.argsInit+=['--overlap-list', pathOverlap,] # stereopair file for key point extraction
            #OR
        #self.argsInit+=['--position-filter-dist', 'XXm',] # image couple for key point based on centre distance
        
        # Scenes
        if not type(lstId)==list : SubLogger('CRITICAL', 'Image list (lstId) must be a list of image id')
        lstId.sort()
        lstImgPath=[os.path.join(dirProcData, extImg.format(idCur)) 
                        for idCur in lstId]
        if not all([os.path.exists(pathCur) for pathCur in lstImgPath]): SubLogger('CRITICAL', 'Image(s) not found' )
        self.nbScene=len(lstImgPath)
        self.argsInit+=lstImgPath

        # RPC
        lstRPCPath=[os.path.join(dirData, extRpc.format(idCur)) 
                            for idCur in lstId]
        if not all([os.path.exists(pathCur) for pathCur in lstRPCPath]): SubLogger('CRITICAL', 'RPC(s) not found' )
        lstRPCUse=[os.path.join(dirProcData, extRpc1b.format(idCur)) 
                            for idCur in lstId]
        self.zipRPC=tuple(zip(lstRPCPath, lstRPCUse))

        # Cameras
        self.lstTsaiName=[extTsai.format(idCur) for idCur in lstId]       

    def KP_RPC(self, prefIn, prefOut, pathDem):
        '''
        Feature extraction merging bundle adjustment. It compute a fixed bundle adjustment
        using the existing .match file and returns the initial coordinates.
        '''
        strInd=' '.join([str(i) for i in range(self.nbScene)])

        # RPC copy
        #if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        [os.system('cp %s %s'% couple) for couple in self.zipRPC]

        args=self.argsInit.copy()
        
        # Case of PM-BA with RPC-KP
        args[args.index('-t')+1]='rpc'
        try:
             args.remove('--inline-adjustments')
        except ValueError:
            pass
        
        args+=['-o', prefOut]
        args+=[## Key points
                '--individually-normalize', # normalisation param per image not global
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                '--heights-from-dem', pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                '--camera-weight', '1', # EO weight (x>1 -> stiffer)
                '--fixed-camera-indices', "'%s'"% strInd, # fixed camera i
                ## Least square
                '--max-iterations', '1', # in non-linear least square (per pass)
                ]

        # Clear RPC
        args+=['; rm']+[fPocData for fData,fPocData in self.zipRPC]

        return args

    def EO_RPC(self, prefIn, prefOut, pathDem):
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
                '--heights-from-dem', pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                '--camera-weight', '0.1', # EO weight (x>1 -> stiffer)
                ## Least square
                '--max-iterations', '200', # in non-linear least square (per pass)
                ]

        # Clear RPC
        args+=['; rm']+[fPocData for fData,fPocData in self.zipRPC]

        return args
    
    def EO_PM(self, prefIn, prefOut, pathGCP):
        '''
        Parameters solving extrinsic parameters from RPC-GCP
        '''
        args=self.argsInit.copy()
        if os.path.isdir(prefIn):
            if not prefIn.endswith('/'): prefIn+='/'
        else:
            if not prefIn.endswith('-'): prefIn+='-' 
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        if pathGCP: args.append(pathGCP)
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                #'--heights-from-dem', pathDem, # fix key point height from DSM
                #'--heights-from-dem-weight', '0.1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                #'--rotation-weight', '1', 
                #'--translation-weight', '0', # EO weight (x>0 -> stiffer) or
                '--camera-weight', '2', # EO weight (x>1 -> stiffer)
                ## Least square
                '--remove-outliers-params','"90.0 1.0 1.0 2.0"',
                #'--robust-threshold', '1000', # set cost function threshold
                #'--max-disp-error', '1', # with ref DSM
                ## Least square
                '--max-iterations', '100', # in non-linear least square (per pass)  
                #'--parameter-tolerance', '1e-7', # least square limit
                ]

        args[args.index('--num-passes')+1]='2' # iteration number
        return args

    def IO_PM(self, prefIn, prefOut, pathGCP):
        '''
        Parameters solving intrinsic parameters from large extrinsic weight
        '''
        args=self.argsInit.copy()
        if os.path.isdir(prefIn):
            if not prefIn.endswith('/'): prefIn+='/'
        else:
            if not prefIn.endswith('-'): prefIn+='-' 
        lstPathTsai=[glob(prefIn+'*'+nameCur)[0] for nameCur in self.lstTsaiName if len(glob(prefIn+'*'+nameCur))==1]
        if not lstPathTsai or not len(lstPathTsai)==self.nbScene: SubLogger('CRITICAL', 'Input cameras not complet')
        args+= lstPathTsai
        if pathGCP: args.append(pathGCP)
        args+=['-o', prefOut]
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                ## Model
                #'--heights-from-dem', pathDem, # fix key point height from DSM
                #'--heights-from-dem-weight', '0.1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                #'--rotation-weight', '1', 
                #'--translation-weight', '0', # EO weight (x>0 -> stiffer)
                '--camera-weight', '10', # EO weight (x>1 -> stiffer)
                ## Intrinsic imporvement
                '--solve-intrinsics', # include IO in BA (default=False) 
                '--intrinsics-to-float', '"optical_center"', # "'focal_length optical_center other_intrinsics' ", # list of IO param to solve
                #'--intrinsics-to-share', '"other_intrinsics"', # "'focal_length optical_center other_intrinsics' ", # list of common IO param
                #'--reference-terrain', pathDem, # use a reference terrain to create points for instrinsic adjust: needs disparities map list
                #'--disparity-list', 'file name chaine as string', # list of disparity map paths: for reference terrain
                #'--reference-terrain-weight', '1',
                ## Least square
                #'--remove-outliers-params','"80.0 1.0 1.0 2.0"',
                #'--robust-threshold', '1000', # set cost function threshold
                #'--max-disp-error', '1', # with ref DSM
                ## Least square
                '--max-iterations', '100', # in non-linear least square (per pass)  
                #'--parameter-tolerance', '1e-7', # least square limit 1e-7
                ]

        #args[args.index('--num-passes')+1]='2' # iteration number
        return args

def SingleBandImg(pathIn, pathOut, imgType='green'):
    '''
    Convert image to a single band image for further process.
    The single band is extracted accroting to the type argument.
    The RPC metadata is also removed to force provided one.

    pathIn (str): input path
    pathOut (str): output path
    imgType ('green'|'hsv'): extraction mode (default: green)
    out:
        process output
    '''
    if imgType=='green':
        cmd='gdal_translate -b 2 -of GTiff -co PROFILE=BASELINE -q %s %s'% (pathIn, pathOut)
        cmd+=' ; rm {0}RPB ; rm {0}tif.aux.xml'.format(pathOut[:-3])
        return os.system(cmd)
    elif imgType=='hsv':
        img = cv.imread(pathIn, cv.IMREAD_LOAD_GDAL+(-1)) # equivalent to 'cv.IMREAD_ANYDEPTH + cv.IMREAD_COLOR'
        
        # Overal normalisation (max normalisation avoid float32 crop)
        imgMax=np.amax(img)
        img_n=(img/imgMax).astype(np.float32)
        
        imgHSV_n = cv.cvtColor(img_n, cv.COLOR_BGR2HSV)
        if 1: # Back scaling
            imgHSV=np.append(imgHSV_n[:,:,[0]], imgHSV_n[:,:,1:]*imgMax, axis=2).astype(np.uint16)
        else: # Full range stretching
            imgHSV=np.append(imgHSV_n[:,:,[0]], imgHSV_n[:,:,1:]*65535, axis=2).astype(np.uint16)
        
        # Img[hue, saturation, value]
        cv.imwrite(pathOut, imgHSV[:,:,-1])

    elif imgType=='hls':
        img = cv.imread(pathIn, cv.IMREAD_LOAD_GDAL+(-1)) # equivalent to 'cv.IMREAD_ANYDEPTH + cv.IMREAD_COLOR'
        
        # Overal normalisation (max normalisation avoid float32 crop)
        imgMax=np.amax(img)
        img_n=(img/imgMax).astype(np.float32)
        
        imgHLS_n = cv.cvtColor(img_n, cv.COLOR_BGR2HLS)
        if 1: # Back scaling
            imgHLS=np.append(imgHLS_n[:,:,[0]], imgHLS_n[:,:,1:]*imgMax, axis=2).astype(np.uint16)
        else: # Full range stretching
            imgHLS=np.append(imgHLS_n[:,:,[0]], imgHLS_n[:,:,1:]*65535, axis=2).astype(np.uint16)
        
        # Img[hue, lightness, saturation]
        cv.imwrite(pathOut, imgHLS[:,:,1])
    else:
        SubLogger('CRITICAL', 'Unknown imgType: %s'% imgType)

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

def MaskedImg_KP(pathImgIn, pathRpc, pathDem, geomIn, pathImgOut, b=10):
    '''
    Mirror to the GeomFunc.MaskedImg function.
    '''
    return GeomFunc.MaskedImg( pathImgIn, pathRpc, pathDem, geomIn, pathImgOut=pathImgOut, buffer=b)

def AspPnP_RPCwithoutDisto(sceneId, pathRpcIn, pathRpcOut):
    '''
    Create RPC without distortion in. It makes uses of Tsai object to undistort
    points.
    
    sceneId (str): scene ID text
    pathRpcIn (str): RPC path
    pathRpcOut (str): path corrected RPC 
    out:
        0 (int)
    '''
    # Create objects
    objRpcIn=GeomFunc.RPCin(pathRpcIn)
    
    emptyCam={'fu': camFocal,
              'fv': camFocal,
              'cu': camCentre[0],
              'cv': camCentre[1],
              'pitch': camPitch,
              'distoType': 'NULL'}
    objCam=GeomFunc.TSAIin(emptyCam)

    # Update distortion model
    hardwId=sceneId.split('_')[-1]
    for keyNew, valNew in pipelDFunc.ExtractDisto(hardwId, 'photometrix'):
        setattr(objCam, keyNew, valNew)
    
    # Point pairs
    # grid from image
    meshRange=np.meshgrid(np.linspace(-1.0, 1.0, num=11), # x
                          np.linspace(-1.0, 1.0, num=11), # y
                          np.linspace(-0.2, 0.2, num=11)) # H
    matPtsImg_d=np.vstack((meshRange[0].flatten(), meshRange[1].flatten())).T*objRpcIn.Scale(d=2)+objRpcIn.Offset(d=2)
    matPtsH=meshRange[2].reshape(-1,1)*objRpcIn.heiScale+objRpcIn.heiOffset
    objRpcIn.Comput_InvRPC()
    matPtsGeo=objRpcIn.Img2Obj_Z(matPtsImg_d,matPtsH)
    matPtsCart=GeomFunc.Geo2Cart_Elli(matPtsGeo)
    nbPts=matPtsCart.shape[0]

    matPtsImg_u=objCam.ApplyDisto('remove', matPtsImg_d)

    objRpcIn.Comput_RPC(matPtsGeo, matPtsImg_u)
    
    with open(pathRpcOut, 'w') as fileOut:
        fileOut.writelines(objRpcIn.__write__())

    return 0

def AspPnP_SubArgs_Camgen(sceneId, pathImgIn, pathRpcIn, pathDemIn, pathCamOut, pattern='circle'):
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
    
    #pathGcp=pathCamOut.split('.')[0]+'.gcp'

    # Copy model
    pathRpcTemp=pathImgIn[:-4]+'_RPC.TXT'
    os.system('cp %s %s'% (pathRpcIn, pathRpcTemp))

    # Point distribution
    txtGdal=os.popen('%s %s'% (gdInfo,pathImgIn)).readlines()
    strSize=[lineCur.strip('\nSize is').split(',') for lineCur in txtGdal if lineCur.startswith('Size')][0]
    imgShape=(int(strSize[1]), int(strSize[0]))

    matOriOff_pxl=pipelDFunc.ExtractFrameOffset(pathImgIn)

    # Circle grid
    if pattern=='circle':
        x0=camCentre[0]//camPitch+matOriOff_pxl[0]
        y0=camCentre[1]//camPitch+matOriOff_pxl[1]
        lstPxlPts=[(x0,y0),]
        for rCur in range(ptSpace,ptRadiusFact*ptSpace+1, ptSpace):
            lstPxlPts.append((x0+rCur, y0))
            dAlpha=2*asin(ptSpace/2/rCur)
            lstPxlPts+=[(x0+int(rCur*cos(alpha)), y0+int(rCur*sin(alpha))) for alpha in np.arange(dAlpha, 2*pi, dAlpha)]
    # Grid  
    else:
        widthRange=np.linspace(0, 6600, num=11)+matOriOff_pxl[0]
        heighRange=np.linspace(0, 4400, num=11)+matOriOff_pxl[1]
        lstPxlPts=[(wiCur, heiCur) for wiCur in widthRange for heiCur in heighRange]
    
    strPxlPts=','.join(['%i %i'% (i,j) for i,j in lstPxlPts])

    # Use distortion centre as PP (like OpenCV method)
    hardwId=sceneId.split('_')[-1]
    dictDisto=dict(pipelDFunc.ExtractDisto(hardwId, 'tsai'))
    camCentre=np.array([dictDisto['cu'], dictDisto['cv']])

    # Arguments
    subArgs=[pathImgIn,
            '--input-camera',pathRpcIn,
            '-t', 'rpc',
            '--camera-type', 'pinhole',
            '--reference-dem', pathDemIn,
            '--optical-center', str(camCentre+matOriOff_pxl*camPitch).strip('[]'),
            '--focal-length', str(camFocal),
            '--pixel-pitch', str(camPitch),
            '--pixel-values', '{!r}'.format(strPxlPts), 
            '-o', pathCamOut,
            '--refine-camera',
            #'--gcp-file', pathGcp,
            ]

    subArgs+=['; rm', pathRpcTemp] # remove RPC file after
    
    return subArgs

def AspPnP_ConvertPM(sceneId, pathImgIn, pathCamIn, pathCamOut):
    '''
    Include the right distortin model in a given PM.
    
    sceneId (str): scene ID text
    pathCamIn (str): input camera path
    pathCamOut (str): ouput camera path
    out:
        0 (int)
    ''' 
    objCamOut=GeomFunc.TSAIin(pathCamIn)
    
    # Update distortion model
    hardwId=sceneId.split('_')[-1]
    SubLogger('CRITICAL', 'Need L1A offset')
    for keyNew, valNew in pipelDFunc.ExtractDisto(hardwId, 'tsai'):
        setattr(objCamOut, keyNew, valNew)

    # Include origin offset (cropped L1A)
    matPPUpdated=np.array([objCamOut.cu, objCamOut.cv])+pipelDFunc.ExtractFrameOffset(pathImgIn)*objCamOut.pitch
    setattr(objCamOut, 'cu', matPPUpdated[0])
    setattr(objCamOut, 'cv', matPPUpdated[1])
    objCamOut.UpdateTsai()
    
    with open(pathCamOut, 'w') as fileOut:
        fileOut.writelines(objCamOut.__write__())

    return 0

def PnP_OCV(sceneId, pathRpcIn, pathCamOut):
    '''
    Run a spatial resection approximating the input RPC.
    It is based on solvePnP function from OpenCV.

    sceneId (str): scene ID text
    pathRpcIn (str): RPC path
    pathCamOut (str): ouput camera path
    out:
        0 (int)
    '''
    # Create objects
    objRpcIn=GeomFunc.RPCin(pathRpcIn)
    objRpcIn.Comput_InvRPC()

    emptyCam={'fu': camFocal,
              'fv': camFocal,
              'cu': objRpcIn.sampOffset*camPitch,
              'cv': objRpcIn.lineOffset*camPitch,
              'pitch': camPitch,
              'distoType': 'NULL'}
    objCamOut=GeomFunc.TSAIin(emptyCam)
    
    # Update distortion model
    for keyNew, valNew in pipelDFunc.ExtractDisto(sceneId, 'tsai', rpcPath=pathRpcIn):
        setattr(objCamOut, keyNew, valNew)
    
    setattr(objCamOut, 'matK', np.array([[objCamOut.fu, 0           , objCamOut.cu   ],
                                         [0           , objCamOut.fv, objCamOut.cv   ],
                                         [0           , 0           , objCamOut.pitch]])/objCamOut.pitch)

    # Point pairs, # grid from image
    meshRange=np.meshgrid(np.linspace(-1.0, 1.0, num=11), # x
                          np.linspace(-1.0, 1.0, num=11), # y
                          np.linspace(-0.2, 0.2, num=11)) # H
    matPtsImg_d=np.vstack((meshRange[0].flatten(), meshRange[1].flatten())).T*objRpcIn.Scale(d=2)+objRpcIn.Offset(d=2)
    matPtsH=meshRange[2].reshape(-1,1)*objRpcIn.heiScale+objRpcIn.heiOffset
    matPtsGeo=objRpcIn.Img2Obj_Z(matPtsImg_d,matPtsH)
    matPtsCart=GeomFunc.Geo2Cart_Elli(matPtsGeo)
    nbPts=matPtsCart.shape[0]

    matDisto=np.array([objCamOut.k1, objCamOut.k2, 0, 0])
    checkPnP, vectR, vectT=cv.solvePnP(matPtsCart, matPtsImg_d, objCamOut.matK, matDisto, flags=cv.SOLVEPNP_EPNP)
    if not checkPnP: SubLogger('CRITICAL', 'PnP (SRS) failed')
    
    # Old scipy version on planet_common
    #from scipy.spatial.transform import Rotation as R
    #matR=R.from_rotvec(vectR.flatten()).as_matrix()
    matR=expm(np.cross(np.eye(3), vectR.flatten()))
    
    # Update camera
    setattr(objCamOut, 'R', matR.T.flatten())
    setattr(objCamOut, 'C', (-matR.T@vectT).flatten())
    objCamOut.UpdateTsai()

    # Projection control
    if 0:
        ptGeo=matPtsGeo[[0,-1], :]
        print('\nPts Geo:')
        print(ptGeo)
        print('RPC:')
        print(np.round(objRpcIn.Obj2Img(ptGeo), 1))
        
        ptCart=matPtsCart[[0, -1], :]
        ptImg_h=(objCamOut.matP@np.append(ptCart, np.ones([2,1]), axis=1).T).T
        ptImg=ptImg_h[:,:2]/ptImg_h[:,[2]]
        ptImg_d=objCamOut.ApplyDisto('add', ptImg)
        print('PM:')
        print(np.round(ptImg_d, 1))

        print('||Centre||:')
        print(norm(objCamOut.C))
        sys.exit()
    
    with open(pathCamOut, 'w') as fileOut:
        fileOut.writelines(objCamOut.__write__())

    return 0

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

def CopyPrevBA(prefIn, prefOut, dirExists=True, img=True, kp='match', dispExists=False):
    '''
    Copy BA files (stats and matches) from a folder to another.
    It is used to propagate bundle adjsutment.

    prefIn (str): path prefix input
    prefOut (str): path prefix output
    kp ('match'|'clean'|'disp'|'none'): copy key point behaviour (default: match)
    out:
        out (int): created folder (0) | error (1,2,3,4)
    '''
    if not kp in ('match', 'clean', 'disp', 'none'): SubLogger('CRITICAL', 'KP copy mode unknown')
    
    dirOut=os.path.dirname(prefOut)
    if dirExists:
        if os.path.exists(dirOut):  
            SubLogger('ERROR', '%s folder already exists'% os.path.basename(prefOut))
            return 1
        else:
            os.mkdir(dirOut)
    
    if dispExists and not os.path.exists(prefIn+'-D.tif'): return 2
    
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
        return 3
    
    lstPathIn=glob(prefIn+extIn)
    for pathIn in lstPathIn:
        pathOut=pathIn.replace(prefIn,prefOut).replace('-disp','').replace('-clean','').replace('_KP', '_1b')
        if os.path.exists(pathOut): return 4
        cmd='cp %s %s'% (pathIn, pathOut)
        os.system(cmd)

    return 0

def KpCsv2Gcp(pathIn, prefOut, accuXYZ=1, accuI=1, nbPts=-1):
    '''
    Reads a cnet.csv file, changes the point accuracy (ECEF Std Dev),
    saves it to the Ba folder with gcp extention. Useful for BA with 
    GCP but the function does not read DEM Height, it should be 
    forced during the previous BA.
    The ground accuracy in [m] is the same in 3 directions due to ECEF.
    It can be in [°] and [m] with adjusted version but the BA has to 
    include --use-lon-lat-height-gcp-error.
    The point number (per characteristic) select "nbPts" of high points,
    "nbPts" of East points, ...
    Characteristics:
        Lat (+/-)
        Long (+/-)
        Height (+/-)
        Nb obs (+/-)
        random 
    The default nbPts=-1 means all points


    pathIn (str): input cnet path
    prefOut (str): output prefix
    accuXYZ (float): ground accuracy (ECEF Std Dev) [m] (default: 1)
    accuI (float): image accuracy (x, y) [pxl] (default: 1)
    nbPts (int): number of point per characteritsic (default: alls)
    out:
        pathOut (str): path of the new file
    '''
    descGound=('id', 'Lat', 'Long', 'H', 'sigX', 'sigY', 'sigZ')
    lenG=len(descGound)
    descImg=('path', 'x', 'y', 'sigx', 'sigy')
    lenI=len(descImg)
    
    # Read
    with open(pathIn) as fileIn:
        lstIn=[lineCur.strip().split() for lineCur in fileIn.readlines()]
    
    # Update and write
    pathOut=prefOut+'-KP2GCP_XYZ%i_I%i.gcp'% (accuXYZ, accuI)
    fileOut=open(pathOut, 'w')

    
    if nbPts<0: # Select all points
        iPts=range(len(lstIn))

    else: # Point selection from characteristics
        matChara=np.array([lineCur[1:4]+[(len(lineCur)-lenG)//lenI, ] 
                                    for lineCur in lstIn],
                            dtype=float)
        
        iPts=[]
        for iCol in range(matChara.shape[1]):
            # Random selection of extreme values, the limit of extrem values is fixed as 1% of the number of points
            # e.g. 500 points in csv, random selection within the 5 first and 5 last points
            iOfIRandom=np.random.random_integers(0, int(0.01*len(lstIn)), 2*nbPts)
            iSorted=np.argsort(matChara[:,iCol])
            iPts+=list(iSorted[iOfIRandom[:nbPts]])+list(iSorted[-iOfIRandom[nbPts:]])
        
        # And random point selection
        iPts+=list(np.random.random_integers(0, len(lstIn), nbPts))
        
    for iPt in iPts:
        ptIn=lstIn[iPt]
        ptOut=[]
        
        # Ground
        for i in range(lenG):
            if i<4:
                ptOut.append(ptIn[i])
                continue
            else:
                ptOut.append(str(accuXYZ))  
            
        # Image
        nbImg=(len(ptIn)-lenG)//lenI
        for j in range(nbImg):  
            # Image Path
            if not os.path.exists(ptIn[lenG+j*lenI]): 
                SubLogger('CRITICAL', 'Image path does not exists, are you in vagrant ?\n%s'% ptIn[lenG+j*lenI])
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
    return pathOut

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
 