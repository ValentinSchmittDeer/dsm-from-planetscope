#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, time, logging
from datetime import datetime, date
from math import pi
from dateutil.relativedelta import relativedelta
import numpy as np
import json
from glob import glob
from shapely.geometry import Polygon
from shapely.errors import TopologicalError as shapelyTopoE
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
__all__=['SceneBlocks', 'Date2Int', 'RatioBH', 'Coverage', 'StereoCoupling']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

class SceneBlocks():
    '''
    1st mode:
    Block creation object using the list of feature. It gathers all scenes 
    with 'one' method or gathers scene from the month with 'month' method.
    2nd mode:
    Read directory and load all descriptors files into the object. The 'info'
    method provide a light version loading just a few information and 
    the 'dir' method loads all of them. The 'dir' method can select block 
    to load from their name.
    
    lstIn (list): list of feature (json) with custumer metatdata (default: None)
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

    def __init__(self, pathCur, lstIn=None, meth='info', b=None):
        '''
        Main block creation function leading to Build_xx functions
        '''
        self.nbFeat=len(lstIn)
        self.method=meth
        if not os.path.isdir(pathCur): SubLogger('CRITICAL', 'pathCur must be a directory')
        self.dirOut=pathCur

        if meth=='one':
            self.Build_One(lstIn)
        elif meth=='month':
            self.Build_Month(lstIn)
        elif meth=='dir':
            self.Build_Dir(b)
        elif meth=='info':
            self.Build_Info()
        else:
            SubLogger('CRITICAL', 'Unknown block method (%s)'% meth)

    def __str__(self):
        return '\n\t\t'.join(['Block List (%s):'% self.method, '(Block ID, Feature number)']+[str(tu) for tu in self.lstBId])

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

        iB=0
        bName, nbFeat=self.lstBId[iB]
        # Directory
        bName, nbFeat=self.lstBId[iB]
        pathDir= os.path.join(self.dirOut, bName)
        if not os.path.exists(pathDir): os.mkdir(pathDir)
        # Scene Id txt
        pathOut=os.path.join(self.dirOut, sbName, fileSceneId.format(bName))
        if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
        with open(pathOut,'w') as fileOut:
            strOut='\n'.join([feat['id']+extSceneIn for feat in self.lstBFeat[iB]])
            fileOut.write(strOut)

        # Selection Geojson
        pathOut=os.path.join(self.dirOut, bName,fileSelec.format(bName))
        if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
        objOut=tempGeojson.copy()
        objOut['name']=fileSelec.format(bName).split('.')[0]
        del objOut['Features']
        strOut=json.dumps(objOut, indent=2)

        fileOut=open(pathOut,'w')
        fileOut.write(strOut[:-2])
        fileOut.write(',\n  "Features":[\n')
        for i, feat in enumerate(self.lstBFeat[iB]):
            lineEnd=',\n'
            if not i: lineEnd=''
            fileOut.write(lineEnd+json.dumps(feat))
        fileOut.write(']\n}')
        fileOut.close()

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

        for iB in range(self.nbB):
            bName, nbFeat=self.lstBId[iB]
            SubLogger('INFO', bName) 
            pathDir= os.path.join(self.dirOut, bName)
            if not os.path.exists(pathDir): os.mkdir(pathDir)
            
            # Scene Id txt
            pathOut=os.path.join(self.dirOut, bName, fileSceneId.format(bName))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            with open(pathOut,'w') as fileOut:
                strOut='\n'.join([feat['id']+extSceneIn for feat in self.lstBFeat[iB]])
                fileOut.write(strOut)

            # Selection Geojson
            pathOut=os.path.join(self.dirOut, bName,fileSelec.format(bName))
            if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
            
            objOut=tempGeojson.copy()
            objOut['name']=fileSelec.format(bName).split('.')[0]
            del objOut['Features']
            strOut=json.dumps(objOut, indent=2)

            fileOut=open(pathOut,'w')
            fileOut.write(strOut[:-2])
            fileOut.write(',\n  "Features":[\n')
            for i, feat in enumerate(self.lstBFeat[iB]):
                lineEnd=',\n'
                if not i: lineEnd=''
                fileOut.write(lineEnd+json.dumps(feat))
            fileOut.write(']\n}')
            fileOut.close()
 
    def Build_Dir(self, b):
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
            if b and not nameB==b: continue

            # Block number
            self.nbB+=1

            # Feature list
            pathDescip=os.path.join(pathB, fileSelec.format(nameB))
            if not os.path.exists(pathDescip): SubLogger('CRITICAL', '%s descriptor not found'% nameBFile.format(nameB, 'Search.json'))
            with open(pathDescip) as fileIn:
                geojsonTxt=json.load(fileIn)
                self.lstBFeat.append(geojsonTxt['Features'])

            # Block ID list and feat number
            self.lstBId.append((nameB, len(self.lstBFeat[-1])))

            # Scene couple
            pathDescip=os.path.join(pathB, fileStereo.format(nameB))
            if not os.path.exists(pathDescip): return 0
            try:
                with open(pathDescip) as fileIn:
                    geojsonTxt=json.load(fileIn)
                    self.lstBCouple.append(geojsonTxt['Features'])
            except json.decoder.JSONDecodeError:
                SubLogger('CRITICAL', 'corrupt stereo file, please, delete it: %s'% os.path.basename(pathDescip))

    def Build_Info(self):
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

        self.lstBId=[]

        for pathB in lstPath:
            nameB=os.path.basename(pathB)

            # Block number
            self.nbB+=1

            # Feature list
            pathDescip=os.path.join(pathB, fileSelec.format(nameB))
            if not os.path.exists(pathDescip): SubLogger('CRITICAL', '%s descriptor not found'% nameBFile.format(nameB, 'Search.json'))
            with open(pathDescip) as fileIn:
                geojsonTxt=json.load(fileIn)
                lstBFeat=geojsonTxt['Features']

            # Block ID list and feat number
            self.lstBId.append((nameB, len(lstBFeat)))

def Date2Int(datetimeObj):
    return int('{}{:02d}'.format(datetimeObj.year, datetimeObj.month))

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

def Coverage(pathIn,  featAoi, lstBName=False):
    '''
    Compute the number of scene per ground sample. It writes straight 
    the image file.
    
    pathIn (str): working directory with block folders
    featAoi (json): orignal AOI feature used as mask
    lstBName (list): list of block name (default: False means all)
    out:
        0 (int): the coverage image has been written at the block root
    '''
    def Geometry_Stack(shapeCur, transfCur, featIn):
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
        frameOut=np.zeros(shapeCur, dtype=np.uint16)

        # Add scene
        procBar=ProcessStdout(name='Geometry_Stack',inputCur=nbFeat)
        for i in range(nbFeat):
            procBar.ViewBar(i)
            rasterize((featIn[i]['geometry'],),
                        out_shape=shapeCur,
                        out=frameOut,
                        fill=0,
                        all_touched=True,
                        transform=transfCur,
                        merge_alg=MergeAlg.add,
                        default_value=1,
                        dtype=np.uint16,
                        )
            
        return frameOut

    objInfo=SceneBlocks(pathIn)
    if not objInfo.nbB: SubLogger('CRITICAL', 'No existing block')

    if lstBName:
        lstBId=[objInfo.lstBId.index(blockCur) for blockCur in objInfo.lstBId if blockCur[0] in lstBName]
    else: 
        lstBId=range(objInfo.nbB)

    for bI in lstBId:
        nameB, nbFeat=objInfo.lstBId[bI]
        SubLogger('INFO', nameB)
        objCur=SceneBlocks(pathIn, meth='dir', b=nameB)
          
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
                                ).astype(np.uint16)
        
        # Update and store image profile
        profileImg=profileCoverTif.copy()
        profileImg['height'],profileImg['width']=shapeAoi
        profileImg['transform']=transfAoi
        profileImg['crs']=CRS.from_epsg(4326)

        # Compute scene pair count
        frameGeomStack=Geometry_Stack(shapeAoi, transfAoi, objCur.lstBFeat[0])

        # Coverage tif
        pathOut= os.path.join(objInfo.dirOut, nameB, fileCov.format(nameB))
        if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))

        with rasterio.open(pathOut,'w',**profileImg) as imgOut:
            imgOut.write(frameGeomStack*frameMask, 1)
            imgOut.set_band_description(1, 'Scene count')

        del frameGeomStack, frameMask, objCur

    return 0

def StereoCoupling(pathIn, lstBName=False, moreComb=False):
    '''
    Combine scenes from vector footprint and write straight 
    the desciptor. It can go beyond stereo pairs but the computation 
    effort may large in case of many images.
    
    pathIn (str): working directory with block folders
    lstBName (lst): list of block name (default: False means all)
    moreComb (bool): compute triplets and higher scene combinaisons (default: False) 
    out:
        0 (int): the stereo combination has been written at the block root
    '''
    from copy import deepcopy
    lstKeysBH=('ecefX_m', 'ecefY_m', 'ecefZ_m', 'sat:alt_km')
    objInfo=SceneBlocks(pathIn)
    if not objInfo.nbB: SubLogger('CRITICAL', 'No existing block')

    if lstBName:
        lstBId=[objInfo.lstBId.index(blockCur) for blockCur in objInfo.lstBId if blockCur[0] in lstBName]
    else: 
        lstBId=range(objInfo.nbB)

    for bI in lstBId:
        nameB, nbFeat=objInfo.lstBId[bI]
        SubLogger('INFO', nameB)
        objCur=SceneBlocks(pathIn, meth='dir', b=nameB)

        # Geometry check
        try:
            lstCheckGeom=[Polygon(np.array(feat['geometry']['coordinates']).reshape(-1,2).tolist()).is_valid for feat in objCur.lstBFeat[0]]
        except shapelyTopoE as msg:
            SubLogger('CRITICAL','%s footprint error:\n%s'% (feat['id'], msg))
        if not all(lstCheckGeom): SubLogger('CRITICAL','%s footprint error, please correct it manually'% objCur.lstBFeat[0][lstCheckGeom.index(False)]['id'])

        # Output file
        pathOut= os.path.join(objCur.dirOut, nameB, fileStereo.format(nameB))
        if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
        objOut=tempGeojson.copy()
        objOut['name']=fileStereo.format(nameB).split('.')[0]
        del objOut['Features']
        strOut=json.dumps(objOut, indent=2)
        
        fileOut=open(pathOut,'w')
        fileOut.write(strOut[:-2])
        fileOut.write(',\n  "Features":[\n')

        lstBCouple=[]

        lstK=[0]
        # Pairs
        k=-1
        for i in range(nbFeat):
            feat1=objCur.lstBFeat[0][i]
            coords1=np.array(feat1['geometry']['coordinates']).reshape(-1,2).tolist()
            geom1=Polygon(coords1)

            for j in range(i+1,nbFeat):
                feat2=objCur.lstBFeat[0][j]
                coords2=np.array(feat2['geometry']['coordinates']).reshape(-1,2).tolist()
                geom2=Polygon(coords2)

                if not geom1.intersects(geom2): continue
                try:
                    geomInters=geom1.intersection(geom2)
                except shapelyTopoE:
                    continue                    

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
                if all(checkAttrib): newCouple['properties']['bh']=RatioBH(feat1,feat2)


                newCouple["geometry"]["type"]= geomInters.geom_type

                if geomInters.geom_type=='Polygon' :
                    lstCoords=[list(geomInters.exterior.coords)]
                    newCouple['properties']['area']=geomInters.area

                elif geomInters.geom_type=='MultiPolygon':
                    lstArea=[geomPart.area for geomPart in geomInters.geoms if geomPart.geom_type=='Polygon']
                    lstCoords=[list(geomInters[lstArea.index(max(lstArea))].exterior.coords),]
                    newCouple['properties']['area']=sum(lstArea)
                    
                else:
                    print(list(geomInters.geoms))
                    SubLogger('CRITICAL', '%s not managed'% geomInters.geom_type)

                newCouple['geometry']['coordinates']=lstCoords

                lineEnd=',\n'
                if not k: lineEnd=''
                fileOut.write(lineEnd+json.dumps(newCouple))
                lstBCouple.append(deepcopy(newCouple))

        SubLogger('INFO', '%i combinaisons (%i)'% (k+1, 2))
        lstK.append(k)

        # More combinaisons based on pairs
        keepComb=True
        l=2
        while moreComb and keepComb:
            l+=1
            keepComb=False
            for i in range(lstK[-2], lstK[-1]+1):
                comb1=lstBCouple[i]
                coords1=np.array(comb1['geometry']['coordinates']).reshape(-1,2).tolist()
                geom1=Polygon(coords1)
                i0=[int(j) for j in comb1['properties']['scenesI'].split(';')]
                
                for j in range(max(i0),nbFeat):
                    if j in i0: continue
                    feat2=objCur.lstBFeat[0][j]
                    coords2=np.array(feat2['geometry']['coordinates']).reshape(-1,2).tolist()
                    geom2=Polygon(coords2)
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
                        feat1=objCur.lstBFeat[0][iFeat]
                        checkAttrib=[key in feat1['properties'] for key in lstKeysBH]
                        checkAttrib+=[key in feat2['properties'] for key in lstKeysBH]
                    
                    if all(checkAttrib): 
                        lstBH.append(RatioBH(feat1,feat2))
                        meanBH=sum(lstBH)/len(lstBH)
                        newCouple['properties']['bh']=(comb1['properties']['bh']*(l-1)+meanBH)/l
                    else:
                        newCouple['properties']['bh']=-1

                    # New geometry 
                    geomInters=geom1.intersection(geom2)
                    newCouple["geometry"]["type"]= geomInters.geom_type
                    
                    if geomInters.geom_type=='Polygon' :
                        lstCoords=[list(geomInters.exterior.coords)]
                        newCouple['properties']['area']=geomInters.area
                    
                    elif geomInters.geom_type=='MultiPolygon':
                        lstArea=[geomPart.area for geomPart in geomInters.geoms if geomPart.geom_type=='Polygon']
                        lstCoords=[list(geomInters[lstArea.index(max(lstArea))].exterior.coords),]
                        newCouple['properties']['area']=sum(lstArea)

                    else:
                        SubLogger('CRITICAL', '%s no managed'% geomInters.geom_type)

                    newCouple['geometry']['coordinates']=lstCoords
                    
                    lineEnd=',\n'
                    fileOut.write(lineEnd+json.dumps(newCouple))
                    lstBCouple.append(deepcopy(newCouple))

            SubLogger('INFO', '%i combinations (%i scenes => +%i)'% (k+1, l, k-lstK[-1]))
            lstK.append(k)
        
        fileOut.write(']\n}')
        fileOut.close()

        del lstBCouple, objOut, objCur

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        