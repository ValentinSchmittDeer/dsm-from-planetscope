#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from glob import glob
from pprint import pprint

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, ProcessStdout
from PVL.PVL_Rpc import *

# dsm_from_planetscope libraries
from SSBP.SSBPlib_block import SceneBlocks
from PCT import *
from ASfM.ASfMlib_asp import AspUtility as AspObj
from ASfM import *
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
featIdTest=['20210328_151810_1020_1A_Analytic_DN.tif','20210328_151811_1020_1A_Analytic_DN.tif']

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
        parser.add_argument('-i', required=True, help='Working directory')
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM)')


        # Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: [] means all')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        #---------------------------------------------------------------
        # Check planet_common and docker
        #---------------------------------------------------------------
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
            pathDict=ASfMlib_ba.BlockPathDict(args.i, bId, args.dem)
            

            #---------------------------------------------------------------
            # Camera creation
            #---------------------------------------------------------------
            #logger.info('# Camera creation')
            procBar=ProcessStdout(name='Scene and camera creation',inputCur=nbFeat)
            for j in range(nbFeat):
                if not j in (7, 8, 9, 13, 14, 15): continue
                procBar.ViewBar(j)
                
                subArgs=ASfMlib_ba.CameraParam(pathDict, objBlocks.lstBFeat[iB][j])
                asp.cam_gen(subArgs)

                subArgs=ASfMlib_ba.ConvertCameraParam(pathDict, objBlocks.lstBFeat[iB][j])
                asp.convert_pinhole_model(subArgs)
                
            print()

            #---------------------------------------------------------------
            # Orbit visualisation
            #---------------------------------------------------------------
            logger.info('# Orbit visualisation')
            regexProcImg= os.path.join(pathDict['pProcData'], '*.tif')
            regexProcCam= os.path.join(pathDict['pProcData'], nameTsai1.format('*'))
            pathOut= os.path.join(pathDict['pB'],'%s_InitialCam.kml'% bId)
            subArgs=(regexProcImg,
                    regexProcCam,
                    '-o', pathOut,
                    )
            if os.path.exists(pathOut): 
                os.remove(pathOut)
                logger.info('Overwrite %s'% os.path.basename(pathOut))
            asp.orbitviz(subArgs)
            
            #---------------------------------------------------------------
            # Bundle adjustment series
            #---------------------------------------------------------------
            pathPairTxt=ASfMlib_ba.StereoPairDescriptor(pathDict, objBlocks.lstBCouple[iB])

            argsCur=ASfMlib_ba.BunAdjParam(glob(regexProcImg), args.dem, pathPairTxt)

            #---------------------------------------------------------------
            # Key point extraction
            #---------------------------------------------------------------
            folderKP=os.path.dirname(pathDict['baKP'])
            if not os.path.exists(folderKP):
                logger.info('# Key point extraction')
                input('ENTER\n')
                asp.bundle_adjust(argsCur.KeyPoints(pathDict['pProcData'], pathDict['baKP']))

            #---------------------------------------------------------------
            # EO adjustment
            #---------------------------------------------------------------
            if ASfMlib_ba.CopyPrevBA(pathDict['baKP'], pathDict['baEO']):
                logger.info('# EO adjustment')
                input('ENTER\n')
                asp.bundle_adjust(argsCur.EO(pathDict['baKP'], pathDict['baEO']))
                        
            #---------------------------------------------------------------
            # IO adjustment
            #---------------------------------------------------------------
            if ASfMlib_ba.CopyPrevBA(pathDict['baEO'], pathDict['baIO'], gcp=True):
                logger.info('# IO adjustment')
                input('ENTER\n')
                asp.bundle_adjust(argsCur.IO(pathDict['baEO'], pathDict['baIO']))
            
            ASfMlib_ba.ExportCam(pathDict['baIO'], pathDict['pProcData'])
            
            logger.warning("Normalise function name in ..._ba")



        
        
        
        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
