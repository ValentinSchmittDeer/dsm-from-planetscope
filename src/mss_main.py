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
            logger.info('# Dense matching')

            for i,pairCur in enumerate(objBlocks.lstBCouple[iB]):
                if not i==580: continue
                #---------------------------------------------------------------
                # Find Images
                #---------------------------------------------------------------
                lstImgId=[pairCur['properties'][key] for key in pairCur['properties'] if key.startswith('scene')]
                lstOfLst=[glob(os.path.join(pathDict['pProcData'], idCur+'*.tif')) for idCur in lstImgId]
                lstImgPath=[lst[0] for lst in lstOfLst if lst]
                if not len(lstImgPath)==2: continue
                
                #---------------------------------------------------------------
                # More images
                #---------------------------------------------------------------
                if args.m=='MVS':
                    lstFuthImgId=MSSlib_stereo.MvsAddImg(pairCur, objBlocks.lstBCouple[iB])
                    lstOfLst=[glob(os.path.join(pathDict['pProcData'], idCur+'*.tif')) for idCur in lstFuthImgId]
                    lstImgPath+=[lst[0] for lst in lstOfLst if lst]
                    print(len(lstImgPath), lstImgPath)

                #---------------------------------------------------------------
                # Find the best Tsai
                #---------------------------------------------------------------
                lstCamPath=[]
                for pathImg in lstImgPath:
                    lstCam=glob(pathImg.split('.')[0]+'*.tsai')
                    if not lstCam: raise RuntimeError('Camera file (tsai) not found: %s'% pathImg)
                    lstCam.sort()
                    lstCamPath.append(lstCam[-1],)
                
                print(lstCamPath)
                input('GO?')
                #---------------------------------------------------------------
                # Preparation
                #---------------------------------------------------------------
                '''
                There are 2 options:
                    alignment-method epipolar> +: make use of input geometry -: must shrink the mask
                    alignment-method affineepipolar> +: automatic relvant mask, better result -: transfo based on new key points
                '''
                #subArgs=MSSlib_stereo.StereoParam(lstImgPath, lstCamPath, pathDict['pDm'])                
                #asp.stereo_pprc(subArgs)
                #input('pprc OK')
                #if not os.path.exists(os.path.dirname(pathDict['pDm'])): 
                #    logger.error('preparation step failed: %i'% i)
                #    cmd='rm -r %s*'% pathDict['pDm']
                #    os.system(cmd)
                #    continue
                #tileSize1=MSSlib_stereo.OverlapMask(pairCur, pathDict['pDm']+'-lMask.tif', pathDict['pDm']+'-L.tsai', args.dem)
                #tileSize2=MSSlib_stereo.OverlapMask(pairCur, pathDict['pDm']+'-rMask.tif', pathDict['pDm']+'-R.tsai', args.dem)
                #
                #cmd='rm %s*_sub.tif'% pathDict['pDm']
                #os.system(cmd)
                #input('mask OK')
                
                #---------------------------------------------------------------
                # Process
                #---------------------------------------------------------------
                subArgs=MSSlib_stereo.StereoParam(lstImgPath, lstCamPath, pathDict['pDm'])                
                print(subArgs)
                asp.stereo(subArgs)
                #input('stereo OK')
                if not os.path.exists(pathDict['pDm']+'-PC.tif'): 
                    cmd='rm -r %s*'% pathDict['pDm']
                    os.system(cmd)
                    continue
                subArgs=MSSlib_stereo.P2DParam(pathDict['pDm']+'-PC.tif')
                asp.point2dem(subArgs)
                #input('dem OK')
                
                #---------------------------------------------------------------
                # Save Process
                #---------------------------------------------------------------
                perfOut=os.path.join(os.path.dirname(pathDict['pDm']),'ResDM')
                for nameIn in ('-DEM.tif', '-IntersectionErr.tif', '-GoodPixelMap.tif', '-F.tif'):
                    pathIn=pathDict['pDm']+nameIn
                    if not os.path.exists(pathIn): 
                        logger.error('File not found (%s): pair %i'% (nameIn, i))
                    else:
                        cmd='mv {} {}'.format(pathIn, 
                                                    perfOut+nameIn.replace('.', '-%i.'% i)
                                                    )
                        #print(cmd)
                        os.system(cmd)

                input('next OK')
                
                #---------------------------------------------------------------
                # Clean folder
                #---------------------------------------------------------------
                cmd='rm -r %s*'% pathDict['pDm']
                #print(cmd)
                os.system(cmd)
            

    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
