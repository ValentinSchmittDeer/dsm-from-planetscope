#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time, copy
from glob import glob
import rasterio
import json
from multiprocessing import Pool
from pprint import pprint

# PyValLib packages
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc import DockerLibs, MSSFunc

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task
Run reconstruction process based on stereo pairs. Dense matching results
are stored into point cloud which are then gathered per tiles. Additional 
filters from PDAL classify points based on the morphology. Complete tiles
are rasterized by weighted average. A final merge creates one file from 
all tiles.

**************************************************************************
> Read existing blocks
> Select stereo pair to match (preparation)
> Create epipolar images of the current stereo pair
> Match epipolar images
> Match the inverse pair (left image becomes right image and right becomes left)
> Merge disparity results
> Triangulate points
> Convert point cloud into .las format
> Record the computed geometry
> Recap existing point clouds
> Tile gathering clouds
> Filter tiles
> Rasterize tiles
> Merge raster tiles

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

def FailedDM(pathFile, j,lstPrefClean=None):
    logger.warning('Error occured with stereopair ID %s'% j)
    with open(pathFile, 'w') as fileOut:
        fileOut.write('Failed')

    if lstPrefClean: os.system('rm ' +'-* '.join(lstPrefClean)+'-* ')

    
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
            geomAoiLoc=copy.deepcopy(geomAoi)
            MSSFunc.ReprojGeom(geomAoiLoc, args.epsg)
            

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
        objInfo=SceneBlocks(args.i)
        if not objInfo.nbB: raise RuntimeError('No block available')
        logger.info(str(objInfo))

        #---------------------------------------------------------------
        # Loop per block
        #---------------------------------------------------------------
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

            MSSFunc.PdalJson(objPath)
            
            #---------------------------------------------------------------
            # Dense matching preparation, filtering
            #---------------------------------------------------------------
            logger.info('# Stereo pair dense matching ')
            lstIPair=[]
            nbPair=len(objBlocks.lstBCouple[0]) 
            procBar=ProcessStdout(name='Dense maching preparation',inputCur=nbPair)
            for j in range(nbPair) :
                procBar.ViewBar(j)
                strJ=str(j).rjust(5,'0')
                pathPcLas=objPath.prefStereoDM+objPath.extPC.format(strJ)
                if not MSSFunc.FilterDmProces(objBlocks.lstBFeat[0],
                                              objBlocks.lstBCouple[0][j],
                                              pathPcLas,
                                              os.path.join(objPath.pProcData, objPath.nTsai[2]), 
                                              geomAoi['geometry']): continue          

                lstIPair.append(j)

            lstCouple=[objBlocks.lstBCouple[0][j] for j in lstIPair]
            del objBlocks.lstBCouple[0]
            objBlocks.lstBCouple.append(lstCouple)
            del lstCouple
            nbPair=len(objBlocks.lstBCouple[0])
            logger.info('%i stereo pair in process'% nbPair)

            for j in range(nbPair):
                objBlocks.lstBCouple[0][j]['properties']['DmProcess']=False
            
            if not os.path.exists(objPath.pStereoDM):
                objGeojsonSDM=tempGeojson.copy()
                objGeojsonSDM["name"]=os.path.basename(objPath.pStereoDM).split('.')[0]
            else:
                with open(objPath.pStereoDM) as fileIn:
                    objGeojsonSDM=json.load(fileIn)
                lstJnew=[feat['id'] for feat in objBlocks.lstBCouple[0]]
                lstJdel=[]
                for j in range(len(objGeojsonSDM["Features"])):
                    if not objGeojsonSDM["Features"][j]['id'] in lstJnew: continue
                    lstJdel.append(j)
                [objGeojsonSDM["Features"].pop(j-i) for i, j in enumerate(lstJdel)]

            with open(objPath.pStereoDM,'w') as fileGeojson:
                fileGeojson.write(json.dumps({key:objGeojsonSDM[key] for key in objGeojsonSDM if not key=="Features"}, indent=2)[:-2])
                fileGeojson.write(',\n  "Features":[\n')
                for k in range(len(objGeojsonSDM["Features"])):
                    lineEnd=',\n'
                    if not k: lineEnd=''
                    fileGeojson.write(lineEnd+json.dumps(objGeojsonSDM["Features"][k]))

                for k in range(nbPair):
                    lineEnd=',\n'
                    if not k and not objGeojsonSDM["Features"]: lineEnd=''
                    fileGeojson.write(lineEnd+json.dumps(objBlocks.lstBCouple[0][k]))

                fileGeojson.write(']\n}')
            #sys.exit()
            #---------------------------------------------------------------
            # Dense matching pairwise
            #---------------------------------------------------------------
            if nbPair: procBar=ProcessStdout(name='Dense maching',inputCur=len(lstIPair))
            
            # Clean Docker system /!\ If parallel process, it prunes all existing containers
            #os.popen('sudo docker container prune --force ; sudo docker volume prune --force')

            j=0
            #while j<nbPair//2:
            #j=nbPair//2+1
            while j<nbPair:
                procBar.ViewBar(j)
                strJ=str(objBlocks.lstBCouple[0][j]['id']).rjust(5,'0')

                pathPcLas=objPath.prefStereoDM+objPath.extPC.format(strJ)
                if os.path.exists(pathPcLas): os.system('rm %s'% pathPcLas)

                lstId=sorted(objBlocks.lstBCouple[0][j]['properties']['scenes'].split(';'))
                
                #if not objBlocks.lstBCouple[0][j]['id']==262: 
                #    j+=1
                #    continue
                #logger.info('j: %s'% strJ)
                #if not input('Ready? (1/0)'): continue
                #---------------------------------------------------------------
                # Left or Right Ref
                #---------------------------------------------------------------
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
                epipMode=True
                if glob(objPath.prefProcDM+'*'): os.system('rm %s*'% objPath.prefProcDM)
                prepaProc=MSSFunc.EpipPreProc( tupLstPath[0], 
                                            objBlocks.lstBCouple[0][j]['geometry'], 
                                            args.dem,  
                                            tupPref[0],
                                            epip=epipMode,
                                            geomAoi=geomAoi['geometry'],
                                            )
                    
                # Does not attempt though matches yet
                if prepaProc:
                    FailedDM(pathPcLas, strJ)
                    j+=1
                    continue

                #---------------------------------------------------------------
                # Disparities
                #---------------------------------------------------------------
                out=0
                for i in range(2):
                    prefOut=tupPref[i]
                    lstPath=tupLstPath[i]
                    
                    out+=asp.parallel_stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=epipMode)+['--stop-point', '5',]) 
                    #os.system('cp %s %s'% (prefOut+'-F.tif', prefOut+'-F_init.tif'))
                    if out: break
                    
                    # Switch epipolar images
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
                    logger.error('ASP stereo Failed at %i'% i)
                    FailedDM(pathPcLas, strJ, lstPrefClean=[tupPref[0], ])
                    if i: FailedDM(pathPcLas, strJ, lstPrefClean=[tupPref[1],])
                    j+=1
                    continue

                #---------------------------------------------------------------
                # merge Disparities
                #---------------------------------------------------------------
                prefOut=tupPref[0]
                lstPath=tupLstPath[0]

                pathDispMean=MSSFunc.MergeDisparities(tupPref[0], tupPref[1], gdal)
                if not pathDispMean: 
                    FailedDM(pathPcLas, strJ, lstPrefClean=tupPref)
                    j+=1
                    continue
                
                out=asp.parallel_stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=epipMode)+['--entry-point', '5',])
                pathPcTif=prefOut+'-PC.tif'
                if not os.path.exists(pathPcTif): 
                    FailedDM(pathPcLas, strJ, lstPrefClean=tupPref)
                    j+=1
                    continue

                #asp.point2dem(MSSFunc.SubArgs_P2D(pathPcTif, args.epsg))     
                #os.system('mv %s %s'% (prefOut+'-DEM.tif', objPath.prefStereoDM+'-DEM-%i.tif'% j,))
                #sys.exit()  
                
                #---------------------------------------------------------------
                # Save Process
                #---------------------------------------------------------------
                pathTxt=MSSFunc.AspPc2Txt(pathPcTif)
                if type(pathTxt)==int: 
                    FailedDM(pathPcLas, strJ, lstPrefClean=tupPref)
                    j+=1
                    continue
                
                subArgs=[objPath.pJsonSource,
                         '--readers.text.filename=%s'% pathTxt,
                         '--writers.las.filename=%s'% pathPcLas,
                         '--filters.reprojection.out_srs="EPSG:%s"'% args.epsg,
                         '--stage.source.value="PointSourceId=%i"'% (objBlocks.lstBCouple[0][j]['id']+1),
                         '--stage.angle.value="ScanAngleRank=%i"'% int(round(MSSFunc.BRratio(lstPath[0][1], lstPath[1][1], atype='deg'))),
                         ]
                pdal.pipeline(subArgs)
                
                #---------------------------------------------------------------
                # Save geometry
                #---------------------------------------------------------------
                objBlocks.lstBCouple[0][j]['properties']['DmProcess']=True
                
                with open(objPath.pStereoDM,'w') as fileGeojson:
                    fileGeojson.write(json.dumps({key:objGeojsonSDM[key] for key in objGeojsonSDM if not key=="Features"}, indent=2)[:-2])
                    fileGeojson.write(',\n  "Features":[\n')
                    for k in range(len(objGeojsonSDM["Features"])):
                        lineEnd=',\n'
                        if not k: lineEnd=''
                        fileGeojson.write(lineEnd+json.dumps(objGeojsonSDM["Features"][k]))

                    for k in range(nbPair):
                        lineEnd=',\n'
                        if not k and not objGeojsonSDM["Features"]: lineEnd=''
                        fileGeojson.write(lineEnd+json.dumps(objBlocks.lstBCouple[0][k]))

                    fileGeojson.write(']\n}')

                #---------------------------------------------------------------
                # Clean folder
                #---------------------------------------------------------------
                cmd='rm -r '+objPath.prefProcDM+'*'
                os.system(cmd)
                j+=1
            
            # Clean Docker system /!\ If parallel process, it prunes all existing containers
            #os.popen('sudo docker container prune --force ; sudo docker volume prune --force')
            #---------------------------------------------------------------
            # Point cloud summary
            #---------------------------------------------------------------
            logger.info('# Point cloud summary')

            lstPCpath=glob(objPath.prefStereoDM+objPath.extPC.format('*'))
            if not lstPCpath: raise RuntimeError("No created point clouds")
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
            
            #---------------------------------------------------------------
            # Point cloud filtering
            #---------------------------------------------------------------
            logger.info('# Point cloud filtering')

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
            
            with Pool(None) as poolCur:
                poolCur.map(Filtering, list(range(nbTile)))
                print()

            lstTilePath=glob(objPath.pPcFltTile.format('*'))
            lstTilePath.sort()
            nbTile=len(lstTilePath)
            
            #---------------------------------------------------------------
            # Point cloud rasterize
            #---------------------------------------------------------------
            logger.warning('# Point cloud merging')
            
            strTemplate=objPath.pPcFltTile.split('{}')
            
            procBar=ProcessStdout(name='Rasterizing per tile',inputCur=nbTile//os.cpu_count()+nbTile%os.cpu_count())
            def RasterizeTiles(i):
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

            with Pool(None) as poolCur:
                poolCur.map(RasterizeTiles, list(range(nbTile)))
                print()

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
