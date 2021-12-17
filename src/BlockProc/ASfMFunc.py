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
    imgType ('green'|'hsv'): extraction mode (default: green)
    out:
        process output
    '''
    if imgType=='green':
        cmd='gdal_translate -b 2 -of GTiff -co PROFILE=BASELINE -q %s %s'% (pathIn, pathOut)
        cmd+=' ; rm {0}/*.RPB ; rm {0}/*.tif.aux.xml'.format(os.path.dirname(pathOut))
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

def SubArgs_StereoKP_RPC(pathObj, lstPath, softness=0):
    '''
    Create a list of stereo_pprc parameters for key point extraction per pair

    pathObj (obj): PathCur class from VarCur
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
    
    dirOut=os.path.dirname(pathObj.prefStereoKP)
    
    if os.path.exists(dirOut): os.system('rm -r %s'% dirOut)
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

def SubArgs_Camgen(sceneId, pathImgIn, pathRpcIn, pathDemIn, pathCamOut, pattern='circle'):
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

def RPCwithoutDisto(sceneId, pathRpcIn, pathRpcOut):
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

def ConvertPM(sceneId, pathImgIn, pathCamIn, pathCamOut):
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

def SRS_OCV(sceneId, pathImgIn, pathRpcIn, pathCamOut):
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
    for keyNew, valNew in pipelDFunc.ExtractDisto(sceneId, 'tsai', scenePath=pathImgIn):
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
                #'--report-level', '20',
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
        self.lstTsaiName=[pathObj.nTsai[1].format(idCur) 
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

    def EO_RPC(self, prefIn, prefOut):
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

    def IO_RPC(self, prefIn, prefOut, pathObj, outGraph=False):
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
                #'--heights-from-dem', self.pathDem, # fix key point height from DSM
                #'--heights-from-dem-weight', '0.1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                #'--rotation-weight', '1', 
                #'--translation-weight', '0', # EO weight (x>0 -> stiffer) or
                #'--camera-weight', '100', # EO weight (x>1 -> stiffer)
                ## Least square
                '--remove-outliers-params','"80.0 1.0 2.0 3.0"',
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
                #'--heights-from-dem', self.pathDem, # fix key point height from DSM
                #'--heights-from-dem-weight', '0.1', # weight of key point height from DSM: need a balancing wieght (camera), no need to fix more than 1
                #'--rotation-weight', '1', 
                #'--translation-weight', '0', # EO weight (x>0 -> stiffer)
                '--camera-weight', '10', # EO weight (x>1 -> stiffer)
                ## Intrinsic imporvement
                '--solve-intrinsics', # include IO in BA (default=False) 
                '--intrinsics-to-float', '"optical_center"', # "'focal_length optical_center other_intrinsics' ", # list of IO param to solve
                #'--intrinsics-to-share', '"other_intrinsics"', # "'focal_length optical_center other_intrinsics' ", # list of common IO param
                #'--reference-terrain', self.pathDem, # use a reference terrain to create points for instrinsic adjust: needs disparities map list
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

def CopyPrevBA(prefIn, prefOut, dirExists=True, img=True, kp='match', dispExists=False):
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
        return 1
    
    lstPathIn=glob(prefIn+extIn)
    for pathIn in lstPathIn:
        pathOut=pathIn.replace(prefIn,prefOut).replace('-disp','').replace('-clean','').replace('_KP', '_1b')
        cmd='cp %s %s'% (pathIn, pathOut)
        os.system(cmd)
    
    return 0

def KpCsv2Gcp(pathIn, prefOut, accuXYZ=1, accuI=1, nbPts=0):
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
    The default nbPts=0 means all points


    pathIn (str): input cnet path
    prefOut (str): output prefix
    accuXYZ (float): ground accuracy (ECEF Std Dev) [m] (default: 1)
    accuI (float): image accuracy (x, y) [pxl] (default: 1)
    nbPts (int): number of point per characteritsic (default: 0)
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

    # Point selection from characteristics:
    if not nbPts:
        iPts=range(len(lstIn))
    else:
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

##########################################

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



