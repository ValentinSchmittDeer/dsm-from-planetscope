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
# Larger Block
featIdTest=('20210112_180846_0f15',
'20210112_180848_0f15',
'20210112_180847_0f15',
'20210112_180849_0f15',
'20210107_180313_1040',
'20210107_180314_1040',
'20210107_180316_1040',
'20210107_180317_1040',
'20210105_180641_0f22',
'20210105_180642_0f22',
'20210105_180643_0f22',
'20210105_180644_0f22',
    )
# Small Block
#featIdTest=('20210112_180848_0f15',
#'20210112_180847_0f15',
#'20210107_180314_1040',
#'20210107_180316_1040',
#'20210105_180642_0f22',
#'20210105_180643_0f22',
#    )
# In track
#featIdTest=('20210107_180314_1040','20210107_180316_1040',)
# Cross date
#featIdTest=('20210107_180314_1040','20210105_180642_0f22',)
# Cross track
#featIdTest=('20210112_180848_0f15','20210107_180314_1040',)
# One
featIdTest=('20210112_180848_0f15')
# Three
#featIdTest=('20210112_180848_0f15','20210112_180847_0f15','20210105_180642_0f22')
'''
-t rpc
point2dem --errorimage
'''
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

        # Process level
        #   read: ReadBlock
        #   cam: CamCreat
        #   ctrl: CtrlCam
        #   orb: OrbitVis
        #   kp: BA-KP
        #   eo:BA-EO
        #   io: BA-IO,
        #   exp:Export
        parser.add_argument('-p', default='exp', help='Process last step- read: ReadBlock, cam: CamCreat, ctrl: CtrlCam, orb: OrbitVis, kp: BA-KP, eo:BA-EO, io: BA-IO, exp:Export (default: exp)')

        # Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: False means all)')
        parser.add_argument('-ortho',action='store_true', help='Compute orthophoto from initial and final parameters (default: False)')
        parser.add_argument('-epsg', default='32611', help='Current ESPG used by initial ortho (default: 32611)')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        
        lstProcLvl=('read', 'cam', 'ctrl', 'orb', 'kp', 'eo', 'io', 'exp')
        if not args.p in lstProcLvl: raise RuntimeError("Last process step unknown")
        iProc=lstProcLvl.index(args.p)

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

            if iProc <= lstProcLvl.index('read'): continue

            #---------------------------------------------------------------
            # Camera creation
            #---------------------------------------------------------------
            logger.info('# Camera creation')
            procBar=ProcessStdout(name='Scene and camera creation',inputCur=nbFeat)
            lstCtlCam=[]
            for j in range(nbFeat):
                procBar.ViewBar(j)

                # Point grid
                asp.cam_gen(ASfMFunc.SubArgs_Camgen(objPath, objBlocks.lstBFeat[iB][j], pat='grid'))
                
                pathCam=glob(os.path.join(objPath.pProcData, objPath.nTsai[0].format(objBlocks.lstBFeat[iB][j]['id']+'*')))[0]
                pathGcpIn=pathCam.split('.')[0]+'.gcp'
                pathGcpOut=pathGcpIn.replace('0Rough','0Grid')
                if not os.path.exists(pathGcpOut):
                    os.remove(pathCam)
                    os.system('mv %s %s'% (pathGcpIn, pathGcpOut))
                
                # RPC 2 PM rough
                asp.cam_gen(ASfMFunc.SubArgs_Camgen(objPath, objBlocks.lstBFeat[iB][j]))
                
                # Distortion modeling
                if ASfMFunc.Gcp2Disto(objPath, objBlocks.lstBFeat[iB][j], distModel='photometrixdrpc', outGraph=True)>1: continue
                
                # Conversion to TSAI model
                asp.convert_pinhole_model(ASfMFunc.SubArgs_ConvertCam(objPath, objBlocks.lstBFeat[iB][j]))

                # Test ortho
                input('Ortho?')

                subArgs=[objPath.pDem,
                        os.path.join(objPath.pProcData, objPath.extFeat1B.format(objBlocks.lstBFeat[iB][j]['id'])),
                        os.path.join(objPath.pProcData, objPath.nTsai[1].format(objPath.extFeat1B.format(objBlocks.lstBFeat[iB][j]['id']).split('.')[0])),
                        objPath.pOrtho.format(objPath.extFeat1B.format(objBlocks.lstBFeat[iB][j]['id']).split('.')[0], 'PM'),
                        '--t_srs', 'EPSG:'+str(args.epsg), 
                        '-t', 'pinhole',
                        '--tr', str(gsdOrth),
                        '--ot', 'UInt16',
                        ]
                asp.mapproject(subArgs)
                
                subArgs=[objPath.pDem,
                        os.path.join(objPath.pProcData, objPath.extFeat1B.format(objBlocks.lstBFeat[iB][j]['id'])),
                        os.path.join(objPath.pData, objPath.extFeat.format(objBlocks.lstBFeat[iB][j]['id']))[:-4]+'_RPC.TXT',
                        objPath.pOrtho.format(objPath.extFeat1B.format(objBlocks.lstBFeat[iB][j]['id']).split('.')[0], 'RPC'),
                        '--t_srs', 'EPSG:'+str(args.epsg), 
                        '-t', 'rpc',
                        '--tr', str(gsdOrth),
                        '--ot', 'UInt16',
                        ]
                asp.mapproject(subArgs)
                
                # Controle coords
                lstCtlCam.append(ASfMFunc.CtlCam(objPath, objBlocks.lstBFeat[iB][j]))

                # Ortho Init
                if args.ortho:
                    asp.mapproject(ASfMFunc.SubArgs_Ortho('Init', objPath, objBlocks.lstBFeat[iB][j], objPath.pProcData, args.epsg))
                   
            print()
            
            if iProc <= lstProcLvl.index('cam'): continue

            ASfMFunc.CtlCamStat(lstCtlCam)
            
            if iProc <= lstProcLvl.index('ctrl'): continue
            raise RuntimeError("Development break")
            #---------------------------------------------------------------
            # Orbit visualisation
            #---------------------------------------------------------------
            logger.info('# Orbit visualisation')
            regexProcImg= os.path.join(objPath.pProcData, objPath.extFeat1B.format('*'))
            regexProcCam= os.path.join(objPath.pProcData, objPath.nTsai[1].format('*'))
            pathOut= objPath.pOrbit
            
            if os.path.exists(pathOut): os.remove(pathOut)
            subArgs=(regexProcImg,
                    regexProcCam,
                    '-o', pathOut,
                    )
            asp.orbitviz(subArgs)
            
            if iProc <= lstProcLvl.index('orb'): continue
            
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
                    if not objBlocks.lstBCouple[iB][j]['properties']['nbScene']==2: continue
                    
                    print('Pair%i'% objBlocks.lstBCouple[iB][j]['id'], end=', ')
                    softLvl=0
                    asp.stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath, objBlocks.lstBCouple[iB][j], softness=softLvl))
                    
                    while ASfMFunc.CopyMatches(objPath.prefStereoKP, objPath.prefKP, kp='disp'):
                        raise RuntimeError("ERROR SKP")
                        softLvl+=1
                        asp.stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath, objBlocks.lstBCouple[iB][j], softness=softLvl))

                    ASfMFunc.CopyMatches(objPath.prefStereoKP, objPath.prefKP_std, kp='match')
                
                print()
                
                # Fixed bundle adjustment: Merge obs and ste SRTM height
                asp.bundle_adjust(subArgs.Init(objPath.pProcData, objPath.prefKP))
                ASfMFunc.KpCsv2Geojson(objPath.prefKP)
                ###### stsKP
                asp.bundle_adjust(subArgs.Init(objPath.pProcData, objPath.prefKP_std))
                ASfMFunc.KpCsv2Geojson(objPath.prefKP_std)
                
            else:
                logger.warning('%s folder already exists (skipped)'% os.path.basename(folderKP))
            
            if iProc <= lstProcLvl.index('kp'): continue

            #---------------------------------------------------------------
            # EO adjustment
            #---------------------------------------------------------------
            if not ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefEO, kp='none'):
                logger.info('# EO adjustment')
                ASfMFunc.KpCsv2Gcp(objPath.prefKP+'-cnet.csv', 
                                    objPath.prefEO, 
                                    accuXY=10, 
                                    accuZ=10, 
                                    accuI=0.5)
                
                asp.bundle_adjust(subArgs.EO(objPath.prefKP, objPath.prefEO))
                ASfMFunc.KpCsv2Geojson(objPath.prefEO)
            
                if args.ortho:
                    [asp.mapproject(ASfMFunc.SubArgs_Ortho('EO', objPath, objBlocks.lstBFeat[iB][j], objPath.prefEO, args.epsg)) for j in range(nbFeat)]

                ###### stsKP
                ASfMFunc.CopyPrevBA(objPath.prefKP_std, objPath.prefEO_std, kp='none')
                ASfMFunc.KpCsv2Gcp(objPath.prefKP_std+'-cnet.csv', 
                                    objPath.prefEO_std, 
                                    accuXY=10, 
                                    accuZ=10, 
                                    accuI=0.5)
                asp.bundle_adjust(subArgs.EO(objPath.prefKP_std, objPath.prefEO_std))
                ASfMFunc.KpCsv2Geojson(objPath.prefEO_std)
            
                if args.ortho:
                    [asp.mapproject(ASfMFunc.SubArgs_Ortho('EO_std', objPath, objBlocks.lstBFeat[iB][j], objPath.prefEO_std, args.epsg)) for j in range(nbFeat)]


            if iProc <= lstProcLvl.index('eo'): continue

            #---------------------------------------------------------------
            # IO adjustment
            #---------------------------------------------------------------
            if False  and not ASfMFunc.CopyPrevBA(objPath.prefFree, objPath.prefIO):
                logger.info('# IO adjustment')
                asp.parallel_bundle_adjust(subArgs.IO(objPath.prefEO, objPath.prefIO))
                ASfMFunc.KpCsv2Geojson(objPath.prefIO)
            
            if iProc >= lstProcLvl.index('io'): continue

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
            
            if iProc <= lstProcLvl.index('exp'): continue
              
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)

