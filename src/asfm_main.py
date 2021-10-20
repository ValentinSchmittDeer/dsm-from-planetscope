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
# Small Block
featIdTest=('20201225_180508_1003',
'20201225_180507_1003',
'20201220_180803_0f15',
'20201220_180802_0f15',
'20201202_153645_0f21',
'20201202_153644_0f21',
'20201201_180335_103c',
'20201201_180334_103c')

#featIdTest=('20210112_180846_0f15',
# '20210112_180848_0f15',
# '20210112_180847_0f15',
# '20210107_180314_1040',
# '20210107_180316_1040',
# '20210105_180642_0f22',
# '20210105_180643_0f22'
# )

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def Main(args):
    try:
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        
        if not args.m in ('rpc','pm'): raise RuntimeError("BA mode unknown")
        lstProcLvl=('read', 'data', 'ortho', 'kp', 'eo', 'io', 'exp')
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
            #---------------------------------------------------------------
            bId, nbFeat= objBlocks.lstBId[iB]
            logger.info('%s (%i scenes)'% objBlocks.lstBId[iB])
            objPath=PathCur(args.i, bId, args.dem)
            
            if iProc <= lstProcLvl.index('read'): continue

            #---------------------------------------------------------------
            # Process data 
            #---------------------------------------------------------------
            logger.info('# Process data')
            procBar=ProcessStdout(name='Process data creation',inputCur=nbFeat)
            for j in range(nbFeat):
                procBar.ViewBar(j)
                featCur=objBlocks.lstBFeat[iB][j]
                idImg=featCur['id']
                pathImgIn=os.path.join(objPath.pData, objPath.extFeat.format(idImg))
                pathImgOut=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                
                if not os.path.exists(pathImgOut): ASfMFunc.SingleBandImg(pathImgIn, pathImgOut)

            if iProc <= lstProcLvl.index('data'): continue

            #---------------------------------------------------------------
            # Initial ortho
            #---------------------------------------------------------------
            logger.info('# Initial ortho')
            procBar=ProcessStdout(name='Initial ortho creation',inputCur=nbFeat)
            for j in range(nbFeat):
                procBar.ViewBar(j)
                featCur=objBlocks.lstBFeat[iB][j]
                idImg=featCur['id']
                pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                pathOrtho=objPath.pOrtho.format(idImg, 'Init')

                if not os.path.exists(pathOrtho): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathRpcIn, objPath.pDem, pathOrtho, args.epsg))
                
            if iProc <= lstProcLvl.index('ortho'): continue

            #---------------------------------------------------------------
            # Bundle adjustment series
            #---------------------------------------------------------------
            ASfMFunc.StereoDescriptor(objPath, objBlocks.lstBCouple[iB])
            
            lstImgId=[feat['id'] for feat in objBlocks.lstBFeat[iB]]
            subArgs=ASfMFunc.SubArgs_BunAdj(objPath, lstImgId, args.m)

            #---------------------------------------------------------------
            # Key point extraction
            #---------------------------------------------------------------
            if not os.path.exists(objPath.prefKP+'-cnet.csv'):
                logger.info('# Key point')
                folderKP=os.path.dirname(objPath.prefKP)
                if not os.path.exists(folderKP): os.mkdir(folderKP)

                # Feature extraction (stereo)
                nbComb=len(objBlocks.lstBCouple[iB])
                lstPair=[objBlocks.lstBCouple[iB][j]['properties']['scenes'] 
                            for j in range(nbComb) 
                            if objBlocks.lstBCouple[iB][j]['properties']['nbScene']==2]

                procBar=ProcessStdout(name='Feature extraction',inputCur=len(lstPair))
                #for j in ():
                for j, strId in enumerate(lstPair):
                    procBar.ViewBar(j)
                    lstId=sorted(strId.split(';'))
                    
                    basenameMatch='__'.join([objPath.extFeat1B.format(idCur).split('.')[0] for idCur in lstId])
                    pathMatch=objPath.prefKP+'-'+basenameMatch+'.match'
                    if os.path.exists(pathMatch): continue

                    softLvl=0
                    asp.stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath, lstId, softness=softLvl))
                    
                    while ASfMFunc.CopyPrevBA(objPath.prefStereoKP, objPath.prefKP, existBool=False, img=False, kp='disp') and softLvl<2:
                        softLvl+=1
                        print('\nLvl %i'% softLvl, end='')
                        asp.stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath, lstId, softness=softLvl))
                
                print()
                
                # Initialisation bundle adjustment: Merge obs 
                asp.bundle_adjust(subArgs.KP_RPC(objPath.pProcData, objPath.prefKP))
                ASfMFunc.KpCsv2Geojson(objPath.prefKP)
                
            else:
                logger.error('%s folder already full (skipped)'% os.path.basename(objPath.prefKP))
            
            if iProc <= lstProcLvl.index('kp'): continue

            #=======================================================================
            # RPC-BA
            #-----------------------------------------------------------------------
            if args.m=='rpc':
                logger.warning('RPC-BA mode')
                #---------------------------------------------------------------
                # RPC adjust EO
                #---------------------------------------------------------------
                if not ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefEO):
                    logger.info('# RPC adjust EO')
                    asp.bundle_adjust(subArgs.Adjust_RPC(objPath.prefKP, objPath.prefEO))
                    ASfMFunc.KpCsv2Geojson(objPath.prefEO)

                    procBar=ProcessStdout(name='EO RPC creation',inputCur=nbFeat)
                    for j in range(nbFeat):
                        procBar.ViewBar(j)
                        featCur=objBlocks.lstBFeat[iB][j]
                        idImg=featCur['id']
                        pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                        pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                        pathRpcOut=objPath.prefEO+'-'+objPath.extRpc1Bx.format(idImg)

                        asp.cam2rpc(ASfMFunc.SubArgs_Adj2Rpc(pathImgIn, pathRpcIn, objPath.pDem, pathRpcOut, prefBA=objPath.prefEO))

                if iProc <= lstProcLvl.index('eo'): continue

                #---------------------------------------------------------------
                # RPC adjust IO
                #---------------------------------------------------------------
                if not ASfMFunc.CopyPrevBA(objPath.prefEO, objPath.prefIO):
                    logger.info('# RPC adjust IO')
                    subArgs.ImageAdjust_RPC(objPath.prefEO, objPath.prefIO, objPath, outGraph=False)

                if iProc <= lstProcLvl.index('io'): continue

                #---------------------------------------------------------------
                # Export model
                #---------------------------------------------------------------
                logger.info('# RPC export')
                lstIn=glob(objPath.prefIO+objPath.extRpc1B.format('*'))
                if not objPath.pProcData.endswith('/'):
                    prefOut=objPath.pProcData+'/'
                else:
                    prefOut=objPath.pProcData
                
                procBar=ProcessStdout(name='RPC export',inputCur=len(lstIn))
                for j in range(len(lstIn)):
                    procBar.ViewBar(j)
                    pathOut=lstIn[j].replace(objPath.prefIO+'-', prefOut)
                    cmd='cp %s %s'% (lstIn[j], pathOut)
                    os.system(cmd)
                
                if iProc <= lstProcLvl.index('exp'): continue

            #=======================================================================
            # PM-BA
            #-----------------------------------------------------------------------
            elif args.m=='pm':
                logger.warning('PM-BA mode')
                #---------------------------------------------------------------
                # Camera creation
                #---------------------------------------------------------------
                logger.info('# Camera creation')
                procBar=ProcessStdout(name='Scene and camera creation',inputCur=nbFeat)
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[iB][j]
                    idImg=featCur['id']
                    pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                    pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                    pathCamOut=os.path.join(objPath.pProcData, objPath.nTsai[1].format(idImg))

                    # Point grid
                    if not os.path.exists(pathCamOut): 
                        asp.cam_gen(ASfMFunc.SubArgs_Camgen(pathImgIn, pathRpcIn, objPath.pDem, pathCamOut, pattern='grid'))
                        os.remove(pathCamOut)
                    
                    # RPC 2 PM rough
                    pathCamIn=os.path.join(objPath.pProcData, objPath.nTsai[0].format(idImg))
                    if not os.path.exists(pathCamOut): asp.cam_gen(ASfMFunc.SubArgs_Camgen(pathImgIn, pathRpcIn, objPath.pDem, pathCamIn))

                    # Adjust PM rough 2 init
                    if not os.path.exists(pathCamOut): ASfMFunc.AjustPM(idImg, pathRpcIn, pathCamIn, pathCamOut, outGraph=True)
                
                    # Ortho
                    pathOrthoOut=objPath.pOrtho.format(idImg, 'InitCam')
                    if not os.path.exists(pathOrthoOut):
                        subArgs=[objPath.pDem,
                                pathImgIn,
                                pathCamOut,
                                pathImgIn.replace('.', 'ortho.'),
                                '--t_srs', 'EPSG:'+str(args.epsg), 
                                '-t', 'pinhole',
                                '--tr', str(gsdOrth),
                                '--ot', 'UInt16',
                                ]
                        asp.mapproject(subArgs)

                sys.exit()
                #---------------------------------------------------------------
                # EO adjustment
                #---------------------------------------------------------------
                if not ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefEO):
                    logger.info('# RPC adjust EO')
                    asp.bundle_adjust(subArgs.Adjust_RPC(objPath.prefKP, objPath.prefEO))
                    ASfMFunc.KpCsv2Geojson(objPath.prefEO)
                    
                    procBar=ProcessStdout(name='EO ortho',inputCur=nbFeat)
                    for j in range(nbFeat):
                        procBar.ViewBar(j)
                        featCur=objBlocks.lstBFeat[iB][j]
                        idImg=featCur['id']
                        pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                        pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                        pathCamOut=os.path.join(objPath.pProcData, objPath.nTsai[1].format(idImg))

                        # Ortho
                        subArgs=[objPath.pDem,
                                pathImgIn,
                                pathCamOut,
                                pathImgIn.replace('.', 'ortho.'),
                                '--t_srs', 'EPSG:'+str(args.epsg), 
                                '-t', 'pinhole',
                                '--tr', str(gsdOrth),
                                '--ot', 'UInt16',
                                ]
                        asp.mapproject(subArgs)
                    
                if iProc <= lstProcLvl.index('eo'): continue

###########################################################################

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

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
        print()
        logger = SetupLogger(name=__title__)
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        parser.add_argument('-i', required=True, help='Working directory')
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM)')

        parser.add_argument('-m', default='rpc', help='BA mode RPC|PM (default: RPC)')
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

        argsMain = parser.parse_args()
        
        Main(argsMain)

        print('\nEND, Continue with dense matching')
        

