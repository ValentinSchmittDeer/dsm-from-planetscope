#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, time, logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import numpy as np
import json
from glob import glob
from shapely.geometry import Polygon
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.crs import CRS

from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc.GeomFunc import Geo2Cart_Elli

from pprint import pprint

#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__=['SceneBlocks', 'Date2Int', 'SimplifyGeom']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

class SceneBlocks():
    '''
    Block creation object using the list of feature. One object SceneBlocks holds 
    all blocks information
    
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
        if not os.path.isdir(pathOut): SubLogger('CRITICAL', 'pathOut must be a directory')
        self.dirOut=pathOut

        if meth=='one':
            self.Build_One(lstIn)
        elif meth=='month':
            self.Build_Month(lstIn)
        elif meth=='dir':
            self.Build_Dir()
        else:
            SubLogger('CRITICAL', 'Unknown block method (%s)'% meth)

    def __str__(self):
        return '\n\t\t'.join(['Block List:', '(Block ID, Feature number)']+[str(tu) for tu in self.lstBId])

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
        SubLogger('INFO', nameB)
        self.lstBFeat=[lstIn,]
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
        lstSceneDate=[datetime.strptime(\
                        feat\
                            ['properties']\
                                ['acquired']\
                                    .replace('Z','')\
                                        .ljust(26, '0'),
                                        '%Y-%m-%dT%H:%M:%S.%f')\
                                        for feat in lstIn]
        lstDateTag=[Date2Int(dateCur) for dateCur in lstSceneDate]
                                        
        # Scene clustering
        monthCur=min(lstDateTag)
        yearCur=min(lstSceneDate).year*100
        monthMax=max(lstDateTag)
        
        self.lstBFeat=[]
        self.lstBId=[]

        while monthCur<=monthMax:
            nameB=nameBlock.format(str(monthCur))
            SubLogger('INFO', nameB)            
            lstFeatCur=[]

            for i in range(self.nbFeat):
                if lstDateTag[i]==monthCur: lstFeatCur.append(lstIn[i])

            # Store data
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
            SubLogger('CRITICAL', 'Block creation issue, %i clustered feature among %i inputs'% (sumBlock, self.nbFeat))

        self.nbB=len(self.lstBId)
    
    def Build_Dir(self):
        '''
        Recreate the python object from repository and descriptors

        out:
            objBlock (class):
                lstBId (list with (str, int)): list of tuple with block ID (name), feature number
                lstBFeat (list with json): list with feature decription
                nbB (int): number of block
                lstBCouple (list): list of json stereo pairs
        '''
        regexBlock=os.path.join(self.dirOut,nameBlock.format('*'))
        lstPath=glob(regexBlock)
        self.nbB=0
        lstPath.sort()

        self.lstBFeat, self.lstBId, self.lstBCouple=[], [], []

        for pathB in lstPath:
            nameB=os.path.basename(pathB)
            SubLogger('INFO', nameB)

            # Block number
            self.nbB+=1

            # Feature list
            pathDescip=os.path.join(pathB, fileSelec.format(nameB))
            if not os.path.exists(pathDescip): SubLogger('CRITICAL', '%s descriptor not found'% nameBFile.format(nameB, 'Search.json'))
            with open(pathDescip) as fileIn:
                geojsonTxt=json.load(fileIn)
                self.lstBFeat.append(geojsonTxt['features'])

            # Block ID list and feat number
            self.lstBId.append((nameB, len(self.lstBFeat[-1])))

            # Scene couple
            pathDescip=os.path.join(pathB, fileStereo.format(nameB))
            if os.path.exists(pathDescip):
                with open(pathDescip) as fileIn:
                    geojsonTxt=json.load(fileIn)
                    self.lstBCouple.append(geojsonTxt['features'])
    
    def SatGeo2Cart(self, lstBName=False):
        '''
        Compute the cartesian coordinate of the camera center
        based on lat [°], long [°] and alt [km] above 
        the ellipsoid WGS84. iIt can be run after extended 
        metadata importation.
        
        descrip1 (json): scene desciptor to update
        out:
            objBlock (class): updated object
                    lstBCouple (list): list of json stereo pairs
        ''' 
        if not self.nbB: SubLogger('CRITICAL', 'No existing block')

        if lstBName:
            lstBI=[self.lstBName.index(blockCur) for blockCur in self.lstBName if blockCur[0] in lstBName]
        else: 
            lstBI=range(self.nbB)

        for bI in lstBI:
            SubLogger('INFO', self.lstBId[bI][0])


            ptsGeo=np.zeros([self.lstBId[bI][1],3])
            for i in range(self.lstBId[bI][1]):
                lstKeys=('sat:alt_km', 'sat:lat_deg', 'sat:lng_deg')
                checkAttrib=[key in self.lstBFeat[bI][i]['properties'].keys() for key in lstKeys]
                if False in checkAttrib: 
                    SubLogger('ERROR', 'extended MD not available, requires %s'% str(lstKeys))
                    continue
                
                ptsGeo[i,:]=np.array([self.lstBFeat[bI][i]['properties']['sat:lng_deg'], 
                                      self.lstBFeat[bI][i]['properties']['sat:lat_deg'],
                                      self.lstBFeat[bI][i]['properties']['sat:alt_km']*1e3])
             
            ptsCart=Geo2Cart_Elli(ptsGeo)

            # Update
            for i in range(self.lstBId[bI][1]):
                for j, key in enumerate(('ecefX_m', 'ecefY_m', 'ecefZ_m')):
                    self.lstBFeat[bI][i]['properties'][key]=ptsCart[i,j]

    def StereoCoupling(self, lstBName=False, moreComb=False):
        '''
        Create list of stereo scene pairs, triplet, etc
        
        lstBName (lst): list of block name (default: False means all)
        moreComb (bool): compute triplets and higher scene combinaisons (default: False) 
        out:
            objBlock (class): updated object
                lstBCouple (list): list of json stereo pairs
        '''
        from copy import deepcopy
        lstKeysBH=('ecefX_m', 'ecefY_m', 'ecefZ_m', 'sat:alt_km')

        if not self.nbB: SubLogger('CRITICAL', 'No existing block')

        self.lstBCouple=[]

        if lstBName:
            lstBI=[self.lstBName.index(blockCur) for blockCur in self.lstBName if blockCur[0] in lstBName]
        else: 
            lstBI=range(self.nbB)

        for bI in lstBI:
            SubLogger('INFO', self.lstBId[bI][0])

            lstK=[0]
            # Pairs
            self.lstBCouple.append([])
            k=-1
            for i in range(self.lstBId[bI][1]):
                feat1=self.lstBFeat[bI][i]
                geom1=Polygon(feat1['geometry']['coordinates'][0])

                for j in range(i+1,self.lstBId[bI][1]):
                    feat2=self.lstBFeat[bI][j]
                    geom2=Polygon(feat2['geometry']['coordinates'][0])
                    if not geom1.intersects(geom2): continue
                    
                    # New intersection
                    k+=1
                    newCouple=tempDescripPair.copy()
                    newCouple['id']=k
                    newCouple['properties']['id']=k
                    newCouple['properties']['nbScene']=2
                    newCouple['properties']['scenes']='%s;%s'% (feat1['id'], feat2['id'])
                    newCouple['properties']['scenesI']='%i;%i'% (i, j)
                    
                    # New B/H
                    checkAttrib=[key in feat1['properties'].keys() for key in lstKeysBH]
                    checkAttrib+=[key in feat2['properties'].keys() for key in lstKeysBH]
                    if not False in checkAttrib: newCouple['properties']['bh']=RatioBH(feat1,feat2)

                    # New geometry 
                    geomInters=geom1.intersection(geom2)
                    newCouple["geometry"]["type"]= geomInters.geom_type
                    
                    if geomInters.geom_type=='Polygon' :
                        lstCoords=[list(geomInters.exterior.coords)]
                        newCouple['properties']['area']=geomInters.area
                    else:
                        SubLogger('CRITICAL', '%s no managed'% geomInters.geom_type)
                        #lstCoords=[]
                        #for geomPart in geomInters:
                        #    lstCoords.append([list(geomPart.exterior.coords)])
                        #    newCouple['properties']['area']=geomPart.area

                    newCouple['geometry']['coordinates']=lstCoords
                    
                    self.lstBCouple[-1].append(deepcopy(newCouple))
            SubLogger('INFO', '%i combinaisons (%i)'% (k+1, 2))
            lstK.append(k)

            if not moreComb: continue
            # More combinaisons based on pairs
            keepComb=True
            l=2
            while keepComb:
                l+=1
                keepComb=False
                for i in range(lstK[-2], lstK[-1]+1):
                    comb1=self.lstBCouple[-1][i]
                    geom1=Polygon(comb1['geometry']['coordinates'][0])
                    i0=[int(j) for j in comb1['properties']['scenesI'].split(';')]
                    
                    for j in range(max(i0),self.lstBId[bI][1]):
                        if j in i0: continue
                        feat2=self.lstBFeat[bI][j]
                        geom2=Polygon(feat2['geometry']['coordinates'][0])
                        if not geom1.intersects(geom2): continue

                        keepComb=True
                        # New intersection
                        k+=1
                        newCouple=tempDescripPair.copy()
                        newCouple['id']=k
                        newCouple['properties']['id']=k
                        newCouple['properties']['nbScene']=comb1['properties']['nbScene']+1
                        newCouple['properties']['scenes']='%s;%s'% (comb1['properties']['scenes'], feat2['id'])
                        lstIFeat=comb1['properties']['scenesI'].split(';')+[str(j)]
                        newCouple['properties']['scenesI']=';'.join(lstIFeat)
                        ####################
                        # New B/H: just for info
                        # Caution: the mean does not take care of MVS
                        lstBH=[]
                        for strIFeat in lstIFeat[:-1]:
                            iFeat=int(strIFeat)
                            feat1=self.lstBFeat[bI][iFeat]
                            checkAttrib=[key in feat1['properties'].keys() for key in lstKeysBH]
                            checkAttrib+=[key in feat2['properties'].keys() for key in lstKeysBH]
                            if not False in checkAttrib: lstBH.append(RatioBH(feat1,feat2))
                        meanBH=sum(lstBH)/len(lstBH)
                        newCouple['properties']['bh']=(comb1['properties']['bh']*(l-1)+meanBH)/l

                        # New geometry 
                        geomInters=geom1.intersection(geom2)
                        newCouple["geometry"]["type"]= geomInters.geom_type
                        
                        if geomInters.geom_type=='Polygon' :
                            lstCoords=[list(geomInters.exterior.coords)]
                            newCouple['properties']['area']=geomInters.area
                        else:
                            SubLogger('CRITICAL', '%s no managed'% geomInters.geom_type)

                        newCouple['geometry']['coordinates']=lstCoords
                        
                        self.lstBCouple[-1].append(deepcopy(newCouple))

                SubLogger('INFO', '%i combinations (%i scenes => +%i)'% (k+1, l, k-lstK[-1]))
                lstK.append(k)    

    def Coverage(self, featAoi, lstBName=False):
        '''
        Compute the number of scene per ground sample and 
        stereopair (if available). It is written down laster 
        by the WriteBlocks function.

        featAoi (json): orignal AOI feature used as mask
        lstBName (list): list of block name (default: False means all)
        out:
            objBlock (class): updated object
                lstCoverage (list): list of tuple (image profile, scene coverage frame, stereo pair coverage frame)
        '''
        if not self.nbB: SubLogger('CRITICAL', 'No existing block')

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

        if lstBName:
            lstBI=[self.lstBName.index(blockCur) for blockCur in self.lstBName if blockCur[0] in lstBName]
        else: 
            lstBI=range(self.nbB)

        for bI in lstBI:
            SubLogger('INFO', self.lstBId[bI][0])
            
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
            
    def WriteBlocks(self, lstBName=False, simpleGeom=False):
        '''
        Write block descriptors at the given path creating block subfolder.

        lstBName (list): list of block name to write (default: False means all blocks).
            e.g.: ['B202010', 'B202011'] 
        simpleGeom (bool): replace existing geometry by the simplify one.
        out:
        '''
        if not self.nbB: SubLogger('CRITICAL', 'No existing block')
        
        # Write all files
        if lstBName:
             lstBId=[self.lstBId.index(blockCur) for blockCur in self.lstBId if blockCur[0] in lstBName]
        else:
            lstBId=range(self.nbB)

        for bI in lstBId:
            SubLogger('INFO', self.lstBId[bI][0])

            # Creation simplify geometry
            if simpleGeom and not 'geometry_simple' in self.lstBFeat[bI][0]:
                for j in range(self.lstBId[bI][1]):
                    self.lstBFeat[bI][j]['geometry']={"type": "Polygon",
                                                        "coordinates": [SimplifyGeom(self.lstBFeat[bI][j]['geometry']['coordinates'][0], rdpEpsi)]}

            # Directory
            pathDir= os.path.join(self.dirOut, self.lstBId[bI][0])
            if not os.path.exists(pathDir): os.mkdir(pathDir)

            # Scene Id txt
            pathOut=os.path.join(pathDir,fileSceneId.format(self.lstBId[bI][0]))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            with open(pathOut,'w') as fileOut:
                strOut='\n'.join([feat['id']+extSceneIn for feat in self.lstBFeat[bI]])
                fileOut.write(strOut)

            # Selection Geojson
            pathOut=os.path.join(pathDir,fileSelec.format(self.lstBId[bI][0]))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            objOut=tempGeojson.copy()
            objOut['name']=fileSelec.format(self.lstBId[bI][0]).split('.')[0]
            objOut['features']=self.lstBFeat[bI]
            with open(pathOut,'w') as fileOut:
                fileOut.write(json.dumps(objOut, indent=2))

            # Coupling json
            if 'lstBCouple' in self.__dir__():
                pathOut= os.path.join(pathDir, fileStereo.format(self.lstBId[bI][0]))
                if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
                objOut=tempGeojson.copy()
                objOut['name']=fileStereo.format(self.lstBId[bI][0]).split('.')[0]
                objOut['features']=self.lstBCouple[bI]
                with open(pathOut,'w') as fileOut:
                    fileOut.write(json.dumps(objOut, indent=2))
            
            # Coverage tif
            if 'lstCoverage' in self.__dir__():
                pathOut= os.path.join(pathDir, fileCov.format(self.lstBId[bI][0]))
                if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
                with rasterio.open(pathOut,'w',**self.lstCoverage[bI][0]) as fileOut:
                    for iFrame in range(1,len(self.lstCoverage[bI])):
                        fileOut.write(self.lstCoverage[bI][iFrame].astype('uint8'), iFrame)
                self.lstCoverage[bI]=False


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
            SubLogger('CRITICAL', strOut)
        
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
        SubLogger('CRITICAL', strOut)
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

def RatioBH(descrip1, descrip2):
    '''
    Compute B/H ratio based on lat, long and altitude of 2 images.

    descrip1 (json): scene 1 desciptor
    descrip2 (json): scene 2 desciptor
    out:
        bh (float): B/H ratio
    '''
    ptsCart=np.zeros([2,3])
    for k,scene in enumerate((descrip1, descrip2)):
        ptsCart[k,:]=np.array([scene['properties']['ecefX_m'], 
                                scene['properties']['ecefY_m'], 
                                scene['properties']['ecefZ_m']])

    base=sum(np.power(ptsCart[1,:]-ptsCart[0,:],2))**0.5
    

    height=(descrip1['properties']['sat:alt_km']+descrip2['properties']['sat:alt_km'])/2*1e3

    return base/height

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        