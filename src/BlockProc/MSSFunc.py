#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from math import pi, sin, cos, ceil, floor
from copy import copy
from glob import glob
import numpy as np
from numpy.linalg import norm, inv, det, matrix_rank
from scipy.signal import gaussian
import rasterio
from shapely.geometry import Polygon
import pyproj
from pprint import pprint


from importlib.util import find_spec
checkPlanetCommon=find_spec('planet_opencv3') is not None
if checkPlanetCommon:
    from planet_opencv3 import cv2 as cv
else:
    import cv2 as cv

from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc import GeomFunc, DockerLibs

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['ReprojGeom', 'FilterDmProces', 'EpipPreProc', 'SubArgs_Stereo', 'MergeDisparities', 'SubArgs_P2D', 'SubArgs_P2L', 'BRratio', 'AspPc2Txt', 'PdalJson', 'PC_Summary', 'FilterTiles', 'PC2Raster']
SetupLogger(name=__name__)
#SubLogger('ERROR', 'Hello')

gdTrans='gdal_translate'
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def ReprojGeom(featIn, epsgOut):
    '''
    Reproject feature geometry with pyproj.

    featIn (json): input feature with 'properties', 'geometry', etc.
    epsgOut (str): destination EPSG code
    out:
        featIn (json): updated feature
    '''
    coordIn=np.array(featIn['geometry']['coordinates']).reshape(-1,2)
    coordsLong, coordsLat=coordIn.T

    wgs84=pyproj.Proj(init='epsg:4326')
    utm=pyproj.Proj(init='epsg:%s'% epsgOut)
    coordsX, coordsY = pyproj.transform(wgs84, utm, coordsLong, coordsLat)
    
    coordOut=np.append(coordsX[:,np.newaxis], coordsY[:,np.newaxis], axis=1)[np.newaxis,np.newaxis,:,:]
    featIn['geometry']['coordinates']=coordOut.tolist()

    return featIn

def FilterDmProces(lstFeat, coupleCur, pathPC, formTsai, geomAoi):              
    '''
    Filter stereo pair dense matching list.

    lstFeat (lst): list of feature (json)
    coupleCur (json): stereo pair feature
    pathPC (str): destination path for "_pc.tif"
    formTsai (str): standard name of Tsai file
    geomAoi (json): 'geometry' part of the AOI feature
    out:
        run (bool): False=skip that stereo pair
    '''
    # Exists
    if os.path.exists(pathPC): 
        
        # Binary file
        fileEncode=os.popen('file --mime-encoding %s'% pathPC).read()
        if fileEncode.strip().split(':')[-1]==' binary': 
            return False
        else:
            return False
            pass

    # Stereo pair
    if coupleCur['properties']['nbScene']>2: return False
    lstId=sorted(coupleCur['properties']['scenes'].split(';'))

    # Ascending/Descending
    lstSatAz=[lstFeat[i]['properties']['sat:satellite_azimuth_mean_deg'] 
                    for i in range(len(lstFeat)) 
                            if lstFeat[i]['id'] in lstId and 
                                    'sat:satellite_azimuth_mean_deg' in lstFeat[i]['properties']]

    if len(lstSatAz)==2:
        lstSatAzDiff=[[abs(az-azRef)//satAz_Tol for azRef in satAz_Val] for az in lstSatAz]
        if not all([0 in tup for tup in lstSatAzDiff]): raise RuntimeError('Input satellite azimut not interpreted (stereopair %i): %s (+/-%i)'% (j, str(lstSatAz), satAz_Tol))
        setSatOri=set([satAz_Name[tup.index(0)] for tup in lstSatAzDiff])
        
        if not len(setSatOri)==1: return False
        #if 'ascending' in setSatOri: return False

    # Geometry size
    polyAoi=Polygon(np.array(geomAoi['coordinates']).reshape(-1,2).tolist())
    polyPair=Polygon(np.array(coupleCur['geometry']['coordinates']).reshape(-1,2).tolist())
    if not polyPair.intersects(polyAoi): return False
    if polyPair.intersection(polyAoi).area<tolPairArea: return False

    # Epipolar angle
    if not all([os.path.exists(formTsai.format(idImg)) for idImg in lstId]): return False
    lstCamIn=[GeomFunc.TSAIin(formTsai.format(idImg)) for idImg in lstId]
    epipXaxis=(lstCamIn[1].vectX0-lstCamIn[0].vectX0).flatten()
    epipXaxis*=1/norm(epipXaxis)
    epipZaxis=0.5*(lstCamIn[0].matR[-1, :]+lstCamIn[1].matR[-1, :])
    epipZaxis*=1/norm(epipZaxis)
    
    axisAngle=np.arccos(np.abs(np.vdot(epipXaxis, epipZaxis)))*180/pi
    if round(axisAngle)<tolAxisAngle: return False

    return True

def EpipPreProc(lstIn, geomIn, pathDem, prefOut, epip=False, geomAoi=None):
    '''
    Packed function for dense matching preparation. It can create 
    epipolar images or simply enhanced images (radiometry).
    
    lstIn (list): list of i, scene and camera path (in tuples)
    geomIn (json): overlap footprint as geojson['geometry'] object
    prefOut (str): output prefix
    epip (bool): create an epipolar image if True
    aoi (json): Json feature of the region of interest to mask it in the image
    out:
        0 (int): 
    '''
    margin=20
    with os.popen("awk '/MemAvailable/ {print $0}' /proc/meminfo") as meminfo:
        cmdOut=meminfo.read().split()
        dicFact={'kB': 1024, 'B':1, 'MB': 1024**2, 'GB': 1024**3}
        sizeFreeMem=int(cmdOut[1])*dicFact[cmdOut[2]]

    def _PrepaRadioImg(i):
        lstImg[i]=lstImg[i].astype(np.float32, copy=False)

        ## Copy kernel
        #kernShape=11
        #kernMid=int(kernShape//2)
        #kernCopy=np.zeros([kernShape, kernShape], dtype=np.float32)
        #kernCopy[kernMid, kernMid]=1
        ## DoG kernel
        #gaussSig=3
        #matGausOut=cv.getGaussianKernel(  kernShape, gaussSig)
        #matGausOut*=1/matGausOut.sum()
        #matGausIn=cv.getGaussianKernel(  kernShape, gaussSig*1.6)
        #matGausIn*=1/matGausIn.sum()
        #kernDoG=2*(np.outer(matGausOut, matGausOut)-np.outer(matGausIn, matGausIn))
        ## Convolution
        #kernFull=(kernCopy+kernDoG)
        #cv.filter2D(src=lstImg[i], 
        #           ddepth=-1, 
        #           kernel=kernFull,
        #           dst=lstImg[i])

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
        
        np.clip(lstImg[i], 0, None, out=lstImg[i])

        # Mask AOI
        if not geomAoi is None:
            lstImg[i]=GeomFunc.MaskedImg(  lstImg[i],
                                        lstCamIn[i], 
                                        pathDem, 
                                        geomAoi,
                                        buffer=margin*3)
            
            lstMask[i]=GeomFunc.MaskedImg( lstMask[i],
                                       lstCamIn[i], 
                                       pathDem, 
                                       geomAoi,
                                       buffer=margin*3)
        # Mask overlap area
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
        # Epipolar parameters
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
        
        return vectOff, vectSize

    if not len(lstIn)==2: SubLogger('CRITICAL', 'lstIn must be of length 2 (stereo pair)')
    if not os.path.exists(os.path.dirname(prefOut)): os.mkdir(os.path.dirname(prefOut))
    #if glob(prefOut+'-*'): os.system('rm -f %s'% (prefOut+'*'))

    nameASP=(('-L.tif', '-L.tsai', '-lMask.tif', '-L_sub.tif', '-lMask_sub.tif'),
             ('-R.tif', '-R.tsai', '-rMask.tif', '-R_sub.tif', '-rMask_sub.tif'))

    lstImg=[cv.imread(lstIn[i][0], cv.IMREAD_GRAYSCALE+(-1)) for i in range(2)]
    lstMask=[np.ones(img.shape, dtype=bool) for img in lstImg]
    lstCamIn=[GeomFunc.TSAIin(lstIn[i][1]) for i in range(2)]

    # Epipolar 
    if epip:
        epipXaxis=(lstCamIn[1].vectX0-lstCamIn[0].vectX0).flatten()
        f=norm(epipXaxis)
        epipXaxis*=1/norm(epipXaxis)
        epipZaxis=0.5*(lstCamIn[0].matR[-1, :]+lstCamIn[1].matR[-1, :])
        epipZaxis*=1/norm(epipZaxis)
        
        axisAngle=np.arccos(np.abs(np.vdot(epipXaxis, epipZaxis)))*180/pi
        if round(axisAngle)<tolAxisAngle:
            SubLogger('ERROR', 'Axis angle smaller than %i°: %2f'% (tolAxisAngle, axisAngle))
            return 1

        r1=epipXaxis
        r2=np.cross(epipZaxis, epipXaxis)
        r3=np.cross(r1, r2)
        epipR=np.vstack((r1/norm(r1), 
                         r2/norm(r2), 
                         r3/norm(r3)))
        
        epipPP_pxl=np.mean((lstMask[0].shape, lstMask[1].shape), axis=0)[[1,0]] /2
        
        lstCamOut=[_PrepaEpipCam(i) for i in range(2)]
        
        epipOff, epipSize=EpipFrameParam()
        if epipSize[0]*epipSize[1]*32>sizeFreeMem/2:
            SubLogger('ERROR', 'Epipolar image too large: %.2f GB'% (epipSize[0]*epipSize[1]*32/1024**3))
            return 1
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
    '''
    Create a list of stereo parameters.

    lstPath (list of list): list (2 items) with list (2 items) of image and tsai path
    prefOut (str): output prefix
    epip (bool): apply an epipolar transformation
    out:
        subArgs (list): list of parameters
    '''
    # Arguments
    subArgs=['-t', 'nadirpinhole', # mode
             #'--entry-point', '1', # starting point 1:Preprocessing, 2:Disparity, 3:Blend, 4:Sub-pixel Refinement, 5:Outlier Rejection and Hole Filling, 6:Triangulation
             #'--stop-point', '1', # Stop the stereo pipeline 
             '--nodata-value', '0',
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
             '--ip-detect-method', '0', # key point algorithm 0:OBAlgG, 1:SIFT, 2:ORB (case of alignement method)
             '--disable-tri-ip-filter', '1', # disable the triangulation filtering
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

def MergeDisparities(prefLeft, prefRight, gdalDock):
    '''
    Scope for disparity image merge (and filter). The current version
    runs with OpenCV functions but it heavy and unstable (for large images).
    A version with GDAL (C++) may be lighter (not finished).

    prefLeft (str): left disparity prefix
    prefRight (str): right disparity prefix
    gdalDock (class): python interface for gdal command
    out:
        pathDispLeft (str): left diparity path (updated file)
    '''
    def Merge_OpenCV(pathLeft, pathRight, imgLeft):
        imgRight= cv.imread(pathRight, cv.IMREAD_LOAD_GDAL)
        if imgRight is None: 
            SubLogger('ERROR', 'Cannot read right disparity image')
            return False
        if not imgLeft.shape==imgRight.shape: 
            SubLogger('ERROR', 'Disparities images with different size: %s VS %s'% (str(imgLeft.shape), str(imgRight.shape)))
            return False
        r,c,b=imgLeft.shape
        
        # Right image shift
        medLeft, medRight=np.median(imgLeft[imgLeft[:,:,0]==1,2]), np.median(imgRight[imgRight[:,:,0]==1,2])
        if floor(abs(medLeft+medRight))//2: 
            SubLogger('ERROR', 'Disparitiy median above 1 pixels: %.2f'% (medLeft+medRight))
            return False
        shift=int(round(0.5*(medLeft-medRight)))
        if shift<0:
            imgRight=np.append(np.zeros([r,-shift,b], dtype=np.float32), imgRight[:,:shift,:], axis=1)
        else:
            SubLogger('WARNING', 'Positive disparitiy case, please check it')
            imgRight=np.append(imgRight[:,shift:,:], np.zeros([r,shift,b], dtype=np.float32), axis=1)
        
        # Disparity mask
        matOut=np.repeat((imgLeft[:,:,0]*imgRight[:,:,0])[:,:,np.newaxis], 3, axis=2).astype(np.float32)
        # Disparity mean
        matOut[:,:,1:]*=0.5*(imgLeft[:,:,1:]-imgRight[:,:,1:])
        # Disparitiy difference (filtered out)
        threshDispI=np.abs(norm(imgLeft[:,:,1:]+imgRight[:,:,1:], axis=2))>tolDispDiff
        matOut[threshDispI,:]=np.zeros(3)
        
        if os.path.exists(pathLeft): os.remove(pathLeft)
        cv.imwrite(pathLeft.replace('.tif','.exr'), matOut.astype(np.float32), [cv.IMWRITE_EXR_TYPE, cv.IMWRITE_EXR_TYPE_FLOAT])

        return pathLeft
    
    def Merge_GDAL(pathLeft, pathRight):
        SubLogger('ERROR', 'Cannot read large disparity images, need Merge_GDAL() function')
        return False
        gdal=DockerLibs.GdalPython()

        dirTilesLeft=pathLeft.replace('.tif', '_Tiles')
        os.mkdir(dirTilesLeft)
        gdal.gdal_retile(['-ps 4000 %i'%  lstNbPix[1],'-targetDir', dirTilesLeft, pathLeft])

        dirTilesRight=pathRight.replace('.tif', '_Tiles')
        os.mkdir(dirTilesRight)
        gdal.gdal_retile(['-ps 4000 %i'%  lstNbPix[1],'-targetDir', dirTilesRight, pathRight])

        lstPathLeft=sorted(glob(os.path.join(dirTilesLeft, '*')))
        n=len(lstPathLeft)
        if not len(glob(os.path.join(dirTilesRight, '*')))==n:
            SubLogger('ERROR', 'Disparities images with different size')
            return False

        # Mean disparity
        for i in range(n):
            pathLeftT=lstPathLeft[i]
            pathRightT=pathLeftT.replace('Left', 'Right')
            print(pathLeftT, pathRightT)

            sys.exit()
        return pathLeft

    extFiltered='-F.tif'
    pathDispLeft=prefLeft+extFiltered
    pathDispRight=prefRight+extFiltered
    if not os.path.exists(pathDispLeft) or not os.path.exists(pathDispRight): 
        SubLogger('CRITICAL', 'Disparities images not found (Left, Right): %s, %s'% (os.path.exists(pathDispLeft), os.path.exists(pathDispRight)))
        return False

    readCheck, lstMat = cv.imreadmulti(   pathDispLeft, [], cv.IMREAD_LOAD_GDAL)
    if readCheck: 
        pathDispLeft=Merge_OpenCV(pathDispLeft, pathDispRight, lstMat[0])
    else:
        pathDispLeft=Merge_GDAL(pathDispLeft, pathDispRight)
    
    if pathDispLeft:
        gdalDock.gdal_translate(['-if', '"EXR"', pathDispLeft.replace('.tif','.exr'), pathDispLeft])
    return pathDispLeft
 
def SubArgs_P2D(pathPCIn, epsgCur):
    '''
    Create a list of point2dem parameters.

    pathPCIn (str): _PC.tif path
    epsgCur (str): output EPSG code
    out:
        subArgs (list): parameters list
    '''
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
    '''
    Create a list of point2las parameters.

    pathPCIn (str): _PC.tif path
    epsgCur (str): output EPSG code
    out:
        subArgs (list): parameters list
    '''
    # Arguments
    subArgs=['--datum', 'WGS84', 
            '--t_srs', 'EPSG:%s'% str(epsgCur), 
            pathPCIn,
            '-o', pathPCIn.replace('.tif','')
            ]
    return subArgs

def BRratio(path1, path2, atype=False):
    '''
    Compute B/H ratio from camera file and return the incidence angle

    path1 (str): camera file 1
    path2 (str): camera file 2
    atype ([False]|'deg'|'rad'): angle type selection
    out:
        bh (float): B/H ratio
    '''
    objCam1=GeomFunc.TSAIin(path1)
    objCam2=GeomFunc.TSAIin(path2)

    matCentres=np.append(objCam1.vectX0.T, objCam2.vectX0.T, axis=0)

    base=norm(np.diff(matCentres, axis=0))
    matCentresGeo=GeomFunc.Cart2Geo_Elli(matCentres)
    height=np.mean(matCentresGeo, axis=0)[2]
    angleInci=2*np.arctan(base/height/2)

    if atype=='deg':
        return angleInci*180/pi
    elif atype=='rad':
        return angleInci
    elif not atype:
        return base/height
    else:
        SubLogger('CRITICAL', 'Unknown atype (angle type): %s'% atype)

def AspPc2Txt(pathIn):
    '''
    Convert -PC.tif (ASP format) into a .las point cloud in geopgarphic 
    coordinates. It includes 'intersection error'*100 [m*100] as "Intensity"

    pathIn (str): -PC.tif path
    out:
        0 (int): done

    '''
    pathTxt=pathIn.replace('.tif', '.txt')
    
    with rasterio.open(pathIn) as imgIn:
        tagsCur=imgIn.tags()
        if not 'POINT_OFFSET' in tagsCur: return 1

        matOffset=np.array([float(off) for off in tagsCur['POINT_OFFSET'].split()])
        matPtsFull=imgIn.read().reshape(4,-1).T
          
    # logical OR on (x, y, z)
    maskPts=np.bool_(np.sum(np.abs(matPtsFull), axis=1))
    matPtsCart=matPtsFull[maskPts]
    del matPtsFull
    
    nbPts=matPtsCart.shape[0]
    
    # X=dX+Ox, Y=dY+Oy, Z=dZ+Oz, Intensity=e*1000
    matPtsCart+=np.append(matOffset, [0])
    matPtsCart[:,3]*=1000
    
    fileOut=open(pathTxt, 'w')
    fileOut.write('X Y Z Intensity\n')
    for i in range(matPtsCart.shape[0]):
        fileOut.writelines(' '.join(matPtsCart[i].astype(str))+'\n')
    fileOut.close()

    return pathTxt

def PdalJson(pathObj):
    '''
    Create PDAL pipeline jsone files.
    
    pathObj (obj): PathCur class from VarCur
    out:
        0
    '''
    # Add stereopair ID
    with open(pathObj.pJsonSource, 'w') as fileOut:
        fileOut.writelines(json.dumps({"pipeline": 
                                        [{  
                                            "type":"readers.text",
                                            "filename":"PathIn.txt",
                                            "override_srs": "EPSG:4978"
                                            },
                                        {   
                                            "type":"filters.reprojection",
                                            "out_srs":"EPSG:0"},
                                        {   
                                            "type": "filters.ferry",
                                            "dimensions": [ "=>PointSourceId",
                                                            "=>ScanAngleRank"]
                                        },
                                        {   
                                            "type":"filters.assign",
                                            "tag": "source",
                                            "value" : "PointSourceId= 0"
                                            },
                                        {   
                                            "type":"filters.assign",
                                            "tag": "angle",
                                            "value" : "ScanAngleRank= 0"
                                            },
                                        "PathOut.las",
                                        ]
                                    }, indent=2))
    # Filtering
    with open(pathObj.pJsonFilter, 'w') as fileOut:
        fileOut.writelines(json.dumps({"pipeline": 
                                        ["PathIn.las",
                                        {
                                          "type":"filters.elm",
                                          #"threshold":"2.0",
                                        },
                                        {
                                          "type":"filters.outlier"
                                        },
                                        #{
                                        #    "type":"filters.smrf"
                                        #},
                                        "PathOut.las"
                                        ]
                                    }, indent=2))

    # Weighted average
    # e_Z [m] = sig_Z^2 = e_H [m] / a [rad] = e_H [mm] / a [°] * 180/(pi*1000)
    # w = sig_Z^{-2} = a [°] / e_H [mm] * pi*1000/180
    # e_H [mm] = Intensity + 1000 to avoid over weighting and /0
    # pipeline process uses Intensity as uint16, so not /1000
    strWeight='ScanAngleRank/(Intensity+1000)*%.6f'% (pi/180*1000**2) # w = sig_Z^{-2} = e_Z^{-1} [m]
    srtRadius=str(gsdOrth*2**0.5/2) # half gsdOrth diagonal (circumcircle of original GSD)
    with open(pathObj.pJsonRast_WA, 'w') as fileOut:
        fileOut.writelines(json.dumps({"pipeline": 
                                        ["PathIn.las",
                                        {
                                            "type":"filters.range",
                                            "limits":"Classification[0:0]"
                                        },
                                        {
                                            "tag": "ImgCount",
                                            "type": "writers.gdal",
                                            "filename": "PathOut.tif",
                                            "gdaldriver": "GTiff",
                                            "data_type": "float32",
                                            "output_type": "count",
                                            "dimension": "Z",
                                            "radius": srtRadius,
                                            "resolution": str(gsdDsm),
                                            "nodata": "-32767",
                                            "origin_x": "0",
                                            "origin_y": "0",
                                            "width": str(1000//gsdDsm),
                                            "height": str(1000//gsdDsm),
                                        },
                                        {
                                            "tag": "ImgStdev",
                                            "type": "writers.gdal",
                                            "filename": "PathOut.tif",
                                            "gdaldriver": "GTiff",
                                            "data_type": "float32",
                                            "output_type": "stdev",
                                            "dimension": "Z",
                                            "radius": srtRadius,
                                            "resolution": str(gsdDsm),
                                            "nodata": "-32767",
                                            "origin_x": "0",
                                            "origin_y": "0",
                                            "width": str(1000//gsdDsm),
                                            "height": str(1000//gsdDsm),
                                        },
                                        {   
                                            "type":"filters.assign",
                                            "value" : "Intensity=%s"% strWeight
                                            },
                                        {
                                            "tag": "ImgW",
                                            "type": "writers.gdal",
                                            "filename": "PathOut.tif",
                                            "gdaldriver": "GTiff",
                                            "data_type": "float32",
                                            "output_type": "mean",
                                            #"power": "0.5",
                                            "dimension": "Intensity",
                                            "radius": srtRadius,
                                            "resolution": str(gsdDsm),
                                            "nodata": "-32767",
                                            "origin_x": "0",
                                            "origin_y": "0",
                                            "width": str(1000//gsdDsm),
                                            "height": str(1000//gsdDsm),
                                        },
                                        {   
                                            "type":"filters.assign",
                                            "value" : "Z=Z*Intensity"
                                            },
                                        {
                                            "tag": "ImgWZ",
                                            "type": "writers.gdal",
                                            "filename": "PathOut.tif",
                                            "gdaldriver": "GTiff",
                                            "data_type": "float32",
                                            "output_type": "mean",
                                            #"power": "0.5",
                                            "dimension": "Z",
                                            "radius": srtRadius,
                                            "resolution": str(gsdDsm),
                                            "nodata": "-32767",
                                            "origin_x": "0",
                                            "origin_y": "0",
                                            "width": str(1000//gsdDsm),
                                            "height": str(1000//gsdDsm),
                                        },
                                        ]
                                    }, indent=2))

    return 0

def PC_Summary(lstPath, lstEmpty, lstBoundsCur, nb, pathTxt):
    '''
    Print out point cloud summary and write it down. If the file
    already exists and it is the same, it return a True checkMerged.

    lstPath (list): list of usable point cloud path
    lstEmpty (list): list of emtpy pont cloud path
    lstBoundsCur (list): 'coordinates' part of AOI feature
    nb (int): number of point in total
    pathTxt (str): point cloud list path
    out:
        checkMerged (bool): True=must be merged (again)
        lstMid (list): middle point coordinates
    '''
    nbFile=len(lstPath)+len(lstEmpty)
    lstMid=np.round(np.mean(np.array(lstBoundsCur).reshape(2,2), axis=0), -3).astype(int).tolist()

    # STDOUT summary
    SubLogger('WARNING', '='*30)
    SubLogger('INFO', '\tFile number (usable/empty)  : %i/%i'% (len(lstPath),len(lstEmpty)))
    SubLogger('INFO', '\tFile percent (usable/empty) : %.1f/%.1f'% (len(lstPath)/nbFile*100,len(lstEmpty)/nbFile*100))
    SubLogger('INFO', '\tPoint number                : %i'% nb)
    SubLogger('INFO', '\tCentre coords [m]           : %i %i'% tuple(lstMid))

    # Record file list
    if os.path.exists(pathTxt):
        with open(pathTxt) as fileIn:
            lstPCmerge=[lineCur.strip() for lineCur in fileIn.readlines()]
        lstPCin=[path in lstPCmerge for path in lstPath]
        checkMerged=all(lstPCin) and len(lstPCin)==len(lstPCmerge)
    else:
        checkMerged=False

    return (checkMerged, lstMid)

def FilterTiles(lstMid, lstTilePath, pathTemplate, featAoi):
    '''
    Filter out outside tile by geometry intersection and 
    rename tiles by replacing indices with top-left 
    coordinates [km].
    
    jsonInfo00 (json): 0_0 tile informations
    lstTilePath (list): tile path list
    pathTemplate (str): tile path template with '#'
    out:
        code (int): process return code sum
    '''
    matOrigin=(np.array(lstMid)*1e-3).astype(int)
    
    geomAoi=Polygon(featAoi['geometry']['coordinates'][0][0])
    cornerTile=np.array([[0,0],[0,1],[1,1],[1,0], [0,0]])

    strTemplate=pathTemplate.split('#')
    code=0
    for pathTile in lstTilePath:
        strIndexIn=pathTile.replace(strTemplate[0],'').replace(strTemplate[1],'')
        indexIn=np.array(strIndexIn.split('_')).astype(int)
        indexOut=matOrigin+indexIn
        geomTile=Polygon((indexOut+cornerTile)*1e3)
        if not geomTile.intersects(geomAoi):
            code+=os.system('rm %s'% pathTile)
            continue

        strIndexOut='_'.join((indexOut+[0,1]).astype(str))
        cmd='mv %s %s'% (pathTile, pathTile.replace(strIndexIn, strIndexOut))
        code+=os.system(cmd)
    
    return code

def PC2Raster(pathIn, pathOut, lstIndex, pathJson, pdalTool):
    '''
    Run PDAL command line for rasterisation and merge all outcoming 
    raster files into 1 final product.

    pathIn (str): point cloud tile path
    pathOut (str): output DSM path
    lstIndex (list): list of tile indices value
    pathJson (str): pipeline json descriptor 
    pdalTool (class): PDAL python interface
    out:
        out (int): cleaning output code 
    '''
    pathJsonCur='.'.join(pathOut.split('.')[:-1])+'.json'
    dicOri={'origin_x': str(lstIndex[0]*1000),
            'origin_y': str((lstIndex[1]-1)*1000)}
    
    # Update pipeline
    with open(pathJson) as fileIn:
        jsonPipline=json.load(fileIn)
    for brick in jsonPipline['pipeline']:
        if not 'type' in brick or not brick['type']=='writers.gdal': continue
        brick.update(dicOri)
    with open(pathJsonCur, 'w') as fileOut:
        fileOut.writelines(json.dumps(jsonPipline, indent=2))

    # ImgCount, ImgStdev, ImgWeight ,ImgWZ
    lstPath=(pathOut.replace('.','_Count.'),
             pathOut.replace('.','_Stdev.'),
             pathOut.replace('.','_W.'),
             pathOut.replace('.','_WZ.'))
    subArgs=[pathJsonCur,
            '--readers.las.filename=%s'% pathIn,
            '--stage.ImgCount.filename=%s'% lstPath[0],
            '--stage.ImgStdev.filename=%s'% lstPath[1],
            '--stage.ImgW.filename=%s'% lstPath[2],
            '--stage.ImgWZ.filename=%s'% lstPath[3]]
    
    pdalTool.pipeline(subArgs)
    
    # Raster combination
    with rasterio.open(lstPath[2]) as imgIn:
        profileImg=imgIn.profile
        matMeanW=imgIn.read(1)
    
    indexNoData=np.where(matMeanW==-32767)
    np.clip(matMeanW, 1, None, out=matMeanW)

    # Update profile
    profileImg['count']=3

    if not (profileImg['width']>0 and profileImg['height']>0 and profileImg['width']*profileImg['height']>0):
        return os.system(cmdClean)
    
    with rasterio.open(pathOut, 'w', **profileImg) as imgOut:
        
        # Count
        with rasterio.open(lstPath[0]) as imgIn:
            matCount=imgIn.read(1)
        # Standard dev
        with rasterio.open(lstPath[1]) as imgIn:
            matStdev=imgIn.read(1)
        # Height
        with rasterio.open(lstPath[3]) as imgIn:
            matMeanWZ=imgIn.read(1)
        
        imgOut.set_band_description(1, 'Height')
        matOut=matMeanWZ/matMeanW
        matOut[indexNoData]=-32767
        imgOut.write(matOut,1)
        imgOut.set_band_description(2, 'Accuracy') 
        matOut=matStdev+np.sqrt(1000/matMeanW/matCount-1)
        matOut[indexNoData]=-32767
        imgOut.write(matOut,2)
        imgOut.set_band_description(3, 'PtCount')
        imgOut.write(matCount,3)
        #imgOut.set_band_description(3, 'Stdev Pts')
        #imgOut.write(matStdev,3)
        #imgOut.set_band_description(4, 'Stdev Intersec')
        #matOut=np.sqrt(1000/matMeanW/matCount-1)
        #matOut[indexNoData]=-32767
        #imgOut.write(matOut,4)
        #imgOut.set_band_description(5, 'Count Pts')
        #imgOut.write(matCount,5)        

    cmdClean='rm %s'% ' '.join(list(lstPath)+[pathJsonCur,])
    return os.system(cmdClean)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        


