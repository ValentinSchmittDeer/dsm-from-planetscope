#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from glob import glob
from pprint import pprint
import rasterio


# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import ASP, ASfMFunc, GeomFunc
from PCT import pipelDFunc

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
gdInfo='gdalinfo'

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
        with rasterio.open(args.dem) as fileIn: 
            if not fileIn.crs==4326: raise RuntimeError("DEM EPSG must be 4326 (WGS 84, geographic)")
        
        if not args.m in ('rpc','pm'): raise RuntimeError("BA mode unknown")
        lstProcLvl=('read', 'data', 'orthoI', 'kp', 'eo', 'io', 'exp', 'orthoF')
        if not args.p in lstProcLvl: raise RuntimeError("Last process step unknown")
        iProc=lstProcLvl.index(args.p)

        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        print()
        
        msg='Are you sure to run RPC-BA with intrinsic adjustment? ([0]|1)'
        if args.io and args.m=='rpc' and not input(msg): raise RuntimeError("RPC-IO-BA is not stable yet")
        msg='Are you sure of the EPSG code for ortho creation? ([0]|1)'
        if args.ortho and not input(msg): raise RuntimeError("EPSG detection not implemented yet")

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
            if 0:
                featIdTest=('20201225_180508_1003',
                            '20201225_180507_1003',
                            '20201220_180803_0f15',
                            '20201220_180802_0f15',
                            '20201202_153645_0f21',
                            '20201202_153644_0f21',
                            '20201201_180335_103c',
                            '20201201_180334_103c',
                            '20201201_153553_1048',
                            '20201201_153552_1048')
                logger.warning('# TEST MODE')
                lstTemp=[objBlocks.lstBFeat[iB][j] for j in range(objBlocks.lstBId[iB][1]) if objBlocks.lstBFeat[iB][j]['id'] in featIdTest]
                objBlocks.lstBFeat[iB]=lstTemp
                objBlocks.lstBId[iB]=(objBlocks.lstBId[iB][0], len(lstTemp))
                lstTemp=[objBlocks.lstBCouple[iB][j] for j in range(len(objBlocks.lstBCouple[iB])) if not False in [idCur in featIdTest for idCur in objBlocks.lstBCouple[iB][j]['properties']['scenes'].split(';')]]
                objBlocks.lstBCouple[iB]=lstTemp
            
            #---------------------------------------------------------------
            # Block Setup
            #---------------------------------------------------------------
            bId, nbFeat= objBlocks.lstBId[iB]
            logger.info('%s (%i scenes)'% objBlocks.lstBId[iB])
            objPath=PathCur(args.i, bId, args.dem)
            
            if iProc <= lstProcLvl.index('read'): continue

            #---------------------------------------------------------------
            # Process data 
            #---------------------------------------------------------------
            logger.info('# Process data')
            procBar=ProcessStdout(name='Data creation',inputCur=nbFeat)
            for j in range(nbFeat):
                procBar.ViewBar(j)
                featCur=objBlocks.lstBFeat[iB][j]
                idImg=featCur['id']
                pathImgIn=os.path.join(objPath.pData, objPath.extFeat.format(idImg))
                pathImgOut=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                                
                if not os.path.exists(pathImgOut): ASfMFunc.SingleBandImg(pathImgIn, pathImgOut, imgType='green')

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
                pathOrtho=objPath.pOrtho.format(idImg, '-Init')

                if not os.path.exists(pathOrtho): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathRpcIn, objPath.pDem, pathOrtho, args.epsg))
                
            if iProc <= lstProcLvl.index('orthoI'): continue

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
                lstIPair=[j for j in range(nbComb) 
                            if objBlocks.lstBCouple[iB][j]['properties']['nbScene']==2]

                procBar=ProcessStdout(name='Feature extraction',inputCur=len(lstIPair))
                for j in lstIPair:
                    procBar.ViewBar(j)
                    strId=objBlocks.lstBCouple[iB][j]['properties']['scenes']
                    lstId=sorted(strId.split(';'))
                    
                    basenameMatch='__'.join([objPath.extFeat1B.format(idCur).split('.')[0] for idCur in lstId])
                    pathMatch=objPath.prefKP+'-'+basenameMatch+'.match'
                    if os.path.exists(pathMatch): continue
                    
                    lstPath=[]
                    for idCur in lstId:
                        GeomFunc.MaskedImg( os.path.join(objPath.pProcData, objPath.extFeat1B.format(idCur)), 
                                            os.path.join(objPath.pData, objPath.extRpc.format(idCur)), 
                                            objPath.pDem, 
                                            objBlocks.lstBCouple[iB][j]['geometry'],
                                            pathImgOut=os.path.join(objPath.pProcData, objPath.extFeatKP.format(idCur)),
                                            buffer=10,
                                            )
                        
                        # RPC creation
                        pathRpcOut=os.path.join(objPath.pProcData, objPath.extRpcKP.format(idCur))
                        cmd='cp %s %s'% (os.path.join(objPath.pData, objPath.extRpc.format(idCur)), 
                                        pathRpcOut)
                        os.system(cmd)

                        lstPath.append((pathImgOut, pathRpcOut))

                    softLvl=-1
                    # KP grid
                    while ASfMFunc.CopyPrevBA(objPath.prefStereoKP, objPath.prefKP, kp='disp', dispExists=True, dirExists=False, img=False) and softLvl<3:
                    # KP sparse + check (with '--stop-point', '2')
                    #while ASfMFunc.CopyPrevBA(objPath.prefStereoKP, objPath.prefKP, kp='match', dispExists=True, dirExists=False, img=False) and softLvl<3:
                        softLvl+=1
                        asp.parallel_stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath, lstPath, softness=softLvl))
                    
                    if softLvl==3 and not os.path.exists(pathMatch): logger.warning('Check feature: %s'% str(lstId))
                    
                    # Remove KP files
                    cmd='rm '
                    cmd+=' '.join([' '.join(tupCur) for tupCur in lstPath])
                    os.system(cmd)

                print()
                
                # Fixed bundle adjustment: Initial residuals
                asp.parallel_bundle_adjust(subArgs.KP_RPC(objPath.pProcData, objPath.prefKP), boolConv=False)
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
                    logger.info('# EO adjustment')
                    asp.parallel_bundle_adjust(subArgs.EO_RPC(objPath.prefKP, objPath.prefEO))
                    ASfMFunc.KpCsv2Geojson(objPath.prefEO)

                    procBar=ProcessStdout(name='EO RPC',inputCur=nbFeat)
                    for j in range(nbFeat):
                        procBar.ViewBar(j)
                        featCur=objBlocks.lstBFeat[iB][j]
                        idImg=featCur['id']
                        pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                        pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                        pathRpcOut=objPath.prefEO+'-'+objPath.extRpc1Bx.format(idImg)

                        asp.cam2rpc(ASfMFunc.SubArgs_Adj2Rpc(pathImgIn, pathRpcIn, objPath.pDem, pathRpcOut, prefBA=objPath.prefEO))

                    if args.ortho:
                        procBar=ProcessStdout(name='EO ortho',inputCur=nbFeat)
                        for j in range(nbFeat):
                            procBar.ViewBar(j)
                            featCur=objBlocks.lstBFeat[iB][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathRpcOut=objPath.prefEO+'-'+objPath.extRpc1Bx.format(idImg)

                            pathOrthoOut=objPath.pOrtho.format(idImg, '-EO-RPC')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathRpcOut, objPath.pDem, pathOrthoOut, args.epsg))
                    

                if iProc <= lstProcLvl.index('eo'): continue

                #---------------------------------------------------------------
                # RPC adjust IO
                #---------------------------------------------------------------
                if args.io and not ASfMFunc.CopyPrevBA(objPath.prefEO, objPath.prefIO):
                    logger.info('# IO adjustment')
                    subArgs.IO_RPC(objPath.prefEO, objPath.prefIO, objPath, outGraph=False)

                    if args.ortho:
                        procBar=ProcessStdout(name='IO ortho',inputCur=nbFeat)
                        for j in range(nbFeat):
                            procBar.ViewBar(j)
                            featCur=objBlocks.lstBFeat[iB][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathRpcOut=objPath.prefIO+'-'+objPath.extRpc1Bx.format(idImg)

                            pathOrthoOut=objPath.pOrtho.format(idImg, '-IO-RPC')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathRpcOut, objPath.pDem, pathOrthoOut, args.epsg))

                if iProc <= lstProcLvl.index('io'): continue

                #---------------------------------------------------------------
                # Export model
                #---------------------------------------------------------------
                logger.info('# RPC export')
                if args.io:
                    lstIn=glob(objPath.prefIO+objPath.extRpc1B.format('*'))
                else:
                    lstIn=glob(objPath.prefEO+objPath.extRpc1B.format('*'))
                prefOut=objPath.pProcData+'/'
                
                procBar=ProcessStdout(name='RPC copy',inputCur=len(lstIn))
                for j in range(len(lstIn)):
                    procBar.ViewBar(j)
                    pathOut=lstIn[j].replace(objPath.prefIO+'-', prefOut)
                    cmd='cp %s %s'% (lstIn[j], pathOut)
                    os.system(cmd)
                
                if iProc <= lstProcLvl.index('exp'): continue

                #---------------------------------------------------------------
                # Final ortho
                #---------------------------------------------------------------
                logger.info('# Final ortho')
                procBar=ProcessStdout(name='Final ortho creation',inputCur=nbFeat)
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[iB][j]
                    idImg=featCur['id']
                    pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                    pathRpcIn=os.path.join(objPath.pProcData, objPath.extRpc.format(idImg))
                    print('pathRpcIn: ', pathRpcIn)
                    raise RuntimeError("Check RPC path, not tested")
                    pathOrtho=objPath.pOrtho.format(idImg, '-Final')

                    if not os.path.exists(pathOrtho): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathRpcIn, objPath.pDem, pathOrtho, args.epsg))
                    
                if iProc <= lstProcLvl.index('orthoF'): continue

            #=======================================================================
            # PM-BA
            #-----------------------------------------------------------------------
            elif args.m=='pm':
                logger.warning('PM-BA mode')
                #---------------------------------------------------------------
                # Camera creation
                #---------------------------------------------------------------
                logger.info('# Camera creation')
                procBar=ProcessStdout(name='PnP per camera',inputCur=nbFeat)
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[iB][j]
                    idImg=featCur['id']
                    pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                    pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                    pathCamRough=os.path.join(objPath.pProcData, objPath.nTsai[0].format(idImg))
                    pathCamOut=os.path.join(objPath.pProcData, objPath.nTsai[1].format(idImg))

                    # PnP, SRS 
                    if 0: # ASP no disto RPC
                        pathRpcNdisto=os.path.join(objPath.pData, objPath.extRpcNdisto.format(idImg))
                        if not os.path.exists(pathRpcNdisto): ASfMFunc.RPCwithoutDisto(idImg, pathRpcIn, pathRpcNdisto)
                        if not os.path.exists(pathCamRough): asp.cam_gen(ASfMFunc.SubArgs_Camgen(idImg, pathImgIn, pathRpcNdisto, objPath.pDem, pathCamRough, pattern='grid'))
                        if not os.path.exists(pathCamOut): ASfMFunc.ConvertPM(idImg, pathImgIn, pathCamRough, pathCamOut)

                    else: # OpenCV EPnP
                        if not os.path.exists(pathCamOut): ASfMFunc.SRS_OCV(idImg, pathImgIn, pathRpcIn, pathCamOut)
                    
                    if args.ortho:
                        pathOrthoOut=objPath.pOrtho.format(idImg, '-Init-PM')
                        if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamOut, objPath.pDem, pathOrthoOut, args.epsg))
                
                #---------------------------------------------------------------
                # EO adjustment
                #---------------------------------------------------------------
                if not ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefEO):
                    logger.info('# EO adjustment')
                    pathCnetIn=objPath.prefKP+'-cnet.csv'
                    pathCnetOut=ASfMFunc.KpCsv2Gcp(pathCnetIn, objPath.prefEO, accuXYZ=8, accuI=1, nbPts=3)

                    asp.parallel_bundle_adjust(subArgs.EO_PM(objPath.pProcData, objPath.prefEO, pathCnetOut))
                    ASfMFunc.KpCsv2Geojson(objPath.prefEO)
                    
                    if args.ortho:
                        procBar=ProcessStdout(name='EO ortho',inputCur=nbFeat)
                        for j in range(nbFeat):
                            procBar.ViewBar(j)
                            featCur=objBlocks.lstBFeat[iB][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathCamIn=glob(objPath.prefEO+'-*'+objPath.nTsai[1].format(idImg))[0]

                            # Ortho
                            pathOrthoOut=objPath.pOrtho.format(idImg, '-EO-PM')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamIn, objPath.pDem, pathOrthoOut, args.epsg))
                    
                if iProc <= lstProcLvl.index('eo'): continue

                #---------------------------------------------------------------
                # IO adjustment
                #---------------------------------------------------------------
                if args.io and not ASfMFunc.CopyPrevBA(objPath.prefEO, objPath.prefIO, kp='clean'):
                    logger.info('# IO adjustment')
                    pathCnetIn=glob(objPath.prefEO+'*.gcp')[0]
                    pathCnetOut=pathCnetIn.replace(objPath.prefEO, objPath.prefIO)
                    os.system('cp %s %s'% (pathCnetIn, pathCnetOut))

                    asp.parallel_bundle_adjust(subArgs.IO_PM(objPath.prefEO, objPath.prefIO, pathCnetOut))
                    ASfMFunc.KpCsv2Geojson(objPath.prefIO)
                    
                    if args.ortho:
                        procBar=ProcessStdout(name='IO ortho',inputCur=nbFeat)
                        for j in range(nbFeat):
                            procBar.ViewBar(j)
                            featCur=objBlocks.lstBFeat[iB][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathCamIn=glob(objPath.prefIO+'-*'+objPath.nTsai[1].format(idImg))[0]

                            # Ortho
                            pathOrthoOut=objPath.pOrtho.format(idImg, '-IO-PM')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamIn, objPath.pDem, pathOrthoOut, args.epsg))
                    
                
                if iProc <= lstProcLvl.index('io'): continue

                #---------------------------------------------------------------
                # Export cam
                #---------------------------------------------------------------
                logger.info('# PM export')
                procBar=ProcessStdout(name='Camera copy',inputCur=nbFeat)
                lstCtlCam=[]
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[iB][j]
                    idImg=featCur['id']
                    if args.io:
                        pathCamIn=glob(objPath.prefIO+'-*'+objPath.nTsai[1].format(idImg))[0]
                    else:
                        pathCamIn=glob(objPath.prefEO+'-*'+objPath.nTsai[1].format(idImg))[0]
                    pathCamOut=os.path.join(objPath.pProcData, objPath.nTsai[2].format(idImg))
                    os.system('cp %s %s'% (pathCamIn, pathCamOut))
                    
                print()
                
                if iProc <= lstProcLvl.index('exp'): continue

                #---------------------------------------------------------------
                # Final ortho
                #---------------------------------------------------------------
                logger.info('# Final ortho')
                procBar=ProcessStdout(name='Final ortho creation',inputCur=nbFeat)
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[iB][j]
                    idImg=featCur['id']
                    pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                    pathCamIn=os.path.join(objPath.pProcData, objPath.nTsai[2].format(idImg))
                    
                    pathOrthoOut=objPath.pOrtho.format(idImg, '-Final')
                    asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamIn, objPath.pDem, pathOrthoOut, args.epsg))
                    
                if iProc <= lstProcLvl.index('orthoF'): continue
              
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

        parser.add_argument('-m', default='pm', help='BA mode RPC|PM (default: RPC)')
        parser.add_argument('-p', default='orthoF', help='Process last step (read, data, orthoI, kp, eo, io, exp, orthoF)')

        # Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: False means all)')
        parser.add_argument('-ortho',action='store_true', help='Compute orthophoto of itermediate steps (default: False)')
        parser.add_argument('-io',action='store_false', help='Adjust intrinsic parameter during BA, only principal point (default: True)')
        parser.add_argument('-epsg', default='32611', help='Current ESPG used by initial ortho (default: 32611)')

        argsMain = parser.parse_args()
        
        Main(argsMain)

        print('\nEND, Continue with dense matching')
        

