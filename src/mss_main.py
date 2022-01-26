#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from datetime import datetime
from pprint import pprint
from glob import glob
import rasterio
import json
from multiprocessing import Pool

# PyValLib packages
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import DockerLibs, MSSFunc, GeomFunc, ASfMFunc

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
global procBar
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

def FailedDM(pathFile, lstPrefClean=None):
    #logger.error('%s failed'% os.path.basename(pathFile))
    with open(pathFile, 'w') as fileOut:
        fileOut.write('Failed')

    if lstPrefClean: os.system(cmd='rm' +'-* '.join(lstPrefClean)+'-* ')

    
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
        parser.add_argument('-epsg', required=True, help='Current ESPG used by output projection')
        
        #Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: [] means all')
        #parser.add_argument('-debug',action='store_true',help='Debug mode: avoid planet_common check')

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
            geomAoiLoc=MSSFunc.ReprojGeom(geomAoi, args.epsg)
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()

        #---------------------------------------------------------------
        # Docker Python interface
        #---------------------------------------------------------------
        logger.info('# Docker Python interface')        
        asp=DockerLibs.AspPython()
        pdal=DockerLibs.PdalPython()
        gdal=DockerLibs.GdalPython()
        
        #---------------------------------------------------------------
        # Read Repo
        #---------------------------------------------------------------
        logger.info('# Read Repo')
        logger.info(geomAoi['properties']['NAME'])
        objInfo=SceneBlocks([], args.i, 'info')
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
            objBlocks=SceneBlocks([], args.i, 'dir', b=nameB)
            objPath=PathCur(args.i, nameB, geomAoi['properties']['NAME'])

            MSSFunc.PdalJson(objPath)
            
            #---------------------------------------------------------------
            # Dense matching pairwise
            #---------------------------------------------------------------
            logger.info('# Dense matching')
            # Stereo pairs
            lstIPair=[j for j in range(len(objBlocks.lstBCouple[0])) 
                            if objBlocks.lstBCouple[0][j]['properties']['nbScene']==2]

            procBar=ProcessStdout(name='Dense maching per stereo pair',inputCur=len(lstIPair))
            for j in lstIPair:
                procBar.ViewBar(j)
                strJ=str(j).rjust(5,'0')

                strId=objBlocks.lstBCouple[0][j]['properties']['scenes']
                lstId=sorted(strId.split(';'))
                
                #---------------------------------------------------------------
                # Filter process
                #---------------------------------------------------------------
                # Exists
                pathPCout=objPath.prefStereoDM+objPath.extPC.format(strJ)
                if os.path.exists(pathPCout): continue
                
                # Ascending/Descending
                #lstSatAz=[]
                #for idCur in lstId:
                #    for i in range(nbFeat):
                #        featCur=objBlocks.lstBFeat[0][i]
                #        if not idCur==featCur['id']: continue
                #        if not 'sat:satellite_azimuth_mean_deg' in featCur['properties']: continue
                #        lstSatAz.append(featCur['properties']['sat:satellite_azimuth_mean_deg'])
                #if len(lstSatAz)==2:
                #    lstSatAzDiff=[[abs(az-azRef)//satAz_Tol for azRef in satAz_Val] for az in lstSatAz]
                #    if not all([0 in tup for tup in lstSatAzDiff]): raise RuntimeError('Input satellite azimut not interpreted (stereopair %i): %s (+/-%i)'% (j, str(lstSatAz), satAz_Tol))
                #    setSatOri=set([satAz_Name[tup.index(0)] for tup in lstSatAzDiff])
                #    
                #    #if not len(setSatOri)==1: continue
                #    #if 'ascending' in setSatOri: continue
                
                #logger.info('j: %i'% j)
                #if not input('Ready? (1/0)'): continue
                #if not j in (0,1,2,3,4,5): continue
                #if 0:
                #---------------------------------------------------------------
                # Left or Right Ref
                #---------------------------------------------------------------
                if glob(objPath.prefProcDM+'*'): os.system('rm %s*'% objPath.prefProcDM)
                tupPref=(objPath.prefProcDM+'Left', objPath.prefProcDM+'Right')
                tupLstPath=([(os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg)),
                                                      os.path.join(objPath.pProcData, objPath.nTsai[2].format(idImg)),
                                                        )
                                                            for idImg in lstId],
                            [(os.path.join(objPath.pProcData, objPath.extFeat1B.format(idImg)),
                                                       os.path.join(objPath.pProcData, objPath.nTsai[2].format(idImg)),
                                                        )
                                                            for idImg in sorted(lstId, reverse=True)]
                            )
                #---------------------------------------------------------------
                # Epipolar images
                #---------------------------------------------------------------
                #if 0:
                epipMode=True
                prepaProc=MSSFunc.EpipPreProc( tupLstPath[0], 
                                            objBlocks.lstBCouple[0][j]['geometry'], 
                                            args.dem,  
                                            tupPref[0],
                                            epip=epipMode,
                                            )
                    
                # Does not attempt though matches yet
                if prepaProc:
                    FailedDM(pathPCout)
                    continue

                #---------------------------------------------------------------
                # Disparities
                #---------------------------------------------------------------
                out=0
                for i in range(2):
                    prefOut=tupPref[i]
                    lstPath=tupLstPath[i]
                    
                    out+=asp.parallel_stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=epipMode)+['--stop-point', '5',]) 
                    
                    if out: break
                    
                    nameImgASP=(('-L.tif', '-L.tsai', '-lMask.tif', '-L_sub.tif', '-lMask_sub.tif'),
                             ('-R.tif', '-R.tsai', '-rMask.tif', '-R_sub.tif', '-rMask_sub.tif'))[::1-2*i]
                    cmd=[]
                    for k in range(2):
                        for l in range(5):
                            ext=''
                            if not k: ext='tmp'
                            cmd.append('mv %s %s'% (tupPref[i]+nameImgASP[k][l], tupPref[(i-1)%2]+nameImgASP[(k-1)%2][l]+ext))
                    cmd+=['mv %s %s'% (cmd[l].split()[-1], cmd[l].split()[-1][:-3]) for l in range(5)]
                    os.system(' ; '.join(cmd))
                    
                if out: 
                    FailedDM(pathPCout, lstPrefClean=tupPref)
                    continue
                #---------------------------------------------------------------
                # merge Disparities
                #---------------------------------------------------------------
                prefOut=tupPref[0]
                lstPath=tupLstPath[0]

                pathDispMean=MSSFunc.MergeDisparities(tupPref[0], tupPref[1])
                if not pathDispMean: 
                    FailedDM(pathPCout, lstPrefClean=tupPref)
                    continue
                gdal.gdal_translate(['-if', '"EXR"', pathDispMean.replace('.tif','.exr'), pathDispMean])
                
                out=asp.parallel_stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=epipMode)+['--entry-point', '5',])
                
                pathPC=prefOut+'-PC.tif'
                if not os.path.exists(pathPC): 
                    FailedDM(pathPCout, lstPrefClean=tupPref)
                    continue

                #asp.point2dem(MSSFunc.SubArgs_P2D(pathPC, args.epsg))        
                #os.system('mv %s %s'% (prefOut+'-DEM.tif', objPath.prefStereoDM+'-DEM-%i.tif'% j,))
                
                #---------------------------------------------------------------
                # Save Process
                #---------------------------------------------------------------
                pathTxt=MSSFunc.AspPc2Txt(pathPC)
                if type(pathTxt)==int: 
                    FailedDM(pathPCout, lstPrefClean=tupPref)
                    continue
                
                subArgs=[objPath.pJsonSource,
                         '--readers.text.filename=%s'% pathTxt,
                         '--writers.las.filename=%s'% pathPCout,
                         '--filters.reprojection.out_srs="EPSG:%s"'% args.epsg,
                         '--stage.source.value="PointSourceId=%i"'% (j+1),
                         '--stage.angle.value="ScanAngleRank=%i"'% int(round(MSSFunc.BRratio(lstPath[0][1], lstPath[1][1], atype='deg'))),
                         ]
                pdal.pipeline(subArgs)
                
                #---------------------------------------------------------------
                # Clean folder
                #---------------------------------------------------------------
                cmd='rm ' +'-* '.join(tupPref)+'-* '
                os.system(cmd)
            

               
            #---------------------------------------------------------------
            # Point cloud summary
            #---------------------------------------------------------------
            logger.warning('# Point cloud summary')

            lstPCpath=glob(objPath.prefStereoDM+objPath.extPC.format('*'))
            lstPCpath.sort()
            nbFile=len(lstPCpath)

            procBar=ProcessStdout(name='Summary computation',inputCur=len(lstPCpath))
            lstPCiEmpty=[]
            nbPts, lstBounds=0, False
            for i in range(nbFile):
                procBar.ViewBar(i)
                
                pathPc=lstPCpath[i]
                
                # Exists
                fileEncode=os.popen('file --mime-encoding %s'% pathPc).read()
                if not fileEncode.strip().split(':')[-1]==' binary':
                    lstPCiEmpty.append(i)
                    continue

                # Nb points
                jsonInfo=pdal.info(['--summary', pathPc])
                if type(jsonInfo)==int or not jsonInfo['summary']['num_points']:
                    lstPCiEmpty.append(i)
                    continue
                nbPts+=jsonInfo['summary']['num_points']

                # Boundaries
                bnds=jsonInfo['summary']['bounds']
                if not lstBounds:
                    lstBounds=[bnds['minx'], bnds['miny'], bnds['maxx'], bnds['maxy']]
                else:
                    lstBounds[0]=min(lstBounds[0],bnds['minx'])
                    lstBounds[1]=min(lstBounds[1],bnds['miny'])
                    lstBounds[2]=max(lstBounds[2],bnds['maxx'])
                    lstBounds[3]=max(lstBounds[3],bnds['maxy'])

            [lstPCpath.pop(i-j) for j,i in enumerate(lstPCiEmpty)]
            
            checkMerged, coordMid=MSSFunc.PC_Summary(lstPCpath, lstPCiEmpty, lstBounds, nbPts, objPath.pPcFullList)
            
            #---------------------------------------------------------------
            # Point cloud tiling
            #---------------------------------------------------------------
            grepTile=objPath.pPcFullTile.replace('#', '*')
            if not checkMerged:
                logger.info('# Point cloud tiling')
                with open(objPath.pPcFullList, 'w') as fileOut:
                    fileOut.writelines([line+'\n' for line in lstPCpath])

                # Clear folder
                if glob(grepTile): os.system('rm %s'% grepTile)
                
                # Link to correct files
                prefLink=os.path.join(objPath.pPcFullDir, os.path.basename(objPath.prefStereoDM))
                [os.system('ln -s %s %s'% (pathPC, pathPC.replace(objPath.prefStereoDM, prefLink))) 
                            for pathPC in lstPCpath]
                
                subArgs=['"%s*"'% prefLink,
                         '"%s"'% objPath.pPcFullTile,
                         '--out_srs="EPSG:%s"'% args.epsg,
                         '--length', '1000', # cell length
                         '--buffer', str(2*gsdDsm+gsdDsm/2),
                         '--origin_x', str(coordMid[0]),
                         '--origin_y', str(coordMid[1]),
                         ]
                pdal.tile(subArgs)
                
                os.system('rm %s*'% prefLink)
            
            if os.path.exists(objPath.pPcFullTile.replace('#', '0_0')):
                MSSFunc.FilterTiles(coordMid, 
                                    glob(grepTile), 
                                    objPath.pPcFullTile,
                                    geomAoiLoc)
            
            lstTilePath=glob(grepTile)
            lstTilePath.sort()
            nbTile=len(lstTilePath)
            logger.info('%i point cloud tiles'% nbTile)
            
            raise RuntimeError("Point coud processes - Check parallel processes and gobal var")
            #---------------------------------------------------------------
            # Point cloud filtering
            #---------------------------------------------------------------
            logger.warning('# Point cloud filtering')

            strTemplate=objPath.pPcFullTile.split('#')
            procBar=ProcessStdout(name='filtering per tile',inputCur=nbTile//os.cpu_count()+nbTile%os.cpu_count())
            def Filtering(i):
                procBar.ViewBar(i)
                pathIn=lstTilePath[i]
                strIndexIn=pathIn.replace(strTemplate[0],'').replace(strTemplate[1],'')
                pathOut=objPath.pPcFltTile.format(strIndexIn)
                if os.path.exists(pathOut): return 0

                subArgs=[objPath.pJsonFilter,
                        '--readers.las.filename=%s'% pathIn,
                        '--writers.las.filename=%s'% pathOut]
                return pdal.pipeline(subArgs)
            
            os.system('date')
            with Pool(None) as poolCur:
                poolCur.map(Filtering, list(range(nbTile)))
                print()
            os.system('date')

            lstTilePath=glob(objPath.pPcFltTile.format('*'))
            lstTilePath.sort()
            nbTile=len(lstTilePath)
            sys.exit()
            #---------------------------------------------------------------
            # Point cloud rasterize
            #---------------------------------------------------------------
            logger.warning('# Point cloud merging')
            
            strTemplate=objPath.pPcFltTile.split('{}')
            
            procBar=ProcessStdout(name='Rasterizing per tile',inputCur=nbTile//os.cpu_count()+nbTile%os.cpu_count())
            def RasterizeTiles(i):
                global strTemplate, procBar, lstTilePath, objPath, pdal, MSSFunc
                if j: time.sleep((os.getpid()-os.getppid())%2)
                procBar.ViewBar(i)
                pathIn=lstTilePath[i]
                strIndexIn=pathIn.replace(strTemplate[0],'').replace(strTemplate[1],'')
                pathOut=objPath.pDsmTile.format(strIndexIn)
                if os.path.exists(pathOut): return 0
                indexIn=[int(s) for s in strIndexIn.split('_')]
            
                return MSSFunc.PC2Raster( pathIn, 
                                          pathOut,
                                          indexIn,
                                          objPath.pJsonRast_WA,
                                          pdal)

            os.system('date')
            with Pool(None) as poolCur:
                poolCur.map(RasterizeTiles, list(range(nbTile)))
                print()
            os.system('date')

            #---------------------------------------------------------------
            # Tile merge
            #---------------------------------------------------------------
            lstTilePath=glob(objPath.pDsmTile.format('???_????'))
            gdal.gdal_merge(['-init', '"-32767 -32767 0"',
                             '-a_nodata', '-32767', 
                             '-o', objPath.pDsmFinal,
                             ]+lstTilePath)
            
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
