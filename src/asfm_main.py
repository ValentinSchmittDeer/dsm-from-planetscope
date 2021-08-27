#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from glob import glob
from pprint import pprint


# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import ASP, ASfMFunc

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
featIdTest=('20210112_180848_0f15',
'20210112_180847_0f15',
'20210107_180314_1040',
'20210107_180316_1040',
'20210105_180642_0f22',
'20210105_180643_0f22',
    )
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def FixControl(prefIn):
    logger.error('_______FIX CONTROL_______')
    ASfMFunc.CopyPrevBA(prefIn, objPath.prefFix)
    asp.bundle_adjust(subArgs.Fix(prefIn, objPath.prefFix))
    ASfMFunc.KpCsv2Geojson(objPath.prefFix)

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
        parser.add_argument('-p', type=int, default=8, help='Process last step- 0: ReadBlock, 1: CamCreat, 2: CtrlCam, 3: OrbitVis, 4: BA-KP, 5: BA-Free, 6:BA-EO, 7: BA-IO, 8:Export (default: 8)')
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: False means all)')
        parser.add_argument('-ortho',action='store_true', help='Compute orthophoto from initial and final parameters (default: False)')
        parser.add_argument('-epsg', default='32611', help='Current ESPG used by initial ortho (default: 32611)')

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
        # Read Block
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
            #---------------------------------------------------------------
            # Test Mode
            #---------------------------------------------------------------
            logger.warning('# TEST MODE')
            lstTemp=[objBlocks.lstBFeat[iB][j] for j in range(objBlocks.lstBId[iB][1]) if objBlocks.lstBFeat[iB][j]['id'] in featIdTest]
            objBlocks.lstBFeat[iB]=lstTemp
            objBlocks.lstBId[iB]=(objBlocks.lstBId[iB][0], len(lstTemp))
            lstTemp=[objBlocks.lstBCouple[iB][j] for j in range(len(objBlocks.lstBCouple[iB])) if not False in [idCur in featIdTest for idCur in objBlocks.lstBCouple[iB][j]['properties']['scenes'].split(';')]]
            objBlocks.lstBCouple[iB]=lstTemp
            
            ###################
            bId, nbFeat= objBlocks.lstBId[iB]
            logger.info('%s (%i scenes)'% objBlocks.lstBId[iB])
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

                # Ortho Init
                if args.ortho:
                    asp.mapproject(ASfMFunc.SubArgs_Ortho('Init', objPath, objBlocks.lstBFeat[iB][j], objPath.pProcData, args.epsg))
                   
            print()
            if args.p==1: continue

            ASfMFunc.CtlCamStat(lstCtlCam)
            if args.p==2: continue
            #---------------------------------------------------------------
            # Orbit visualisation
            #---------------------------------------------------------------
            logger.info('# Orbit visualisation')
            regexProcImg= os.path.join(objPath.pProcData, objPath.extFeat1B.format('*'))
            regexProcCam= os.path.join(objPath.pProcData, objPath.nTsai[1].format('*'))
            pathOut= objPath.pOrbit
            
            if not os.path.exists(pathOut): 
                subArgs=(regexProcImg,
                        regexProcCam,
                        '-o', pathOut,
                        )
                asp.orbitviz(subArgs)
            if args.p==3: continue
            
            #---------------------------------------------------------------
            # Bundle adjustment series
            #---------------------------------------------------------------
            ASfMFunc.StereoDescriptor(objPath, objBlocks.lstBCouple[iB])
            
            lstImgId=[feat['id'] for feat in objBlocks.lstBFeat[iB]]
            subArgs=ASfMFunc.SubArgs_BunAdj(objPath, lstImgId)

            #---------------------------------------------------------------
            # Key point extraction
            #---------------------------------------------------------------
            folderKP=os.path.dirname(objPath.prefKP)
            
            if not os.path.exists(folderKP):
                logger.info('# Key point extraction')
                
                # Stereo feature extraction
                for j in range(len(objBlocks.lstBCouple[iB])):
                    print('Pair %i'% objBlocks.lstBCouple[iB][j]['id'], end=';')
                    if not objBlocks.lstBCouple[iB][j]['properties']['nbScene']==2: continue
                    asp.stereo(ASfMFunc.SubArgs_StereoKP(objPath, objBlocks.lstBCouple[iB][j]))
                    ASfMFunc.CopyMatches(objPath.prefStereoKP, objPath.prefKP, kp='disp')
                print()

                # Fixed bundle adjustment
                asp.bundle_adjust(subArgs.Fix(objPath.pProcData, objPath.prefKP))
                ASfMFunc.KpCsv2Geojson(objPath.prefKP)
            else:
                logger.warning('%s folder already exists (skipped)'% os.path.basename(folderKP))
            if args.p==4: continue

            #---------------------------------------------------------------
            # Free adjustment
            #---------------------------------------------------------------
            if not ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefFree, kp='clean'):
                logger.info('# Free adjustment')
                asp.bundle_adjust(subArgs.Free(objPath.prefKP, objPath.prefFree))
                ASfMFunc.KpCsv2Geojson(objPath.prefFree)
                
            if args.ortho:
                [asp.mapproject(ASfMFunc.SubArgs_Ortho('Free', objPath, objBlocks.lstBFeat[iB][j], objPath.prefFree, args.epsg)) for j in range(nbFeat)]
            if args.p==5: continue
            
            #---------------------------------------------------------------
            # EO adjustment
            #---------------------------------------------------------------
            if not ASfMFunc.CopyPrevBA(objPath.prefFree, objPath.prefEO, kp='none'):
                logger.info('# EO adjustment')
                ASfMFunc.KpCsv2Gcp(os.path.join(objPath.pB,'EO-cnet.csv'), 
                                    objPath.prefEO, 
                                    accuXY=10, 
                                    accuZ=30, 
                                    accuI=3)
                asp.bundle_adjust(subArgs.EO(objPath.prefFree, objPath.prefEO))
                ASfMFunc.KpCsv2Geojson(objPath.prefEO)
            if args.p==6: continue

            #---------------------------------------------------------------
            # IO adjustment
            #---------------------------------------------------------------
            if False  and not ASfMFunc.CopyPrevBA(objPath.prefFree, objPath.prefIO):
                logger.info('# IO adjustment')
                asp.parallel_bundle_adjust(subArgs.IO(objPath.prefEO, objPath.prefIO))
                ASfMFunc.KpCsv2Geojson(objPath.prefIO)
            if args.p==7: raise RuntimeError("Process end")

            #---------------------------------------------------------------
            # Export cam
            #---------------------------------------------------------------
            logger.info('# Camera export')
            procBar=ProcessStdout(name='Camera export',inputCur=nbFeat)
            lstCtlCam=[]
            for j in range(nbFeat):
                procBar.ViewBar(j)
                ### Normally IO
                subArgs=ASfMFunc.SubArgs_ExportCam(objPath.prefKP, objPath, objBlocks.lstBFeat[iB][j])
                asp.convert_pinhole_model(subArgs)
                
            print()
            if args.p==8: continue
              
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)


