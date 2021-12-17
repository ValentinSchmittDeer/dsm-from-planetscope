#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from math import pi, sin, cos, ceil
from copy import copy
from glob import glob
import numpy as np
from numpy.linalg import norm, inv, det, matrix_rank
from scipy.signal import gaussian
import rasterio
from shapely.geometry import Polygon
from pprint import pprint


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
#SubLogger(logging.WARNING, 'jojo')

gdTrans='gdal_translate'
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def GardDEM(pathIn, pathOut):
    fileIn=rasterio.open(pathIn)
    
    if fileIn.dtypes[0]=='float32':
        typeOut=cv.CV_32F
    else:
        SubLogger('CRITICAL', 'Unknown DEM type: %s'% fileIn.dtypes[0])
    
    imgIn = cv.Laplacian(fileIn.read(1), typeOut)
    np.absolute(imgIn, out=imgIn)
    imgOut = cv.GaussianBlur(imgIn, (5, 5), 0)
    imgOut*=1/np.amax(imgOut)

    with rasterio.open(pathOut, 'w', **fileIn.profile) as fileOut:
        fileOut.write(imgOut.astype(np.float32), 1)
    return 0

def PrepProcessDM(lstIn, geomIn, pathDem, prefOut, epip=False):
    '''
    Packed function for dense matching preparation. It can create 
    epipolar images or simply enhanced images (radiometry).
    
    lstIn (list): list of i, scene and camera path (in tuples)
    geomIn (json): overlap footprint as geojson['geometry'] object
    prefOut (str): output prefix
    out:
        0 (int): 
    '''
    margin=20
    with os.popen("awk '/MemFree/ {print $0}' /proc/meminfo") as meminfo:
        cmdOut=meminfo.read().split()
        dicFact={'kB': 1024, 'B':1, 'MB': 1024**2, 'GB': 1024**3}
        sizeFreeMem=int(cmdOut[1])*dicFact[cmdOut[2]]

    def _PrepaRadioImg(i):
        # Copy kernel
        kernShape=11
        kernMid=int(kernShape//2)
        kernCopy=np.zeros([kernShape, kernShape], dtype=np.float32)
        kernCopy[kernMid, kernMid]=1
        # DoG kernel
        matGausOut=cv.getGaussianKernel(  kernShape, 2)
        matGausOut*=1/matGausOut.sum()
        matGausIn=cv.getGaussianKernel(  kernShape, 2*1.6)
        matGausIn*=1/matGausIn.sum()
        kernDoG=2*(np.outer(matGausOut, matGausOut)-np.outer(matGausIn, matGausIn))
        # Laplace kernel
        kernLap=np.zeros(kernDoG.shape, dtype=float)
        kernLap[[kernMid-1, kernMid+1], [kernMid-1, kernMid+1]]=-1
        kernLap[kernMid, kernMid]=4
        
        # Convolution
        kernFull=(kernCopy+kernDoG+kernLap)
        
        lstImg[i]=lstImg[i].astype(np.float32, copy=False)
        cv.filter2D(src=lstImg[i], 
                   ddepth=-1, 
                   kernel=kernFull,
                   dst=lstImg[i])
        np.clip(lstImg[i], 0, None, out=lstImg[i])

        # Enhancement
        imgData=lstImg[i][np.where(lstImg[i]>0)]
        #   Stretch: ax+b
        values, base = np.histogram(imgData, bins=int(np.amax(imgData)-int(np.amin(imgData))))
        cumul_n=np.cumsum(values)/imgData.size
        v99P=base[np.where(cumul_n<0.999)[0][-1]]
        v01P=base[np.where(cumul_n>0.001)[0][0]]
        a=1/float(v99P-v01P)
        b=-a*v01P

        lstImg[i]*=a
        lstImg[i]+=b
        
        # Mask
        lstImg[i]=GeomFunc.MaskedImg(  lstImg[i],
                                    lstCamIn[i], 
                                    pathDem, 
                                    geomIn,
                                    buffer=margin)
        
        lstMask[i]=GeomFunc.MaskedImg( lstMask[i],
                                   lstCamIn[i], 
                                   pathDem, 
                                   geomIn,
                                   buffer=margin)

    def _PrepaEpipCam(i):
        objCam=copy(lstCamIn[i])
        lstAttr=[]
        lstAttr.append(('R', epipR.T.flatten()))

        lstAttr.append(('cu', epipPP_pxl[0]*objCam.pitch))
        lstAttr.append(('cv', epipPP_pxl[1]*objCam.pitch))
    
        lstAttr+=[('distoType', 'NULL'), 'k1', 'k2', 'p1', 'p2']

        for attrNew in lstAttr:
            if type(attrNew)==str:
                delattr(objCam, attrNew)
            else:
                setattr(objCam, attrNew[0], attrNew[1])
    
        objCam.UpdateTsai()
        return objCam

    def _PrepaEpipImg(i):
        # Distortion
        mapx, mapy=cv.initUndistortRectifyMap( lstCamIn[i].matK, 
                                               (lstCamIn[i].k1, lstCamIn[i].k2, lstCamIn[i].p1, lstCamIn[i].p2), 
                                               np.eye(3), 
                                               lstCamIn[i].matK, 
                                               (lstImg[i].shape[1], lstImg[i].shape[0]),
                                               cv.CV_32FC1)
        cv.remap(src=lstImg[i], 
                map1=mapx, 
                map2=mapy, 
                interpolation=cv.INTER_LINEAR,
                dst=lstImg[i])
        
        lstMask[i]=lstMask[i].astype(float, copy=False)
        cv.remap(src=lstMask[i], 
                map1=mapx, 
                map2=mapy, 
                interpolation=cv.INTER_NEAREST,
                dst=lstMask[i])
        lstMask[i]=lstMask[i].astype(bool, copy=False)

        # Epipolar homography
        matT=lstCamOut[i].matP[:3,:3]@inv(lstCamIn[i].matP[:3,:3])
        matTs=epipS@matT

        imgCur=cv.warpPerspective(  src=lstImg[i], 
                                    M=matTs, 
                                    dsize=tuple(epipSize),
                                    )# if cv.WARP_INVERSE_MAP, not 'M=' key
        lstImg[i]=imgCur

        imgCur=cv.warpPerspective(  src=lstMask[i].astype(float), 
                                    M=matTs, 
                                    dsize=tuple(epipSize),
                                    )
        lstMask[i]=imgCur.astype(bool, copy=False)

    def EpipFrameParam():
        matCornTransf=np.zeros([2,4,1,2])
        for i in range(2):
            matT=lstCamOut[i].matP[:3,:3]@inv(lstCamIn[i].matP[:3,:3])

            # (x, y)=(col, row)
            matCornIn=np.array([[(0,0)], # TL
                                [(lstImg[i].shape[1], 0)], # TR
                                [(0, lstImg[i].shape[0])], # BL
                                [(lstImg[i].shape[1], lstImg[i].shape[0])], # BR
                                ], dtype=float)
            matCornIn_u=cv.undistortPoints( matCornIn, 
                                            lstCamIn[i].matK, 
                                            (lstCamIn[i].k1, lstCamIn[i].k2, lstCamIn[i].p1, lstCamIn[i].p2), 
                                            np.eye(3), 
                                            lstCamIn[i].matK)
            matCornTransf[i]=cv.perspectiveTransform(matCornIn_u, matT)
        
        minusMinCornProj=-np.ceil(np.amin(matCornTransf, axis=(2,1,0))).astype(int)
        maxCornProj=np.ceil(np.amax(matCornTransf, axis=(2,1,0))).astype(int)
        vectOff=minusMinCornProj-np.ones(2)
        vectSize=maxCornProj+minusMinCornProj
        
        if vectSize[0]*vectSize[1]*32>sizeFreeMem/2:
            nbPts=len(geomIn['coordinates'][0])
            matPtsTransf=np.zeros([2,nbPts,1,2])
            for i in range(2):
                matT=lstCamOut[i].matP[:3,:3]@inv(lstCamIn[i].matP[:3,:3])

                a, matPtsImg=GeomFunc.MaskedImg(lstMask[i], 
                                                lstCamIn[i], 
                                                pathDem, 
                                                geomIn, 
                                                debug=True)
                del a
                matPtsImg_u=cv.undistortPoints(  matPtsImg.reshape(nbPts,1,2).astype(float), 
                                                lstCamIn[i].matK, 
                                                (lstCamIn[i].k1, lstCamIn[i].k2, lstCamIn[i].p1, lstCamIn[i].p2), 
                                                np.eye(3), 
                                                lstCamIn[i].matK)
                matPtsTransf[i]=cv.perspectiveTransform(matPtsImg_u,
                                                        matT)
            
            minPtsTransf=np.floor(np.amin(matPtsTransf, axis=(2,1,0))).astype(int)
            maxPtsTransf=np.ceil(np.amax(matPtsTransf, axis=(2,1,0))).astype(int)
            offsetPts=-minPtsTransf
            sizePts=maxPtsTransf-minPtsTransf
            # Shrink x dim
            vectOff[0]=offsetPts[0]-margin
            vectSize[0]=sizePts[0]+2*margin
            # Shrink y dim
            vectSize[1]=maxPtsTransf[1]+vectOff[1]+margin

        if vectSize[0]*vectSize[1]*32<sizeFreeMem/2:
            #print('vectOff', vectOff)
            #print('vectSize', vectSize)
            #print('Image weight', vectSize[0]*vectSize[1]*32/1024**3)
            return vectOff, vectSize
        else:
            return False, False

    if not len(lstIn)==2: SubLogger('CRITICAL', 'lstIn must be of length 2 (stereo pair)')
    if not os.path.exists(os.path.dirname(prefOut)): os.mkdir(os.path.dirname(prefOut))
    if glob(prefOut+'-*'): os.system('rm %s'% (prefOut+'*'))

    nameASP=(('-L.tif', '-L.tsai', '-lMask.tif', '-L_sub.tif', '-lMask_sub.tif'),
             ('-R.tif', '-R.tsai', '-rMask.tif', '-R_sub.tif', '-rMask_sub.tif'))

    lstImg=[cv.imread(lstIn[i][0], cv.IMREAD_GRAYSCALE+(-1)) for i in range(2)]
    lstMask=[np.ones(img.shape, dtype=bool) for img in lstImg]
    lstCamIn=[GeomFunc.TSAIin(lstIn[i][1]) for i in range(2)]
    
    # Epipolar 
    if epip:
        epipXaxis=(lstCamIn[1].vectX0-lstCamIn[0].vectX0).flatten()
        epipZaxis=((lstCamIn[1].matR[-1, :]+lstCamIn[0].matR[-1, :])/2).flatten()
        
        r1=epipXaxis/norm(epipXaxis)
        r2=np.cross(epipZaxis, r1)
        r3=np.cross(r1, r2)
        epipR=np.vstack((r1/norm(r1), 
                         r2/norm(r2), 
                         r3/norm(r3)))
        
        epipPP_pxl=np.mean((lstMask[0].shape, lstMask[1].shape), axis=0)[[1,0]] /2
        
        lstCamOut=[_PrepaEpipCam(i) for i in range(2)]
        
        epipOff, epipSize=EpipFrameParam()
        if type(epipOff)==bool and not epipOff: return 1
        # S: Shift
        epipS=np.eye(3)
        epipS[:2, -1]=epipOff
        
        for i in range(2):
            _PrepaEpipImg(i)
            
            vectPP=lstCamOut[i].vectPP+epipOff*lstCamOut[i].pitch
            setattr(lstCamOut[i], 'cu', vectPP[0])
            setattr(lstCamOut[i], 'cv', vectPP[1])
            lstCamOut[i].UpdateTsai()

            with open(prefOut+nameASP[i][1], 'w') as fileOut:
                fileOut.writelines(lstCamOut[i].__write__())

        lstCamIn=lstCamOut

    # Radiometry
    [_PrepaRadioImg(i) for i in range(2)]
    
    # Record
    cmd=''
    for i in range(2):
        cv.imwrite(prefOut+nameASP[i][0], lstImg[i].astype(np.float32))
        cv.imwrite(prefOut+nameASP[i][2], 255*lstMask[i].astype(np.uint8))

        cmd+='{gd} -q -outsize 25% 25% -r average -a_nodata 0 {src} {dst} ; '.format(gd=gdTrans,
                src=prefOut+nameASP[i][0],
                dst=prefOut+nameASP[i][3],)
        cmd+='{gd} -q -outsize 25% 25% -r nearest -a_nodata 0 {src} {dst} ; '.format(gd=gdTrans,
                src=prefOut+nameASP[i][2],
                dst=prefOut+nameASP[i][4],)

    del lstImg
    del lstMask
    del lstCamIn
    os.system(cmd)
    
    return 0

def SubArgs_Stereo(lstPath, prefOut, epip=False):
    # Arguments
    subArgs=['-t', 'nadirpinhole', # mode
             #'-e', '1', # starting point 1:Preprocessing, 2:Disparity, 3:Blend, 4:Sub-pixel Refinement, 5:Outlier Rejection and Hole Filling, 6:Triangulation
             #'--stop-point', '1', # Stop the stereo pipeline 
             ]
    
    ## Preprocessing
    # transformation method affineepipolar|homography|epipolar|none: see "Preparation" in mss_main
    if epip:
        subArgs+=['--alignment-method', 'epipolar',]
    else:
        subArgs+=['--alignment-method', 'none',]
    subArgs+=[#'--alignment-method', 'none', 
             #'--individually-normalize', # image radio normalisation
             #'--ip-per-tile', '1000', # key point extraction number per tile (case of alignement method)
             '--ip-num-ransac-iterations', '1000', 
             '--ip-detect-method', '1', # key point algorithm 0:OBAlgG, 1:SIFT, 2:ORB (case of alignement method)
             '--nodata-value', '0',
             #'--force-reuse-match-files', # # use former match file: ?using -o prefix?
             '--skip-rough-homography', # avoid the datum-based homography 
             #'--ip-debug-images 1', # Print image with key points on: written at process root (in docker)
             ]
    ## Correlation
    subArgs+=[#'--prefilter-mode', '2', # Preprocessing method 
             #'corr-seed-mode', '1', # correltion method
             #'--min-num-ip', '10', # quit the process based on number of key point. 
             #'cost-mode', '2', # # correlation cost function method
             #'--stereo-algorithm', '1', # 1:SGM (needs parallel_stereo), 2:MGM
             #'--corr-tile-size', '6400 ', # Value of --corr-tile-size is 1024 but image size is Vector2(1337,1295).
                 #Increase --corr-tile-size so the entire image fits in one tile, or use parallel_stereo. Not that making --corr-tile-size larger than 9000 or so may cause GDAL to crash.
             #'disparity map initialization' #1:box filter-like accumulator; 2:coarse-to-fine pyramid based; 3:disparity search space into sub-regions with similar values of disparity
             ]
    ## Subpixel Refinement
    subArgs+=[#'--subpixel-mode', '1' # subprixel function fitted
             #'--phase-subpixel-accuracy', '20' # max pixel division denominator (1/x)
             ]
    ## Filtering
    subArgs+=[#'--filter-mode', '1' # filtering mode 
             ## Triangulation
             #'--universe-center', 'None' # point cloud filtering based on distance to "universe", None|Camera|Zero
             #'--bundle-adjust-prefix', str #
             #'--min-triangulation-angle', '0.0' # angle in ° fullfilled for triangulation
             #'--point-cloud-rounding-error', '0.0' # point cloud rounding value in m, 1/20**10 = 1mm
             #'--compute-error-vector', # Save the error vectore rather than just its legnth, Stored in -PC
            ]
    subArgs+=[pathImg for pathImg, pathCam in lstPath]
    subArgs+=[pathCam for pathImg, pathCam in lstPath]
    subArgs.append(prefOut)

    return subArgs

def SubArgs_P2D(pathPCIn, epsgCur):
    # Arguments
    subArgs=['--transverse-mercator',
            '--nodata-value', '-32767',
            '--t_srs', 'EPSG:%s'% str(epsgCur),
            ' ', 
            pathPCIn,
            '--dem-spacing', '4',
            ]
    return subArgs

def SubArgs_P2L(pathPCIn, epsgCur):
    # Arguments
    subArgs=['--datum', 'WGS84', 
            '--t_srs', 'EPSG:%s'% str(epsgCur), 
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
        
