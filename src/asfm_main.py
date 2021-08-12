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
        parser.add_argument('-p', default=8, help='Process last step- 0: ReadBlock, 1: CamCreat, 2: CtrlCam, 3: OrbitVis, 4: BA-KP, 5: BA-Free, 6:BA-EO, 7: BA-IO, 8:Export (default: 8)')
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: False means all)')
        parser.add_argument('-fullBA',action='store_true', help=' Compute a full BA (KP,EO,IO) in one shot (default: False)')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        if not -1<args.p<9: raise RuntimeError("Last process step must in range [0, 8]")
        
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
        logger.info('# Read Block')
        objBlocks=SceneBlocks([], args.i, 'dir')
        logger.info(objBlocks)
        
        if not args.b:
            lstLoop=range(objBlocks.nbB)
        else:
            lstLoop=[i for i in range(objBlocks.nbB) if objBlocks.lstBId[i][0] in args.b]
        
        if args.p==0: raise RuntimeError("Process end")
        for iB in lstLoop:
            bId, nbFeat= objBlocks.lstBId[iB]
            logger.info(bId)
            objPath=PathCur(args.i, bId, args.dem)

            #---------------------------------------------------------------
            # Camera creation
            #---------------------------------------------------------------
            logger.info('# Camera creation')
            procBar=ProcessStdout(name='Scene and camera creation',inputCur=nbFeat)
            lstCtlCam=[]
            for j in range(nbFeat):
                procBar.ViewBar(j)
                
                # Create camera
                subArgs=ASfMFunc.SubArgs_Camgen(objPath, objBlocks.lstBFeat[iB][j])
                asp.cam_gen(subArgs)
                
                # Add distortion
                subArgs=ASfMFunc.SubArgs_DistoCam(objPath, objBlocks.lstBFeat[iB][j])
                asp.convert_pinhole_model(subArgs)

                if camDistBa=='TsaiLensDistortion': ASfMFunc.Correct_DistoCam(objPath, objBlocks.lstBFeat[iB][j])

                # Controle coords
                lstCtlCam.append(ASfMFunc.CtlCam(objPath, objBlocks.lstBFeat[iB][j]))
                   
            print()
            if args.p==1: raise RuntimeError("Process end")

            ASfMFunc.CtlCamStat(lstCtlCam)
            if args.p==2: raise RuntimeError("Process end")
            #---------------------------------------------------------------
            # Orbit visualisation
            #---------------------------------------------------------------
            logger.info('# Orbit visualisation')
            regexProcImg= os.path.join(objPath.pProcData, '*.tif')
            regexProcCam= os.path.join(objPath.pProcData, objPath.nTsai[1].format('*'))
            pathOut= objPath.pOrbit
            
            if not os.path.exists(pathOut): 
                subArgs=(regexProcImg,
                        regexProcCam,
                        '-o', pathOut,
                        )
                asp.orbitviz(subArgs)
            if args.p==3: raise RuntimeError("Process end")
            
            #---------------------------------------------------------------
            # Bundle adjustment series
            #---------------------------------------------------------------
            pathPairTxt=ASfMFunc.StereoDescriptor(objPath, objBlocks.lstBCouple[iB])
            
            subArgs=ASfMFunc.SubArgs_BunAdj(objPath, glob(regexProcImg))

            #---------------------------------------------------------------
            # Key point extraction
            #---------------------------------------------------------------
            folderKP=os.path.dirname(objPath.prefKP)
            if not os.path.exists(folderKP):
                logger.info('# Key point extraction')
                asp.parallel_bundle_adjust(subArgs.KeyPoints(objPath.pProcData, objPath.prefKP))
                ASfMFunc.KpCsv2Geojson(objPath.prefKP)
            else:
                logger.warning('%s folder already exists (skipped)'% os.path.basename(folderKP))
            if args.p==4: raise RuntimeError("Process end")

            #---------------------------------------------------------------
            # Free adjustment
            #---------------------------------------------------------------
            if ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefFree):
                logger.info('# Free adjustment')
                asp.parallel_bundle_adjust(subArgs.Free(objPath.prefKP, objPath.prefFree))
                ASfMFunc.KpCsv2Geojson(objPath.prefFree)
            if args.p==5: raise RuntimeError("Process end")

            #---------------------------------------------------------------
            # EO adjustment
            #---------------------------------------------------------------
            if ASfMFunc.CopyPrevBA(objPath.prefFree, objPath.prefEO):
                logger.info('# EO adjustment')
                asp.parallel_bundle_adjust(subArgs.EO(objPath.prefFree, objPath.prefEO))
                ASfMFunc.KpCsv2Geojson(objPath.prefEO)
            if args.p==6: raise RuntimeError("Process end")

            #---------------------------------------------------------------
            # IO adjustment
            #---------------------------------------------------------------
            if ASfMFunc.CopyPrevBA(objPath.prefFree, objPath.prefIO):
                logger.info('# IO adjustment')
                asp.parallel_bundle_adjust(subArgs.IO(objPath.prefEO, objPath.prefIO))
                ASfMFunc.KpCsv2Geojson(objPath.prefIO)
            if args.p==7: raise RuntimeError("Process end")

            #---------------------------------------------------------------
            # Export cam
            #---------------------------------------------------------------
            procBar=ProcessStdout(name='Camera export',inputCur=nbFeat)
            lstCtlCam=[]
            for j in range(nbFeat):
                procBar.ViewBar(j)
                subArgs=ASfMFunc.SubArgs_ExportCam(objPath.prefIO, objPath, objBlocks.lstBFeat[iB][j])
                asp.convert_pinhole_model(subArgs)
                
            print()
            if args.p==8: raise RuntimeError("Process end")
              
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
