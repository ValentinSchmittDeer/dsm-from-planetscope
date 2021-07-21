#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, ProcessStdout
from PVL.PVL_Rpc import *

# dsm_from_planetscope libraries
from SSBP.SSBPlib_block import SceneBlocks
from PCT import *

from MSS.MSSlib_asp import AspUtility as AspObj
from MSS import * 
#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task

**************************************************************************
> Steps
**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        print()
        logger = SetupLogger(name=__title__)
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        #Positional input
        parser.add_argument('-i', required=True, help='Working directory')
        parser.add_argument('-m', required=True, help='Dense matching mode PW|MVS')
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM)')
        
        #Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: [] means all')
        parser.add_argument('-debug',action='store_true',help='Debug mode: avoid planet_common check')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        if not args.m in ('PW', 'MVS'): raise RuntimeError("Unknown mode")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()

        #---------------------------------------------------------------
        # Check planet_common and docker
        #---------------------------------------------------------------
        if not args.debug:
            logger.info('# Check planet_common and docker ')
            if not PCTlib_product.CheckPC(): raise RuntimeError("The script must run in planet_common's env")
            
            asp=AspObj()
        
        #---------------------------------------------------------------
        # Read Repo
        #---------------------------------------------------------------
        logger.info('# Read Repo')
        objBlocks=SceneBlocks([], args.i, 'dir')
        logger.info(objBlocks)
        
        if not args.b:
            lstLoop=range(objBlocks.nbB)
        else:
            lstLoop=[i for i in range(objBlocks.nbB) if objBlocks.lstBId[i][0] in args.b]
        
        for iB in lstLoop:
            bId, nbFeat= objBlocks.lstBId[iB]
            logger.info(bId)
            pathDict=MSSlib_stereo.BlockPathDict(args.i, bId)
            
            
            #---------------------------------------------------------------
            # Dense matching pairwise
            #---------------------------------------------------------------
            if args.m=='PW':
                logger.info('# Dense matching pairwise')

                for i,pairCur in enumerate(objBlocks.lstBCouple[iB]):
                    # Find Image
                    lstImgPath=[]
                    for key in pairCur['properties']:
                        if not key.startswith('scene'): continue
                        nameImg=pairCur['properties'][key]
                        grepImg=os.path.join(pathDict['pProcData'], nameImg+'*.tif')
                        lstImg=glob(grepImg)
                        #if not len(lstImg)==1: raise RuntimeError('Image file not found (or multiple ones): %s'% nameImg)
                        if lstImg:
                            lstImgPath.append(lstImg[0])
                    if not len(lstImgPath)==2: continue
                    
                    # Find the best Tsai
                    lstCamPath=[]
                    for pathImg in lstImgPath:
                        lstCam=glob(pathImg.split('.')[0]+'*.tsai')
                        if not lstCam: raise RuntimeError('Camera file (tsai) not found: %s'% pathImg)
                        lstCam.sort()
                        lstCamPath.append(lstCam[-1],)
                    
                    # Preparation
                    if not os.path.exists(os.path.dirname(pathDict['pDm'])): os.mkdir(os.path.dirname(pathDict['pDm']))
                    tileSize1=MSSlib_stereo.OverlapMask(pairCur,lstImgPath[0],lstCamPath[0], args.dem,pathDict['pDm']+'-lMask.tif')
                    tileSize2=MSSlib_stereo.OverlapMask(pairCur,lstImgPath[1],lstCamPath[1], args.dem,pathDict['pDm']+'-rMask.tif')
                    tileSize=(max(tileSize1[0],tileSize2[0]),
                              max(tileSize1[1],tileSize2[1]))
                    
                    # Process
                    subArgs=MSSlib_stereo.StereoParam(lstImgPath, lstCamPath, pathDict['pDm'])                
                    asp.stereo(subArgs)

                    subArgs=MSSlib_stereo.P2DParam(pathDict['pDm']+'-PC.tif')
                    asp.point2dem(subArgs)
                    #os.system('mv %s %s'% (pathDict['pDm']+'-DEM.tif', pathDict['pDm']+'%04i-DEM.tif'% i))
                    #os.system('mv %s %s'% (pathDict['pDm']+'-IntersectionErr.tif', pathDict['pDm']+'%04i-IntersectionErr.tif'% i))
                    input('-----')
                    continue
                    sys.exit()
            
        #---------------------------------------------------------------
        # Step
        #---------------------------------------------------------------
        logger.info('# Step')
        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
