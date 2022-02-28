#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from glob import glob
import json
import rasterio
from pprint import pprint


# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import DockerLibs, ASfMFunc

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task
Run bundle adjustment tasks of existing blocks. The creation of initial 
and final orthophoto allows the user to controle the block adjustment.
Moreover, ortho can be requested at every adjustment steps: -ortho.
The standard mode (PM: physical model) allows extrainsic and intrinsic 
refinements. The second one can be skiped with -io argument A RPC 
adjustment is written but it only adjusts extrinsic parameters and store 
the new RPC. That method is not recommended during dense matching projects.
A "resume" option in hard coded and allows new runs to restart from 
the last stop. File has to be deleted to avoid it.

**************************************************************************
> Read existing blocks
> Create single band images (green band)
> Create initial orthophotos from RPC
> Extract tie points (key points)
> Run fixed adjustment fixing multi-obs points and input DEM height to them
PM mode:
> Transform RPCs to PMs
> Adjust extrinsic parameters with GCP from RPC key points
> Adjust intrinsic parameters with larger weight on extrinsics
> Export camera models
> Create final orthophoto
RPC mode:
> Adjust RPCs with GCP from RPC key points
> Create adjusted RPCs
> Export camera models
> Create final orthophoto

**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
global procBar

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
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM) with ellipsoidal height (WGS84)')
        parser.add_argument('-epsg', required=True, help='Current ESPG used by initial ortho')

        parser.add_argument('-m', default='pm', help='BA mode rpc|pm (default: pm)')
        parser.add_argument('-p', default='orthoF', help='Process last step (read, data, orthoI, camI, kp, eo, io, exp, orthoF)')

        # Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: False means all)')
        parser.add_argument('-ortho',action='store_true', help='Compute orthophoto of itermediate steps (default: False)')
        parser.add_argument('-io',action='store_false', help='Adjust intrinsic parameter during BA, only principal point (default: True)')
        

        args = parser.parse_args()

        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        with rasterio.open(args.dem) as fileIn: 
            if not fileIn.crs==4326: raise RuntimeError("DEM EPSG must be 4326 (WGS 84, geographic)")
        
        pathAoi=glob(os.path.join(args.i,'*_AOI.geojson'))[0]
        if not os.path.isfile(pathAoi): raise RuntimeError("Incorrect block, AOI file not found")
        with open(pathAoi) as fileIn:
            jsonAoi=json.load(fileIn)
            if not jsonAoi['crs']['properties']['name']=="urn:ogc:def:crs:OGC:1.3:CRS84": raise RuntimeError("AOI shape must be 4326 (WGS 84, geographic)")
            geomAoi=jsonAoi['features'][0]

        if not args.m in ('rpc','pm'): raise RuntimeError("BA mode unknown")
        lstProcLvl=('read', 'data', 'orthoI', 'camI', 'kp', 'eo', 'io', 'exp', 'orthoF')
        if not args.p in lstProcLvl: raise RuntimeError("Last process step unknown")
        iProc=lstProcLvl.index(args.p)

        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        print()
        
        msg='Are you sure to run RPC-BA with intrinsic adjustment? ([0]|1)'
        if args.m=='rpc' : raise RuntimeError("RPC-BA is not stable yet (alti RPC and IO not available)") # and args.io and not input(msg)

        #---------------------------------------------------------------
        # Docker Python interface
        #---------------------------------------------------------------
        logger.info('# Docker Python interface')        
        asp=DockerLibs.AspPython()
        gdal=DockerLibs.GdalPython()
        
        #---------------------------------------------------------------
        # Read Repo
        #---------------------------------------------------------------
        logger.info('# Read Repo')
        logger.info(geomAoi['properties']['NAME'])
        objInfo=SceneBlocks(args.i)
        if not objInfo.nbB: raise RuntimeError('No block available')
        
        #---------------------------------------------------------------
        # Loop per block
        #---------------------------------------------------------------
        logger.info('# Action per block')
        if args.b:
            lstBId=[objInfo.lstBId.index(blockCur) for blockCur in objInfo.lstBId if blockCur[0] in args.b]
        else: 
            lstBId=range(objInfo.nbB)
        
        for iB in lstBId:
            if 'objBlocks' in locals(): del objBlocks, objPath
            #---------------------------------------------------------------
            # Block Setup
            #---------------------------------------------------------------
            nameB, nbFeat=objInfo.lstBId[iB]
            logger.info('%s (%i scenes)'% objInfo.lstBId[iB])
            objBlocks=SceneBlocks(args.i, meth='dir', b=nameB)
            objPath=PathCur(args.i, nameB, geomAoi['properties']['NAME'])
            


            if iProc <= lstProcLvl.index('read'): continue

            #---------------------------------------------------------------
            # Process data 
            #---------------------------------------------------------------
            logger.info('# Process data')

            procBar=ProcessStdout(name='Single band data creation',inputCur=nbFeat)
            for j in range(nbFeat):
                procBar.ViewBar(j)
                featCur=objBlocks.lstBFeat[0][j]
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
                featCur=objBlocks.lstBFeat[0][j]
                idImg=featCur['id']
                pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                pathOrtho=objPath.pOrtho.format(idImg, '-Init')

                if not os.path.exists(pathOrtho): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, 
                                                                                        pathRpcIn, 
                                                                                        args.dem, 
                                                                                        pathOrtho, 
                                                                                        args.epsg))
                

            if iProc <= lstProcLvl.index('orthoI'): continue

            #---------------------------------------------------------------
            # Camera creation
            #---------------------------------------------------------------
            if args.m=='pm':
                logger.warning('PM-BA mode')
                
                logger.info('# Camera creation')
                procBar=ProcessStdout(name='PnP per camera',inputCur=nbFeat)
                
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[0][j]
                    idImg=featCur['id']
                    pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                    pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                    pathCamRough=os.path.join(objPath.pProcData, objPath.nTsai[0].format(idImg))
                    pathCamOut=os.path.join(objPath.pProcData, objPath.nTsai[1].format(idImg))

                    # PnP, SRS 
                    if 0: # ASP PnP
                        raise RuntimeError('ASP PnP not up-to-date, check the DEM (RPCs use alti ?)')
                        pathRpcNdisto=os.path.join(objPath.pData, objPath.extRpcNdisto.format(idImg))
                        # ASP no disto RPC
                        if not os.path.exists(pathRpcNdisto): ASfMFunc.AspPnP_RPCwithoutDisto(idImg, pathRpcIn, pathRpcNdisto)
                        # ASP cam_gen
                        if not os.path.exists(pathCamRough): asp.cam_gen(ASfMFunc.AspPnP_SubArgs_Camgen(idImg, pathImgIn, pathRpcNdisto, args.dem, pathCamRough, pattern='grid'))
                        # PM rough to init
                        if not os.path.exists(pathCamOut): ASfMFunc.AspPnP_ConvertPM(idImg, pathImgIn, pathCamRough, pathCamOut)

                    else: # OpenCV EPnP
                        if not os.path.exists(pathCamOut): ASfMFunc.PnP_OCV(idImg, pathRpcIn, pathCamOut)

                        
                    if args.ortho:
                        pathOrthoOut=objPath.pOrtho.format(idImg, '-Init-PM')
                        if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamOut, args.dem, pathOrthoOut, args.epsg))
            else:
                logger.warning('RPC-BA mode')
            if iProc <= lstProcLvl.index('camI'): continue

            #---------------------------------------------------------------
            # Bundle adjustment series
            #---------------------------------------------------------------
            ASfMFunc.StereoDescriptor(objPath, objBlocks.lstBCouple[0])
            
            lstImgId=[feat['id'] for feat in objBlocks.lstBFeat[0]]
            subArgs=ASfMFunc.SubArgs_BunAdj(objPath.pStereoLst,
                                            objPath.pProcData,
                                            objPath.pData,
                                            lstImgId,
                                            objPath.extFeat1B,
                                            objPath.extRpc,
                                            objPath.extRpc1B,
                                            objPath.nTsai[1], 
                                            args.m)

            #---------------------------------------------------------------
            # Key point extraction
            #---------------------------------------------------------------
            if not os.path.exists(objPath.prefKP+'-cnet.csv'):
                logger.info('# Key point')
                folderKP=os.path.dirname(objPath.prefKP)
                if not os.path.exists(folderKP): os.mkdir(folderKP)
                folderSKP=os.path.dirname(objPath.prefStereoKP)
                if os.path.exists(folderSKP): os.system('rm -r %s'% folderSKP)

                # Feature extraction (stereo)
                nbComb=len(objBlocks.lstBCouple[0])
                lstIPair=[j for j in range(nbComb) 
                            if objBlocks.lstBCouple[0][j]['properties']['nbScene']==2]

                procBar=ProcessStdout(name='Feature extraction',inputCur=len(lstIPair))
                #logger.error('No KP extraction')
                #for i in ():
                for j in lstIPair:
                    procBar.ViewBar(j)
                    strId=objBlocks.lstBCouple[0][j]['properties']['scenes']
                    lstId=sorted(strId.split(';'))

                    basenameMatch='__'.join([objPath.extFeat1B.format(idCur).split('.')[0] for idCur in lstId])
                    pathMatch=objPath.prefKP+'-'+basenameMatch+'.match'
                    if os.path.exists(pathMatch): continue
                    if os.path.exists(pathMatch+'null'): continue
                    
                    lstPath, outMask=[], 0

                    for idCur in lstId:
                        pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idCur))
                        pathImgOut=os.path.join(objPath.pProcData, objPath.extFeatKP.format(idCur))
                        pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idCur))
                        pathRpcOut=os.path.join(objPath.pProcData, objPath.extRpcKP.format(idCur))
                        out=ASfMFunc.MaskedImg_KP( pathImgIn, 
                                                    pathRpcIn, 
                                                    args.dem, 
                                                    objBlocks.lstBCouple[0][j]['geometry'],
                                                    pathImgOut=pathImgOut)
                        if not type(out)==bool: outMask+=out

                        # RPC copy
                        cmd='cp %s %s'% (pathRpcIn, pathRpcOut)
                        os.system(cmd)

                        lstPath.append((pathImgOut, pathRpcOut))

                    # KP grid
                    softLvl=-1
                    while not outMask and ASfMFunc.CopyPrevBA(objPath.prefStereoKP, objPath.prefKP, kp='disp', dispExists=True, dirExists=False, img=False) and softLvl<3:
                        softLvl+=1
                        asp.parallel_stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath.prefStereoKP, lstPath, softness=softLvl))
                    
                    # KP sparse + check (with '--stop-point', '2')
                    if softLvl==3 and not os.path.exists(pathMatch): 
                        softLvl=-1
                        while not outMask and ASfMFunc.CopyPrevBA(objPath.prefStereoKP, objPath.prefKP, kp='match', dispExists=True, dirExists=False, img=False) and softLvl<1:
                            softLvl+=1
                            asp.parallel_stereo(ASfMFunc.SubArgs_StereoKP_RPC(objPath.prefStereoKP, lstPath, softness=softLvl)+['--stop-point', '2'])

                    if softLvl==1 and not os.path.exists(pathMatch): 
                        with open(pathMatch+'null', 'wb') as fileOut:
                            fileOut.write(bytearray())
                        logger.warning('Check feature: %s'% str(lstId))

                    # Remove KP files
                    cmd='rm '+' '.join([' '.join(tupCur) for tupCur in lstPath])
                    os.system(cmd)
                    if os.path.exists(folderSKP): os.system('rm -r %s'% folderSKP)
                    # Clean Docker system /!\ If parallel process, it prunes all existing containers
                    os.popen('sudo docker container prune --force ; sudo docker volume prune --force')

                print()
                # Fixed bundle adjustment: Initial residuals
                asp.parallel_bundle_adjust(subArgs.KP_RPC(objPath.pProcData, 
                                                          objPath.prefKP, 
                                                          args.dem), boolConv=False)
                ASfMFunc.KpCsv2Geojson(objPath.prefKP)
                
            else:
                logger.error('%s folder already full (skipped)'% os.path.basename(objPath.prefKP))
            
            if iProc <= lstProcLvl.index('kp'): continue

            #=======================================================================
            # RPC-BA
            #-----------------------------------------------------------------------
            if args.m=='rpc':
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
                        featCur=objBlocks.lstBFeat[0][j]
                        idImg=featCur['id']
                        pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                        pathRpcIn=os.path.join(objPath.pData, objPath.extRpc.format(idImg))
                        pathRpcOut=objPath.prefEO+'-'+objPath.extRpc1Bx.format(idImg)

                        asp.cam2rpc(ASfMFunc.SubArgs_Adj2Rpc(pathImgIn, pathRpcIn, objPath.pDem, pathRpcOut, prefBA=objPath.prefEO))

                    if args.ortho:
                        procBar=ProcessStdout(name='EO ortho',inputCur=nbFeat)
                        for j in range(nbFeat):
                            procBar.ViewBar(j)
                            featCur=objBlocks.lstBFeat[0][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathRpcOut=objPath.prefEO+'-'+objPath.extRpc1Bx.format(idImg)

                            pathOrthoOut=objPath.pOrtho.format(idImg, '-EO-RPC')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathRpcOut, objPath.pDem, pathOrthoOut, args.epsg))
                    

                if iProc <= lstProcLvl.index('eo'): continue

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
                    featCur=objBlocks.lstBFeat[0][j]
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
                #---------------------------------------------------------------
                # EO adjustment
                #---------------------------------------------------------------
                if not ASfMFunc.CopyPrevBA(objPath.prefKP, objPath.prefEO):
                    logger.info('# EO adjustment')
                    pathCnetIn=objPath.prefKP+'-cnet.csv'
                    pathCnetOut=ASfMFunc.KpCsv2Gcp(pathCnetIn, objPath.prefEO, accuXYZ=10, accuI=1, nbPts=int(round(nbFeat*0.1)))

                    #parallel_bundle_adjust
                    asp.parallel_bundle_adjust(subArgs.EO_PM(objPath.pProcData, objPath.prefEO, pathCnetOut))
                    ASfMFunc.KpCsv2Geojson(objPath.prefEO)
                    
                    if args.ortho:
                        procBar=ProcessStdout(name='EO ortho',inputCur=nbFeat)
                        for j in range(nbFeat):
                            procBar.ViewBar(j)
                            featCur=objBlocks.lstBFeat[0][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathCamIn=glob(objPath.prefEO+'-*'+objPath.nTsai[1].format(idImg))[0]

                            # Ortho
                            pathOrthoOut=objPath.pOrtho.format(idImg, '-EO-PM')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamIn, args.dem, pathOrthoOut, args.epsg))
                    
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
                            featCur=objBlocks.lstBFeat[0][j]
                            idImg=featCur['id']
                            pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                            pathCamIn=glob(objPath.prefIO+'-*'+objPath.nTsai[1].format(idImg))[0]

                            # Ortho
                            pathOrthoOut=objPath.pOrtho.format(idImg, '-IO-PM')                    
                            if not os.path.exists(pathOrthoOut): asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamIn, args.dem, pathOrthoOut, args.epsg))
                    
                
                if iProc <= lstProcLvl.index('io'): continue

                #---------------------------------------------------------------
                # Export cam
                #---------------------------------------------------------------
                logger.info('# PM export')
                procBar=ProcessStdout(name='Camera copy',inputCur=nbFeat)
                lstCtlCam=[]
                for j in range(nbFeat):
                    procBar.ViewBar(j)
                    featCur=objBlocks.lstBFeat[0][j]
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
                    featCur=objBlocks.lstBFeat[0][j]
                    idImg=featCur['id']
                    pathImgIn=os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg))
                    pathCamIn=os.path.join(objPath.pProcData, objPath.nTsai[2].format(idImg))
                    
                    pathOrthoOut=objPath.pOrtho.format(idImg, '-Final')
                    asp.mapproject(ASfMFunc.SubArgs_Ortho(pathImgIn, pathCamIn, args.dem, pathOrthoOut, args.epsg))
                    
                if iProc <= lstProcLvl.index('orthoF'): continue
              
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
        
        

