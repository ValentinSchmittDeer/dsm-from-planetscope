#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, time, logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import numpy as np
import json
from shapely.geometry import Polygon
import rasterio


from PVL.PVL_Logger import SetupLogger, SubLogger, ProcessStdout
from pprint import pprint

#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__=['SceneBlocks', 'Date2Int', 'SimplifyGeom']
SetupLogger(name=__name__)

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

class SceneBlocks():
    '''
    Block creation object using the list of feature 
    
    lstIn (list): list of feature with custumer metatdata (json obj)
    pathOut (str): output directory
    meth (str): block creation method
        'one': one block from input features
        'month': one block per month
        'dir': recreate the python object from repository and descriptors
    
    out:
        objBlock (class):
            nbFeat (int): number of input scene
            method (str): block creation metod
            dirOut (str): output directory
            lstBId (list with (str, int)): list of tuple with block ID (name), feature number
            lstBFeat (list with json): list with feature decription
            nbB (int): number of block
            lstBCouple (list): list of json stereo pairs
            lstCoverage (list): list of tuple (image profile, scene coverage frame, stereo pair coverage frame)
    '''
    def __init__(self, lstIn, pathOut, meth):
        '''
        Main block creation function leading to Build_xx functions
        '''
        self.nbFeat=len(lstIn)
        self.method=meth
        if not os.path.isdir(pathOut): SubLogger(logging.CRITICAL, 'pathOut must be a directory')
        self.dirOut=pathOut

        SubLogger(logging.ERROR, 'create block from best B/H per ground unit (10m) amoung big dataset')
        if meth=='one':
            self.Build_One(lstIn)
        elif meth=='month':
            self.Build_Month(lstIn)
        elif meth=='dir':
            self.Build_Dir()
        else:
            SubLogger(logging.CRITICAL, 'Unknown block method (%s)'% meth)

    def __str__(self):
        return '\n\t\t'.join(['Block List:', '(Block ID, Feature number, Dir name)']+[str(tu) for tu in self.lstBId])

    def Build_One(self, lstIn):
        '''
        Build scene block with all input scenes

        lstIn (list): list of feature with custumer metatdata (json obj)

        out:
            objBlock (class):
                lstBId (list with (int, int)): list of tuple with block ID and feature number
                lstBFeat (list with json): list with feature decription
                nbB (int): number of created block  
        '''
        from SSBP import nameBlock

        dateB='{}-{}'.format(lstIn[0]\
                                    ['properties']\
                                        ['acquired']\
                                            .split('T')\
                                                [0]\
                                                    .replace('-',''),
                                  lstIn[-1]\
                                    ['properties']\
                                        ['acquired']\
                                            .split('T')\
                                                [0]\
                                                    .replace('-','')
                                  )
        nameB=nameBlock.format(dateB)
        SubLogger(logging.INFO, nameB)
        self.lstBFeat=lstIn
        self.lstBId=[(nameB, 
                    self.nbFeat)]
        self.nbB=1

    def Build_Month(self, lstIn):
        '''
        Build scene block per month

        lstIn (list): list of feature with custumer metatdata (json obj)

        out:
            objBlock (class):
                lstBId (list with (int, int)): list of tuple with block ID and feature number
                lstBFeat (list with json): list with feature decription
                nbB (int): number of created block  
        '''
        from SSBP import nameBlock

        lstSceneDate=[datetime.fromisoformat(\
                        feat\
                            ['properties']\
                                ['acquired']\
                                    .replace('Z','')\
                                        .ljust(26, '0'))\
                                            for feat in lstIn]
        lstSceneDate.sort()
        
        # Scene clustering
        monthCur=Date2Int(lstSceneDate[0])
        yearCur=monthCur-lstSceneDate[0].month
        monthMax=Date2Int(lstSceneDate[-1])
        
        self.lstBFeat=[]
        self.lstBId=[]
        i=0
        while monthCur<=monthMax:
            nameB=nameBlock.format(str(monthCur))
            SubLogger(logging.INFO, nameB)
            monthFeat=monthCur
            
            lstFeatCur=[]
            
            while monthCur==monthFeat and i<self.nbFeat:
                if monthCur==monthFeat: lstFeatCur.append(lstIn[i])

                # Update list index
                if not i==self.nbFeat-1: 
                    i+=1
                    monthFeat=Date2Int(lstSceneDate[i])
                else:
                    i+=1

            # Sorte data
            self.lstBFeat.append(lstFeatCur)
            self.lstBId.append((nameB, 
                                len(lstFeatCur)))

            # Update month
            if monthCur-yearCur==12:
                yearCur+=100
                monthCur=yearCur+1
            else:
                monthCur+=1
        
        # Cluster check
        sumBlock=sum([tu[1] for tu in self.lstBId])
        if not sumBlock==len(lstSceneDate):
            SubLogger(logging.CRITICAL, 'Block creation issue, %i clustered feature among %i inputs'% (sumBlock, self.nbFeat))

        self.nbB=len(self.lstBId)
    
    def Build_Dir(self):
        '''
        Recreate the python object from repository and descriptors

        out:
            objBlock (class):
            nbFeat (int): number of input scene
            method (str): block creation metod
            dirOut (str): output directory
            lstBId (list with (str, int)): list of tuple with block ID (name), feature number
            lstBFeat (list with json): list with feature decription
            nbB (int): number of block
            lstBCouple (list): list of json stereo pairs
        '''
        from SSBP import nameBlock, nameBlockFile
        from glob import glob

        regexBlock=os.path.join(self.dirOut,nameBlock.format('*'))
        lstPath=glob(regexBlock)
        self.nbB=len(lstPath)
        lstPath.sort()

        self.lstBFeat, self.lstBId, self.lstBCouple=[], [], []

        for pathB in lstPath:
            nameB=os.path.basename(pathB)
            SubLogger(logging.INFO, nameB)

            # Feature list
            pathDescip=os.path.join(pathB, nameBlockFile.format(nameB, 'Search.json'))
            if not os.path.exists(pathDescip): SubLogger(logging.CRITICAL, '%s descriptor not found'% nameBlockFile.format(nameB, 'Search.json'))
            with open(pathDescip) as fileIn:
                self.lstBFeat.append(json.load(fileIn))

            # Block ID list and feat number
            self.lstBId.append((nameB, len(self.lstBFeat[-1])))

            # Scene couple
            pathDescip=os.path.join(pathB, nameBlockFile.format(nameB, 'Couple.json'))
            if os.path.exists(pathDescip):
                with open(pathDescip) as fileIn:
                    #txtin=fileIn.read()
                    #txt=txtin[390:400]
                    #print(txt)
                    #pprint(eval(txt))
                    #sys.exit()
                    self.lstBCouple.append(json.load(fileIn))

    def FilterBlock(self, fType, lstBI=False):
        '''
        Main filter function leading to Filter_xx functions

        fType (str): fp|
        lstBI (list): list of block index to write (default: False means all blocks).
            To index list can be created from block ID list (lstBId) by:
                [self.lstBId.index(blockCur) for blockCur in self.lstBId if blockCur[0] in lstBId]
        out:
            objBlock (class): updated object, new lstBId and lstBFeat
        '''
        if not self.nbB: SubLogger(logging.CRITICAL, 'No existing block')


        if fType=='fp':
            if not lstBI: lstBI=range(self.nbB)
            for bI in lstBI:
                SubLogger(logging.INFO, self.lstBId[bI][0])
                self.Filter_Footprint(bI)
                    
    def Filter_Footprint(self, bI):
        '''
        Select scenes in a block based on footprint intersection several criteria. It reduces 
        the scene number.

        bI (int): list ID of the block. For instance, bI=0 means 
            the first one with block ID=self.lstBId[0][0]
        '''
        from SSBP import dicTolerance,rdpEpsi
        lstBFeatCur=self.lstBFeat[bI]
        
        setFeatPop=set()
        SubLogger(logging.INFO, 'Identical scenes:') 
        print('[', end='')
        for i in range(self.lstBId[bI][1]):
            for j in range(i+1,self.lstBId[bI][1]):
                # Basic on footprint
                if QGeomDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance['geom']): continue
                lstInd=(0,i,j)

                # Satellite azimuth (ascending/descending)
                out=QSatAzDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance['satAz'])
                if out: continue

                # Cloudness discrimination
                QCloudDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance)
                if out: setFeatPop.add(lstInd[out])

                # Sun elev discrimination
                out=QSunEDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance)
                if out: setFeatPop.add(lstInd[out])

                # Quality discrimination
                out=QQualiDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance['quali'])
                if out: setFeatPop.add(lstInd[out])

                print((lstBFeatCur[i]['id'],lstBFeatCur[j]['id']), end='')
                setFeatPop.add(j)
        print(']\n=> %i removed scenes'% len(setFeatPop))
        
        if setFeatPop:
            self.lstBFeat[bI]=[lstBFeatCur[i] for i in range(self.lstBId[bI][1]) if not i in setFeatPop]
            self.lstBId[bI]=(self.lstBId[bI][0], len(self.lstBFeat[bI]))
    
    def StereoCoupling(self, lstBI=False):
        '''
        Create list of stereo scene pairs
        
        out:
            objBlock (class): updated object
                lstBCouple (list): list of json stereo pairs
        '''
        from copy import deepcopy
        from SSBP import dicCouple

        if not self.nbB: SubLogger(logging.CRITICAL, 'No existing block')

        self.lstBCouple=[]

        if not lstBI: lstBI=range(self.nbB)
        for bI in lstBI:
            SubLogger(logging.INFO, self.lstBId[bI][0])

            self.lstBCouple.append([])
            for i in range(self.lstBId[bI][1]):
                feat1=self.lstBFeat[bI][i]
                geom1=Polygon(feat1['geometry']['coordinates'][0])
                
                for j in range(i+1,self.lstBId[bI][1]):
                    feat2=self.lstBFeat[bI][j]
                    geom2=Polygon(feat2['geometry']['coordinates'][0])
                    
                    if not geom1.intersects(geom2): continue
                    
                    newCouple=dicCouple.copy()
                    newCouple['properties']['Scene1']=feat1['id']
                    newCouple['properties']['Scene2']=feat2['id']

                    geomInters=geom1.intersection(geom2)
                    newCouple["geometry"]["type"]= geomInters.geom_type
                    
                    if newCouple["geometry"]["type"]=='MultiPolygon' :
                        lstCoords=[]
                        for geomPart in geomInters:
                            lstCoords.append([[list(tup) for tup in list(geomPart.exterior.coords)]])
                            newCouple['properties']['area']+=geomPart.area
                    
                    else:
                        lstCoords=[[list(tup) for tup in list(geomInters.exterior.coords)]]
                        newCouple['properties']['area']+=geomInters.area

                    
                    newCouple['geometry']['coordinates']=lstCoords

                    self.lstBCouple[-1].append(deepcopy(newCouple))
                    
            
            SubLogger(logging.INFO, '=> %i scene couples'% len(self.lstBCouple[-1]))
            
    def Coverage(self, featAoi, lstBI=False):
        '''
        Compute the number of scene per ground sample and 
        stereopair (if available). It is written down laster 
        by the WriteBlocks function.

        featAoi (json): orignal AOI feature used as mask
        lstBI (list): list of block index to write (default: False means all blocks).
            To index list can be created from block ID list (lstBId) by:
                [self.lstBId.index(blockCur) for blockCur in self.lstBId if blockCur[0] in lstBId] 
        out:
            objBlock (class): updated object
                lstCoverage (list): list of tuple (image profile, scene coverage frame, stereo pair coverage frame)
        '''
        if not self.nbB: SubLogger(logging.CRITICAL, 'No existing block')

        from rasterio.features import geometry_mask
        from rasterio.transform import from_origin
        from rasterio.crs import CRS
        from SSBP import profileCoverTif, imageGsd

        geomAoiJson=featAoi['features'][0]['geometry']
        geomAoi=Polygon(geomAoiJson['coordinates'][0][0])

        boundsGeomAoi=geomAoi.bounds
        boundsAoi=[item//imageGsd*imageGsd+k//2*imageGsd for k,item in enumerate(boundsGeomAoi)]
        shapeAoi=(int((boundsAoi[3]-boundsAoi[1])/imageGsd), int((boundsAoi[2]-boundsAoi[0])/imageGsd))
        transfAoi=from_origin(boundsAoi[0],boundsAoi[-1],imageGsd,imageGsd)
        
        # Mask to AOI
        frameMask=geometry_mask((geomAoiJson,), 
                                shapeAoi,
                                transfAoi,
                                all_touched=True,
                                invert=True,
                                )

        self.lstCoverage=[]

        if not lstBI: lstBI=range(self.nbB)
        for bI in lstBI:
            SubLogger(logging.INFO, self.lstBId[bI][0])
            
            # Update and store image profile
            self.lstCoverage.append([profileCoverTif.copy(),])
            self.lstCoverage[-1][0]['height'],self.lstCoverage[-1][0]['width']=shapeAoi
            self.lstCoverage[-1][0]['transform']=transfAoi
            self.lstCoverage[-1][0]['crs']=CRS.from_epsg(4326)

            # Compute scene pair count
            frameGeomStack=self.Geometry_Stack(shapeAoi, transfAoi, self.lstBFeat[bI])
            self.lstCoverage[-1].append(frameGeomStack*frameMask)

            # Compute stereo pair count
            ''' It is useless because it prints out 
            the same geometry in longeur time and 
            and exceed 255 => must be turned to 16 bits
                It will be usefull once the B/H ratio would be included !
            '''
            continue
            if 'lstBCouple' in self.__dir__():
                self.lstCoverage[-1][0]['count']*=1
                frameGeomStack=self.Geometry_Stack(shapeAoi, transfAoi, self.lstBCouple[bI])
                self.lstCoverage[-1].append(frameGeomStack*frameMask)

    def Geometry_Stack(self, shapeCur, transfCur, featIn):
        '''
        Add geometry per ground sample. It is write down laster by the WriteBlocks function.

        shapeCur (tuple): frame shape (row, column)
        transfCur (Affine): image transformation
        featIn (lst): list of geometry to stack
        out:
            frameOut (np.array): counting image frame
        '''
        from rasterio.features import rasterize
        from rasterio.enums import MergeAlg
        nbFeat=len(featIn)
        frameOut=np.zeros(shapeCur)
        
        # Add scene
        procBar=ProcessStdout(name='Geometry_Stack',inputCur=nbFeat)
        for i in range(nbFeat):
            procBar.ViewBar(i)
            frameOut=rasterize((featIn[i]['geometry'],),
                                out_shape=shapeCur,
                                out=frameOut,
                                fill=0,
                                all_touched=True,
                                transform=transfCur,
                                merge_alg=MergeAlg.add,
                                default_value=1,
                                dtype=np.uint8,
                                )
        return frameOut
            
    def WriteBlocks(self, lstBI=False, simpleGeom=False):
        '''
        Write block descriptors at the given path creating block subfolder.

        lstBI (list): list of block index to write (default: False means all blocks).
            To index list can be created from block ID list (lstBId) by:
                [self.lstBId.index(blockCur) for blockCur in self.lstBId if blockCur[0] in lstBId] 
        simpleGeom (bool): replace existing geometry by the simplify one.
        out:
        '''
        if not self.nbB: SubLogger(logging.CRITICAL, 'No existing block')

        from SSBP import rdpEpsi, nameBlockFile, sceneIdExt, basicGeojson
        
        # Write all files
        if not lstBI: lstBI=range(self.nbB)
        for bI in lstBI:
            SubLogger(logging.INFO, self.lstBId[bI][0])

            # Creation simplify geometry
            if simpleGeom and not 'geometry_simple' in self.lstBFeat[bI][0]:
                for j in range(self.lstBId[bI][1]):
                    self.lstBFeat[bI][j]['geometry']={"type": "Polygon",
                                                        "coordinates": [SimplifyGeom(self.lstBFeat[bI][j]['geometry']['coordinates'][0], rdpEpsi)]}

            # Directory
            pathDir= os.path.join(self.dirOut, self.lstBId[bI][0])
            if not os.path.exists(pathDir): os.mkdir(pathDir)

            # Search json
            pathOut=os.path.join(pathDir,nameBlockFile.format(self.lstBId[bI][0], 'Search.json'))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            with open(pathOut,'w') as fileOut:
                fileOut.write(json.dumps(self.lstBFeat[bI], indent=2))

            # Scene Id txt
            pathOut=os.path.join(pathDir,nameBlockFile.format(self.lstBId[bI][0], 'SceneId.txt'))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            with open(pathOut,'w') as fileOut:
                strOut='\n'.join([feat['id']+sceneIdExt for feat in self.lstBFeat[bI]])
                fileOut.write(strOut)

            # Search Geojson
            pathOut=os.path.join(pathDir,nameBlockFile.format(self.lstBId[bI][0], 'Search.geojson'))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            with open(pathOut,'w') as fileOut:
                objOut=basicGeojson
                objOut['name']=nameBlockFile.format(self.lstBId[bI][0], 'Search_init')
                objOut['features']=self.lstBFeat[bI]
                fileOut.write(json.dumps(objOut, indent=2))

            # Coupling json
            if 'lstBCouple' in self.__dir__():
                pathOut= os.path.join(pathDir, nameBlockFile.format(self.lstBId[bI][0], 'Couple.json'))
                if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
                with open(pathOut,'w') as fileOut:
                    fileOut.write('[\n')
                    fileOut.write(',\n'.join([str(item).replace('\'','"') for item in self.lstBCouple[bI]]))
                    fileOut.write('\n]')

            # Coverage tif
            if 'lstCoverage' in self.__dir__():
                pathOut= os.path.join(pathDir, nameBlockFile.format(self.lstBId[bI][0], 'Coverage.tif'))
                if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
                with rasterio.open(pathOut,'w',**self.lstCoverage[bI][0]) as fileOut:
                    for iFrame in range(1,len(self.lstCoverage[bI])):
                        fileOut.write(self.lstCoverage[bI][iFrame], iFrame)


def Date2Int(datetimeObj):
    return int('{}{:02d}'.format(datetimeObj.year, datetimeObj.month))

def SimplifyGeom(geomIn,rdpEpsi):
    '''
    Compute simplify geometry of a given footprint coordinates. The simplify 
    geometry is the 4 corner points starting at the North-West corner. This is
    a complicated algorithm which may fail easily:
        -Douglas-Peucker
        -Centroid from wieghted average (distance to other point sum, squared)
        -Distance to centroid and quadrant space division
        -Per quadrant:
            -Grading all available points based on:
                * +1: longer distance to centroid
                * +1: extremum in longitude
                * +1: extremum in latitude
                * +2: larger distance to others sum
            -Select the best point
        -Add the loop closing point (first=last)


    geomIn (list of (x,y)): footprint coordinates

    out:
        geomOut ((list of (x,y))): simplify footprint coordinates (closed loop with 5 points)
    '''
    geomIn=np.array(geomIn[:-1])
    geomDP=rdp(geomIn, epsilon=rdpEpsi)
    
    nb=geomDP.shape[0]
    # Distance to other points
    tableDistOther=np.array([sum(np.sum((geomDP-geomDP[k,:])**2, axis=1)**0.5) for k in range(nb)])
    # Weighted average centre (weight=powered distance)
    centre=np.average(geomDP, axis=0, weights=tableDistOther**2)
    diffPts=geomDP-centre
    tableDiff=np.hstack(((diffPts[:,[0]]>0), 
                         (diffPts[:,[1]]>0), 
                         (np.sum(diffPts**2, axis=1)**0.5).reshape(nb,1)))
    
    geomOut=[]
    # Grading exterior points
    for delta0Posi,delta1Posi in ((1,0), (1,1), (0,1), (0,0)):
        indPts=[k for k in range(nb) if tableDiff[k,0]==delta0Posi and tableDiff[k,1]==delta1Posi]
        
        #DisplayFootprint(geomIn,geomDP,centre)
        if not indPts:
            DisplayFootprint(geomIn,geomDP,centre)
            strOut='centre error, no point in quadrant %i %i:'% (delta0Posi,delta1Posi)
            strOut+='\nInput geometry (%i pts)\n'% geomIn.shape[0]
            strOut+=str(geomIn)
            strOut+='\nDP geometry (%i pts)\n'% geomDP.shape[0]
            strOut+=str(geomDP)
            strOut+='\nWeight\n'+str(tableDistOther**2)
            strOut+='\nCentre\n'+str(centre)
            SubLogger(logging.CRITICAL, strOut)
        
        if len(indPts)==1:
            indMax=indPts[0]
        else:
            grade=[0]*len(indPts)
            #print('ind', indPts)
            
            # Distance
            grade[np.argsort(tableDiff[indPts,2])[-1]]+=1
            #print('Distance', tableDiff[indPts,2])
            #print('c', grade)
            
            # Extrem Long 
            grade[np.argsort(geomDP[indPts,0])[-delta0Posi]]+=1
            #print('Extrem Long', geomDP[indPts,0], '=>', np.argsort(geomDP[indPts,0]))
            #print('c', grade)
            
            # Extrem Lat
            grade[np.argsort(geomDP[indPts,1])[-delta1Posi]]+=1
            #print('Extrem Lat', geomDP[indPts,1], '=>', np.argsort(geomDP[indPts,1]))
            #print('c', grade)
            
            # Dist to others
            grade[np.argsort(tableDistOther[indPts])[-1]]+=2
            #print('Dist to others', tableDistOther[indPts])
            #print('c', grade)

            indMax=indPts[grade.index(max(grade))]
            #print(indMax)
        geomOut.append(list(geomDP[indMax,:]))
        
        #input('SimplifyGeom')


    if not len(geomOut)==4:
        strOut='footprint reconstruction error, only %i points'% len(geomOut)
        strOut+='\nInput geometry (%i pts)\n'% geomIn.shape[0]
        strOut+=str(geomIn)
        strOut+='\nDP geometry (%i pts)\n'% geomDP.shape[0]
        strOut+=str(geomDP)
        strOut+='\nOutput geometry (%i pts)\n'% geomOut.shape[0]
        strOut+=str(geomOut)
        SubLogger(logging.CRITICAL, strOut)
    else:
        geomOut.append(geomOut[0])
    
    return geomOut

def DisplayFootprint(geom1,geom2,centre):
    import matplotlib.pyplot as plt
    fig, graph = plt.subplots(1, 1)
    
    graph.plot(geom1[:,0],geom1[:,1],'kx-',label='Footprint init')
    graph.plot(geom2[:,0],geom2[:,1],'go-',label='Footprint DP')
    graph.plot(centre[0],centre[1],'r^',label='Centre')
    
    graph.set_xlabel('Long')
    graph.set_ylabel('Lat')
    graph.legend()
    
    fig.suptitle('Footprint')
    plt.show()

def QGeomDiff(feat1, feat2, tol):
    '''
    Compare geometric footprints based on overlapping area. 

    feat1 (json object): first scene descriptor
    feat2 (json object): second scene descriptor
    tol (float): similarity percentage, stored in dicTolerance

    out:
        check (bool): bool answer about difference.
    '''
    geom1=Polygon(feat1['geometry']['coordinates'][0])
    geom2=Polygon(feat2['geometry']['coordinates'][0])
    
    if not geom1.intersects(geom2): return True

    geomInters=geom1.intersection(geom2)
    percentOverlap=geomInters.area/geom1.area
    
    if percentOverlap<tol:
        return True
    else:
        return False

def QSunEDiff(feat1, feat2, tol):
    '''
    Compare feature sun elevation states. Return False 
    if they are similare or the best one index (1,2)
    
    feat1 (json object): first scene descriptor
    feat2 (json object): second scene descriptor
    tol (float): not used

    out:
        check (bool): 0-not different, 1-feat1 is the best, 2-feat2 is the best
    '''
    if not 'sun_elevation' in feat1['properties'] or not 'sun_elevation' in feat2['properties']:
        return 0
    diff=feat1['properties']['sun_elevation']-feat2['properties']['sun_elevation']
    if not diff:
        return diff
    else:
        return (diff<0)+1   

def QCloudDiff(feat1, feat2, tol):
    '''
    Compare feature sun elevation states. Return False 
    if they are similare or the best one index (1,2)
    
    feat1 (json object): first scene descriptor
    feat2 (json object): second scene descriptor
    tol (float): not used

    out:
        check (bool): 0-not different, 1-feat1 is the best, 2-feat2 is the best
    '''
    if 'cloud_percent' in feat1['properties'] and 'cloud_percent' in feat2['properties']:
        keyCloud='cloud_percent'
    else:
        keyCloud='cloud_cover'
    diff=feat1['properties'][keyCloud]-feat2['properties'][keyCloud]
    if not diff:
        return diff
    else:
        return (diff>0)+1

def QQualiDiff(feat1, feat2, tol):
    '''
    Compare feature quality states. Return False 
    if they are similare or the best one index (1,2)
    
    feat1 (json object): first scene descriptor
    feat2 (json object): second scene descriptor
    tol (float): sorted quality list (best to worst)

    out:
        check (bool): 0-not different, 1-feat1 is the best, 2-feat2 is the best


    '''
    if not 'quality_category' in feat1['properties'] or not 'quality_category' in feat2['properties']:
        return 0
    if feat1['properties']['quality_category']==feat2['properties']['quality_category']:
            return 0
    else:
        if not feat1['quality_category'] in tol or not feat2['quality_category'] in tol:
            SubLogger(logging.CRITICAL, 'CompQuali: incomplet list of category (%s or %s)'% (feat1['properties']['quality_category'],feat2['properties']['quality_category']))
        order1=tol.index(feat1['quality_category'])
        order2=tol.index(feat2['quality_category'])
        
        return ((order1-order2)>0)+1

def QSatAzDiff(feat1, feat2, tol):
    '''
    Compare feature sun elevation states. Return False 
    if they are similare or True if different
    
    feat1 (json object): first scene descriptor
    feat2 (json object): second scene descriptor
    tol (float): not used

    out:
        check (bool): 0-not difference, 1-difference
    '''
    if not 'satellite_azimuth' in feat1['properties'] or not 'satellite_azimuth' in feat2['properties']:
        return 0
    return abs(feat1['properties']['satellite_azimuth']-feat2['properties']['satellite_azimuth'])>tol 

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        