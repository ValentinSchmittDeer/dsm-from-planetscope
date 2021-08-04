#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from glob import glob
import numpy as np
from pprint import pprint
from importlib.util import find_spec
moduleSpec=find_spec('planet_opencv3')
if moduleSpec:
    from planet_opencv3 import cv2 as cv
else:
    import cv2 as cv

from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc.GeomFunc import ObjTsai

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['SubArgs_Camgen', 'SubArgs_ConvertCam', 'SubArgs_BunAdj', 'SingleBandImg', 'CtlCam',  'StereoDescriptor']
SetupLogger(name=__name__)
#SubLogger('ERROR', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def SubArgs_Camgen(pathObj, featCur):
    '''
    Create a dictionary of cam_gen parameters

    pathObj (obj): PathCur clas from VarCur
    featCur (json): current feature desciptor
    out:
        subArgs (list): argument list
    '''
    # Initial file
    idImg=featCur['id']
    pathImgInit=os.path.join(pathObj.pData, pathObj.extFeat.format(idImg))
    if not os.path.exists(pathImgInit): SubLogger('ERROR', 'Initial image file not found, %s'% pathImgInit)

    pathRpcInit=pathImgInit[:-4]+'_RPC.TXT'
    if not os.path.exists(pathRpcInit): SubLogger('ERROR', 'Initial RPC file not found, %s'% pathRpcInit)

    # New file
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    if not os.path.exists(pathImg1B): SingleBandImg(pathImgInit, pathImg1B)
    
    pathTsai=pathObj.nTsai[0].format(pathImg1B.split('.')[0])
    if os.path.exists(pathTsai): return 0

    pathGcp=pathTsai[:-4]+'gcp'
    
    # Arguments
    subArgs=[ pathImg1B,
            '--refine-camera',
            '--reference-dem', pathObj.pDem,
            '--optical-center', camCentre,
            '--focal-length', camFocal,
            '--pixel-pitch', camPitch,
            '-o', pathTsai,
            #'--gcp-file', pathGcp,
            #'--gcp-std', '10',
            '--camera-type', 'pinhole',
            '--input-camera',pathRpcInit,
            '-t', 'rpc'
            ]
    
    return subArgs

def SubArgs_ConvertCam(pathObj, featCur):
    '''
    Create a dictionary of convert_pinhole_model parameters

    pathDic (dict): BlockPathDict result
    featCur (json): current feature desciptor
    out:
        subArgs (list): argument list
    '''
    # Initial files
    idImg=featCur['id']
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    if not os.path.exists(pathImg1B): SubLogger('ERROR', 'Initial image file not found, %s'% pathImg1B)
    
    pathTsai0=pathObj.nTsai[0].format(pathImg1B.split('.')[0])
    if not os.path.exists(pathTsai0): SubLogger('ERROR', 'Initial tsai file not found, %s'% pathTsai0)

    # New files
    pathTsai1=pathObj.nTsai[1].format(pathImg1B.split('.')[0])
    if os.path.exists(pathTsai1): return 0
    
    # Arguments
    subArgs=[ pathImg1B,
            pathTsai0,
            '--output-type', camDist, # distortion model
            # <TsaiLensDistortion|BrownConradyDistortion|RPC (default: TsaiLensDistortion)>
            '--rpc-degree', '2', # RPC degree
            '--sample-spacing', '100', # number of pixel for distortion modeling 
            '-o', pathTsai1,
            ]
    
    return subArgs

class SubArgs_BunAdj:
    '''
    Documentation at the end of the script
    '''
    argsInit=[  ## Basics
                '-t', 'nadirpinhole', # set stereo session pinhole OR nadirpinhole
                '--datum', 'WGS_1984', # set datum
                '--nodata-value', '0', # nodata, do not process <= x
                #'--input-adjustments-prefix', path # initial camera transform
                # : read adjust files with that prefix
                # Caution cannot be coupled with --inline-adj (so no distortion)
                
                ## Key points
                '--min-matches', '10', # min key point pairs
                
                ## Model: 'Any weight set in the model must balance another one (never a single weight)'
                '--disable-pinhole-gcp-init', # do initialise camera from GCP files

                ## Intrinsic imporvement
                
                ## Least square
                
                ## Storage
                #'--report-level', '20',
                '--save-cnet-as-csv', # Save key points in gcp point format
                '--inline-adjustments', # Store result in .tsai, not in adjsut
                ]

    def __init__(self, pathObj, lstImg):
        self.pathDem=pathObj.pDem
        
        # Scenes
        if not type(lstImg)==list or False in [type(pathCur)==str for pathCur in lstImg]: SubLogger('CRITICAL', 'Image list (lstImg) must be a list of path')
        self.nbScene=len(lstImg)
        lstImg.sort()
        self.argsInit+=lstImg
        
        # Stereo
        self.argsInit+=['--overlap-list', pathObj.pStereoLst,] # stereopair file for key point extraction
            #OR
        #self.argsInit+=['--position-filter-dist', 'XXm',] # image couple for key point based on centre distance
        
        # Cameras
        self.lstTsaiName=[pathObj.nTsai[1].format(
                            os.path.basename(pathCur).split('.')[0]
                            ) 
                                for pathCur in lstImg]
        
    def KeyPoints(self, prefIn, prefOut):
        strInd=' '.join([str(i) for i in range(self.nbScene)])
        
        args=self.argsInit.copy()
        if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        args+= [prefIn+nameCur for nameCur in self.lstTsaiName]
        args+=['-o', prefOut]
        args+=[## Key points
                '--ip-detect-method','1', # algo (0=OBA-loG, 1=SIFT, 2=ORB)
                '--ip-per-tile', '1000', # key point number
                '--ip-inlier-factor', '5e-3', # key point creation filtering (x>1/15 -> more points but worse): 
                '--ip-uniqueness-threshold', '0.1', # key point creation filtering (x>0.7 -> more points but less unique)
                '--individually-normalize', # normalisation param per image not global 
                '--epipolar-threshold', '10', # key point matching, Max distance to the epipolar line in camera unit
                '--ip-num-ransac-iterations', '1000', # number of RANSAC iteration 
                '--enable-tri-ip-filter', # filter out key point based on triangulation
                #'--min-triangulation-angle', '0.2', # filtering min angle [°]: KP fails if bad RPC
                #'--forced-triangulation-distance', '450e3', # force distance to the camera if not trian fails: useless
                #'--stop-after-matching', # stop after matching key point: do not provide initial residuals
                #'--heights-from-dem', 'pathDEM', # fix key point height from DSM
                #'--heights-from-dem-weight', '10', # weight of key point height from DSM
                ## Model
                '--fixed-camera-indices', "'%s'"% strInd, # fixed camera i
                #'--robust-threshold', '0.9', # threshold of cost function, focus on large error
                #'--fix-gcp-xyz', # turn GCP to fixed: useless whether fixed-camera-indices in
                #'--max-disp-error', '100', # ??
                ## Least square
                '--num-passes', '2', # iteration number: need one at least to filter out key points
                '--parameter-tolerance', '1e-6', # least square limite 
                ]
        
        return args

    def EO(self, prefIn, prefOut):
        args=self.argsInit.copy()
        lstTsai=glob(prefIn+'*.tsai')
        lstTsai.sort()
        args+= lstTsai
        args+=[## Key points
                '--force-reuse-match-files', # use former match file: using -o prefix
                '--skip-matching', # skip key points creation part if the no match file found: complementary to --overlap-list
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM
                ## Model
                #'--rotation-weight', '0', '--translation-weight', '0', # EO weight (x>0 -> stiffer)
                # OR
                '--camera-weight', '1', # EO weight (x>1 -> stiffer)
                #'--fixed-camera-indices', "'0 1'", # fixed camera i
                #'--fix-gcp-xyz', # turn GCP to fixed
                ## Least square
                #'--robust-threshold', '10', # set cost function threshold
                #'--max-disp-error', '100', # ??
                '--num-passes', '20', # max number of master iterations (after outlier filtering)
                #'--max-iterations', '100', # in non-linear least square (per pass)  
                #'--remove-outliers-params', "‘75.0 3.0 2.0 3.0’" # outlier filtering param
                # OR
                #'--remove-outliers-by-disparity-params', '70' # outlier filtering param
                # OR
                #'--elevation-limit', 'min', 'max' # outlier filtering param
                ]
        args+=['-o', prefOut]
        
        return args

    def IO(self, prefIn, prefOut):
        args=self.argsInit.copy()
        lstTsai= glob(prefIn+'*.tsai')
        lstTsai.sort()
        args+= lstTsai
        args.append(prefOut+'*.gcp')
        args+=[## Key points
                '--force-reuse-match-files', # use former key points
                '--skip-matching', # skip key points creation part if the no match file found: alternative to --overlap-list
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM
                ## Model
                #'--rotation-weight', '0', '--translation-weight', '0', # EO weight (x>0 -> stiffer)
                # OR
                #'--camera-weight', '1', # EO weight (x>1 -> stiffer)
                #'--fixed-camera-indices', "'%s'"% ' '.join(lstInd), # fixed camera i
                ## Intrinsic imporvement
                '--solve-intrinsics', # include IO in BA (default=False) 
                #'--intrinsics-to-float', "'focal_length'", # list of IO param to solve
                #'--intrinsics-to-share', "' '", # list of common IO param
                #'--reference-terrain', pathDict['pDem'], # intrinsic imporvement
                #'--reference-terrain-weight' # weight of the DEM in IO resolution (x>1 -> more impact)
                ## Least square
                '--num-passes', '20', # iteration number
                '--parameter-tolerance', '1e-2', # least square limite 
                ]
        args+=['-o', prefOut]
        args.remove('--save-cnet-as-csv')

        return args

    def Full(self, prefIn, prefOut):
        args=self.argsInit.copy()
        if os.path.isdir(prefIn) and not prefIn.endswith('/'): prefIn+='/'
        args+= [prefIn+nameCur for nameCur in self.lstTsaiName]
        args+=['-o', prefOut]
        args+=[## Key points
                '--ip-detect-method','1', # algo (0=OBA-loG, 1=SIFT, 2=ORB)
                '--ip-per-tile', '1000', # key point number
                '--ip-inlier-factor', '5e-3', # key point creation filtering (x>1/15 -> more points but worse): 
                '--ip-uniqueness-threshold', '0.1', # key point creation filtering (x>0.7 -> more points but less unique)
                '--individually-normalize', # normalisation param per image not global 
                '--epipolar-threshold', '10', # key point matching, Max distance to the epipolar line in camera unit
                '--ip-num-ransac-iterations', '1000', # number of RANSAC iteration 
                '--enable-tri-ip-filter', # filter out key point based on triangulation
                '--heights-from-dem', self.pathDem, # fix key point height from DSM
                '--heights-from-dem-weight', '1', # weight of key point height from DSM
                ## Model
                '--camera-weight', '1', # EO weight (x>1 -> stiffer)
                #'--solve-intrinsics', # include IO in BA (default=False) 
                ## Least square
                '--num-passes', '20', # max number of master iterations (after outlier filtering)
                ]
        return args


def SingleBandImg(pathIn, pathOut):
    '''
    Convert all images in the folder to a single band image using the HLS
    colour scpace transformaton.
    openCV tool : cvtColor(src, bwsrc, cv::COLOR_RGB2HLS)
    or 
    matrices average (instead of opencv max-min mean)

    include max StdDev band (for all images) selection with gdal
    include multiproc
    '''
    cmd='gdal_translate -b 2 -q %s %s'% (pathIn, pathOut)
    out=os.system(cmd)
    return out

def CtlCam(pathObj, featCur):
    '''
    Compare centre coordinates to extended MD
    '''
    idImg=featCur['id']
    pathImg1B=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format(idImg))
    pathTsai=pathObj.nTsai[1].format(pathImg1B.split('.')[0])
    if not os.path.exists(pathTsai): SubLogger('ERROR', 'Camera not found %s'% pathTsai)

    camPt=ObjTsai(pathTsai)['matC'].flatten()

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

def StereoDescriptor(pathObj, lstPairs):
    
    # Availability
    grepImg=os.path.join(pathObj.pProcData, pathObj.extFeat1B.format('*'))
    lstImgAvai=[os.path.basename(pathCur) for pathCur in glob(grepImg)]
    lstImgAvai.sort()
    
    extTsaiStr=pathObj.nTsai[1].replace('{}','')
    grepTsai=os.path.join(pathObj.pProcData, pathObj.nTsai[1].format('*'))
    lstTsaiAvai=[os.path.basename(pathCur).replace(extTsaiStr,'.tif') for pathCur in glob(grepTsai)]
    lstTsaiAvai.sort()
    
    # Production Check
    if not len(lstImgAvai)==len(lstTsaiAvai): SubLogger('CRITICAL', 'Not same number of image (%i) and camera (%i) files in %s'% (len(lstImgAvai), len(lstTsaiAvai), pathObj.pProcData))
    if not lstImgAvai==lstTsaiAvai: SubLogger('CRITICAL', 'Not identical image and camera files in %s'% pathObj.pProcData)

    lstOut=[]
    nbComb=len(lstPairs)
    #for i in range(-1,-nbComb-1,-1): # In case of multiimages key points
    for i in range(nbComb):
        comb=lstPairs[i]
        if not comb['properties']['nbScene']==2: continue
        lstSceneCur=[pathObj.extFeat1B.format(scenId) for scenId in comb['properties']['scenes'].split(';')]
        if False in [sceneName in lstImgAvai for sceneName in lstSceneCur]: continue
        
        lstScenePath=[os.path.join(pathObj.pProcData,sceneName) for sceneName in lstSceneCur]
        lstOut.append(' '.join(lstScenePath)+'\n')
    
    if not lstOut: SubLogger('CRITICAL', 'stereo list is empty, no scene is available')
    with open(pathObj.pStereoLst, 'w') as fileOut:
                    fileOut.writelines(lstOut)
    return 0

def CopyPrevBA(prefIn, prefOut, gcp=False):
    '''
    
    prefIn (str): path prefix input
    prefOut (str): path prefix output
    out:
        0: folder creation
        OR
        1: skip 
    '''
    
    dirOut=os.path.dirname(prefOut)
    if os.path.exists(dirOut): 
        SubLogger('WARNING', '%s folder already exists (skipped)'% os.path.basename(prefOut))
        return 0
    os.mkdir(dirOut)

    # Copy tif
    for pathCur in glob(prefIn+'*.tif'):
        cmd='cp %s %s'% (pathCur, pathCur.replace(prefIn,prefOut))
        os.system(cmd)

    # Copy match
    for pathCur in glob(prefIn+'*-clean.match'):
        cmd='cp %s %s'% (pathCur, pathCur.replace(prefIn,prefOut).replace('-clean',''))
        os.system(cmd)
    
    # Copy Gcp
    if gcp:
        pathIn=prefIn+'-cnet.csv'
        name=os.path.basename(pathIn).replace('csv', 'gcp')
        cmd='cp %s %s'% (pathIn, prefOut+'-'+name)
        os.system(cmd)
        
    return 1

def ExportCam(prefIn, prefOut):

    from ASfM import nameTsai1, nameTsai2
    extTsai1=nameTsai1.replace('{}', '')
    extTsai2=nameTsai2.replace('{}', '')
    if os.path.isdir(prefOut) and not prefOut.endswith('/'): prefOut+='/'
    
    for pathCur in glob(prefIn+'*'+extTsai1):
        nameOut=os.path.basename(pathCur).strip('KPEIO-').replace(extTsai1,extTsai2)
        pathOut=prefOut+nameOut
        cmd='cp %s %s'% (pathCur, pathOut)
        os.system(cmd)

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
        if not os.path.exists(pathIn): SubLogger('ERROR', '%s file not found'% nameCur)
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