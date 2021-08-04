#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from glob import glob
from pprint import pprint


# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
#from PCT import *
from BlockProc import *

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
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: False means all)')
        parser.add_argument('-fullBA',action='store_true', help=' Compute a full BA (KP,EO,IO) in one shot (default: False)')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        print()
        
        #---------------------------------------------------------------
        # ASP Python interface
        #---------------------------------------------------------------
        logger.info('# ASP Python interface')        
        asp=ASP.AspPython()
        
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
            objPath=PathCur(args.i, bId, args.dem)

            #---------------------------------------------------------------
            # Camera creation
            #---------------------------------------------------------------
            #logger.info('# Camera creation')
            procBar=ProcessStdout(name='Scene and camera creation',inputCur=nbFeat)
            lstCtlCam=[]
            for j in range(nbFeat):
                procBar.ViewBar(j)
                
                # Create camera
                subArgs=ASfMFunc.SubArgs_Camgen(objPath, objBlocks.lstBFeat[iB][j])
                asp.cam_gen(subArgs)
                
                # Add distortion
                subArgs=ASfMFunc.SubArgs_ConvertCam(objPath, objBlocks.lstBFeat[iB][j])
                asp.convert_pinhole_model(subArgs)

                # Controle coords
                lstCtlCam.append(ASfMFunc.CtlCam(objPath, objBlocks.lstBFeat[iB][j]))
                   
            print()
            ASfMFunc.CtlCamStat(lstCtlCam)
            
            #---------------------------------------------------------------
            # Orbit visualisation
            #---------------------------------------------------------------
            logger.info('# Orbit visualisation')
            regexProcImg= os.path.join(objPath.pProcData, '*.tif')
            regexProcCam= os.path.join(objPath.pProcData, objPath.nTsai[1].format('*'))
            pathOut= objPath.pOrbit
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
            pathPairTxt=ASfMFunc.StereoDescriptor(objPath, objBlocks.lstBCouple[iB])
            
            subArgs=ASfMFunc.SubArgs_BunAdj(objPath, glob(regexProcImg))
            
            # OR full BA
            if args.fullBA:
                if os.path.exists(os.path.dirname(objPath.prefFull)): raise RuntimeError("Full BA folder already exists")
                logger.info('# Full adjustment')
                asp.parallel_bundle_adjust(subArgs.Full(objPath.pProcData, objPath.prefFull))
                #ASfMFunc.ExportCam(objPath.prefIO, objPath.pProcData)
                ASfMFunc.KpCsv2Geojson(objPath.prefFull)
                raise RuntimeError("Full BA finished")

            #---------------------------------------------------------------
            # Key point extraction
            #---------------------------------------------------------------
            folderKP=os.path.dirname(objPath.prefKP)
            input(folderKP)
            if not os.path.exists(folderKP):
                logger.info('# Key point extraction')
                asp.parallel_bundle_adjust(subArgs.KeyPoints(objPath.pProcData, objPath.prefKP))
                ASfMFunc.KpCsv2Geojson(objPath.prefKP)
            
            #---------------------------------------------------------------
            # EO adjustment
            #---------------------------------------------------------------
            #input('EO')
            if ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefEO):
                logger.info('# EO adjustment')
                asp.parallel_bundle_adjust(subArgs.EO(objPath.prefKP, objPath.prefEO))
                ASfMFunc.KpCsv2Geojson(objPath.prefEO)
                        
            #---------------------------------------------------------------
            # IO adjustment
            #---------------------------------------------------------------
            #input('IO')
            if ASfMFunc.CopyPrevBA(objPath.prefEO, objPath.prefIO, gcp=True):
                logger.info('# IO adjustment')
                asp.parallel_bundle_adjust(subArgs.IO(objPath.prefEO, objPath.prefIO))
                ASfMFunc.KpCsv2Geojson(objPath.prefIO)
            
            #ASfMFunc.ExportCam(objPath.prefIO, objPath.pProcData)
              
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
