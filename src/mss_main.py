#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob

# PyValLib packages
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import ASP, MSSFunc, GeomFunc

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
featIdTest=('20210112_180848_0f15',
'20210105_180643_0f22',
    )

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
        parser.add_argument('-m', required=True, help='Dense matching method PW|MVS')
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM)')
        
        #Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: [] means all')
        #parser.add_argument('-debug',action='store_true',help='Debug mode: avoid planet_common check')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        if not args.m in methodDM: raise RuntimeError("Unknown method")
        
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
            logger.warning('# TEST MODE')
            lstTemp=[objBlocks.lstBFeat[iB][j] for j in range(objBlocks.lstBId[iB][1]) if objBlocks.lstBFeat[iB][j]['id'] in featIdTest]
            objBlocks.lstBFeat[iB]=lstTemp
            objBlocks.lstBId[iB]=(objBlocks.lstBId[iB][0], len(lstTemp))
            lstTemp=[objBlocks.lstBCouple[iB][j] for j in range(len(objBlocks.lstBCouple[iB])) if not False in [idCur in featIdTest for idCur in objBlocks.lstBCouple[iB][j]['properties']['scenes'].split(';')]]
            objBlocks.lstBCouple[iB]=lstTemp
            
            ###################
            bId, nbFeat= objBlocks.lstBId[iB]
            logger.info(bId)
            objPath=PathCur(args.i, bId, args.dem)
            
            #---------------------------------------------------------------
            # Dense matching pairwise
            #---------------------------------------------------------------
            logger.info('# Dense matching')

            for j in range(len(objBlocks.lstBCouple[iB])):
                if not objBlocks.lstBCouple[iB][j]['properties']['nbScene']==2: continue
                
                pairCur=objBlocks.lstBCouple[iB][j]
                
                # FILTER
                lstID=pairCur['properties']['scenes'].split(';')
                
                #---------------------------------------------------------------
                # Find Images 
                #---------------------------------------------------------------
                lstImgPath=[os.path.join(objPath.pProcData, objPath.extFeat1B.format(idCur)) for idCur in pairCur['properties']['scenes'].split(';')]
                if False in [os.path.exists(pathCur) for pathCur in lstImgPath]: continue
                
                #---------------------------------------------------------------
                # More images
                #---------------------------------------------------------------
                if args.m=='MVS':
                    lstFuthImgId=MSSlib_stereo.MvsAddImg(pairCur, objBlocks.lstBCouple[iB])
                    lstOfLst=[glob(os.path.join(pathDict['pProcData'], idCur+'*.tif')) for idCur in lstFuthImgId]
                    lstImgPath+=[lst[0] for lst in lstOfLst if lst]

                #---------------------------------------------------------------
                # Find camera
                #---------------------------------------------------------------
                lstCamPath=[os.path.join(objPath.pProcData, objPath.nTsai[2].format(objPath.extFeat1B.format(idCur).split('.')[0])) for idCur in pairCur['properties']['scenes'].split(';')]
                if False in [os.path.exists(pathCur) for pathCur in lstCamPath]: continue

                #input('Ready ?')
                #---------------------------------------------------------------
                # Preparation
                #---------------------------------------------------------------
                '''
                There are 2 options:
                    alignment-method epipolar> +: make use of input geometry -: must shrink the mask using the epipolar transformation parameters
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
                # Filter process
                #---------------------------------------------------------------
                perfOut=os.path.join(os.path.dirname(objPath.prefDM),'ResultDM')
                lstNameIn=('-DEM.tif', '-PC.las') #('-DEM.tif', '-IntersectionErr.tif', '-GoodPixelMap.tif', '-F.tif')
                if os.path.exists(perfOut+lstNameIn[0].replace('.', '%i.'% j)): continue
                #---------------------------------------------------------------
                # Process
                #---------------------------------------------------------------
                subArgs=MSSFunc.SubArgs_Stereo(lstImgPath, lstCamPath, objPath.prefDM)                
                out=asp.parallel_stereo(subArgs)
                
                if out or not os.path.exists(objPath.prefDM+'-PC.tif'): 
                    pprint(objBlocks.lstBCouple[iB][j]['properties'])
                    logger.error("Stereo Failed")
                    cmd='rm -r %s-*'% objPath.prefDM
                    os.system(cmd)
                    continue
                
                subArgs=MSSFunc.SubArgs_P2D(objPath.prefDM+'-PC.tif')
                asp.point2dem(subArgs)
                subArgs=MSSFunc.SubArgs_P2L(objPath.prefDM+'-PC.tif')
                asp.point2las(subArgs)
                
                #---------------------------------------------------------------
                # Save Process
                #---------------------------------------------------------------
                for nameIn in lstNameIn:
                    pathIn=objPath.prefDM+nameIn
                    if not os.path.exists(pathIn): 
                        logger.error('File not found (%s): pair %i'% (nameIn, j))
                    else:
                        cmd='mv {} {}'.format(pathIn, 
                                                    perfOut+nameIn.replace('.', '%i.'% j)
                                                    )
                        #print(cmd)
                        os.system(cmd)
                
                #input('Stereo Check')

                #---------------------------------------------------------------
                # Clean folder
                #---------------------------------------------------------------
                cmd='rm -r %s-*'% objPath.prefDM
                #print(cmd)
                os.system(cmd)
                
                #input('Next')
            

    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
