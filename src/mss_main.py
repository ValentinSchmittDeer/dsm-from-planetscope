#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from datetime import datetime
from pprint import pprint
from glob import glob
import rasterio

# PyValLib packages
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import ASP, MSSFunc, GeomFunc, ASfMFunc

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
        #parser.add_argument('-m', required=True, help='Dense matching method (pw|mvs)')
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM)')
        
        #Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: [] means all')
        parser.add_argument('-epsg', default='32611', help='Current ESPG used by DEM and point cloud creation (default: 32611)')
        #parser.add_argument('-debug',action='store_true',help='Debug mode: avoid planet_common check')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        with rasterio.open(args.dem) as fileIn: 
            if not fileIn.crs==4326: raise RuntimeError("DEM EPSG must be 4326 (WGS 84, geographic)")

        #if not args.m in ('PW', 'MVS'): raise RuntimeError("Unknown method")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()

        #---------------------------------------------------------------
        # ASP Python interface
        #---------------------------------------------------------------
        #if not args.debug:
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
            logger.info(bId)
            objPath=PathCur(args.i, bId, args.dem)

            
            #---------------------------------------------------------------
            # Dense matching pairwise
            #---------------------------------------------------------------
            logger.info('# Dense matching')
            lstIPair=[j for j in range(len(objBlocks.lstBCouple[iB])) 
                            if objBlocks.lstBCouple[iB][j]['properties']['nbScene']==2]

            logger.warning('Please check stereopair 4 (?) and 8 (asending/decending)')
            logger.warning('Add filter on asending/decending MD')
            input('Process?')
            t0=datetime.now()
            #procBar=ProcessStdout(name='Dense maching per stereo pair',inputCur=len(lstIPair))
            for j in lstIPair:
                #procBar.ViewBar(j)
                
                strId=objBlocks.lstBCouple[iB][j]['properties']['scenes']
                lstId=sorted(strId.split(';'))
                
                #---------------------------------------------------------------
                # Filter process
                #---------------------------------------------------------------
                lstNameIn=('-DEM.tif', '-PC.las') #('-DEM.tif', '-IntersectionErr.tif', '-GoodPixelMap.tif', '-F.tif')
                if os.path.exists(objPath.prefStereoDM+lstNameIn[0].replace('.', '%i.'% j)): continue
                
                # Stereo pairs
                if not len(lstId)==2 : continue
                # Intrack overlap
                #if not lstId[0].split('_')[-1]==lstId[1].split('_')[-1] : continue
                
                #if not j==4: continue
                #if j>14:
                #    logger.error('Dt: %s'% str(datetime.now()-t0))
                #    sys.exit()
                logger.error('j: %i'% j)
                #---------------------------------------------------------------
                # Preparation
                #---------------------------------------------------------------
                lstPath=[(os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg)),
                            os.path.join(objPath.pProcData, objPath.nTsai[2].format(idImg)),
                            )
                                for idImg in lstId]
                epipMode=True
                prepaProc=MSSFunc.PrepProcessDM( lstPath, 
                                    objBlocks.lstBCouple[iB][j]['geometry'], 
                                    objPath.pDem,  
                                    objPath.prefProcDM,
                                    epip=epipMode)
                
                if prepaProc:
                    logger.error('Epip images larger than RAM not managed yet')
                    continue
                    epipMode=False
                    prepaProc=MSSFunc.PrepProcessDM( lstPath, 
                                        objBlocks.lstBCouple[iB][j]['geometry'], 
                                        objPath.pDem,  
                                        objPath.prefProcDM,
                                        epip=False)
                #input('Ready DM')
                #---------------------------------------------------------------
                # Process
                #---------------------------------------------------------------            
                out=asp.stereo(MSSFunc.SubArgs_Stereo(lstPath, objPath.prefProcDM, epip=epipMode))
                
                if out or not os.path.exists(objPath.prefProcDM+'-PC.tif'): 
                    pprint(objBlocks.lstBCouple[iB][j]['properties'])
                    logger.error("Stereo failed")
                    cmd='rm -r %s-*'% objPath.prefProcDM
                    os.system(cmd)
                    continue
                
                asp.point2las(MSSFunc.SubArgs_P2L(objPath.prefProcDM+'-PC.tif', args.epsg))
                asp.point2dem(MSSFunc.SubArgs_P2D(objPath.prefProcDM+'-PC.tif', args.epsg))
                
                #---------------------------------------------------------------
                # Save Process
                #---------------------------------------------------------------
                for nameIn in lstNameIn:
                    pathIn=objPath.prefProcDM+nameIn
                    if not os.path.exists(pathIn): 
                        logger.error('File not found (%s): pair %i'% (nameIn, j))
                    else:
                        cmd='mv {} {}'.format(pathIn, 
                                              objPath.prefStereoDM+nameIn.replace('.', '%i.'% j)
                                                    )
                        #print(cmd)
                        os.system(cmd)
                #input('Next DM')
                #---------------------------------------------------------------
                # Clean folder
                #---------------------------------------------------------------
                # Correlation files
                cmd='rm -r %s-*'% objPath.prefProcDM
                os.system(cmd)

            

    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
