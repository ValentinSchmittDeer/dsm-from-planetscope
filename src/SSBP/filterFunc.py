#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from shapely.geometry import Polygon, MultiPolygon, Point
from pprint import pprint

from OutLib.LoggerFunc import *
from VarCur import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['FilterBlock', 'Filter_Footprint', 'QGeomDiff', 'QSunEDiff', 'QCloudDiff', 'QualiDiff', 'QSatAzDiff']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

def FilterBlocks(objIn, fType, lstBName=False, aoi=None, red=None):
    '''
    Main filter function leading to Filter_xx functions

    objIn (block object): from blockFunc
    fType (str): fp|
    lstBName (list): list of block name to write (default: False means all blocks).
            
    out:
        objBlock (class): filetered object, new lstBName and lstBFeat
    '''
    if not objIn.nbB: SubLogger('CRITICAL', 'No existing block')
    if not fType in methodF: SubLogger('CRITICAL', 'Unknown filtering method: %s'% fType)

    if lstBName:
        lstBI=[objIn.lstBName.index(blockCur) for blockCur in objIn.lstBName if blockCur[0] in lstBName]
    else: 
        lstBI=range(objIn.nbB)

    for bI in lstBI:
        SubLogger('INFO', objIn.lstBId[bI][0])
        if fType=='fp':
            Filter_Footprint(objIn.lstBFeat[bI])
        elif fType=='bh':
            if not aoi: SubLogger('CRITICAL', 'BH filtering needs the AOI shape (aoi)')
            if red is None: SubLogger('CRITICAL', 'BH filtering needs a redundancy (red)')
            if not 'lstBCouple' in objIn.__dir__(): SubLogger('CRITICAL', 'BH filtering needs stereo pairs')
            
            pathOut=os.path.join(objIn.dirOut, objIn.lstBId[bI][0], fileBHfTrack.format(objIn.lstBId[bI][0]))
            Filter_BHratio(objIn.lstBFeat[bI], objIn.lstBCouple[bI], aoi, red, pathOut)
            
        objIn.lstBId[bI]=(objIn.lstBId[bI][0], len(objIn.lstBFeat[bI]))

def Filter_Footprint(lstBFeatCur):
    '''
    Select scenes in a block based on footprint intersection several criteria. It reduces 
    the scene number.

    bI (int): list ID of the block. For instance, bI=0 means 
        the first one with block ID=self.lstBId[0][0]
    '''
    nbFeat=len(lstBFeatCur)
    
    setFeatPop=set()
    for i in range(nbFeat):
        for j in range(i+1,nbFeat):
            # Basic on footprint
            if QGeomDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance['geom']): continue
            lstInd=(0,i,j)

            # Satellite azimuth (ascending/descending)
            out=QSatAzDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance['satAz'])
            if out: continue

            # Cloudness discrimination
            out=QCloudDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance)
            if out: setFeatPop.add(lstInd[out])

            # Sun elev discrimination
            out=QSunEDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance)
            if out: setFeatPop.add(lstInd[out])

            # Quality discrimination
            out=QQualiDiff(lstBFeatCur[i],lstBFeatCur[j],dicTolerance['quali'])
            if out: setFeatPop.add(lstInd[out])

            setFeatPop.add(j)
    print('=> %i removed scenes'% len(setFeatPop))
    
    for i,j in enumerate(sorted(setFeatPop)):
        del lstBFeatCur[j-i]

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
            SubLogger('CRITICAL', 'CompQuali: incomplet list of category (%s or %s)'% (feat1['properties']['quality_category'],feat2['properties']['quality_category']))
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

def Filter_BHratio(lstBFeatCur, lstBCoupleCur, aoiIn, red, pathOut, disp=False):
    '''
    From the given filtered scene list (may be One or Month block, 
    may be pre-filtered using footprint), it select the best scenes
    according to their B/H ratio. It relies on Pairs.geojson which
    must include the B/H ratio (from extented MD)

    lstBFeatCur (list): list of scene descriptors to update
    lstBCoupleCur (list): list of stereopair
    aoiIn (geojson): AOI shape
    red (int): number of redundancy (0 means single coverage)
    pathOut (str): path of the tacking file
    disp (bool): display the tracking map (default: False)
    out:
        objBlock (class): updated object
            lstBFeatCur (list): Updated list of scene descriptors
    '''
    geomAoi=Polygon(aoiIn['features'][0]['geometry']['coordinates'][0][0])
    
    lstPair=sorted([pair for pair in lstBCoupleCur if pair['properties']['nbScene']==2], key=SortBH, reverse=True)
    nbPair=len(lstPair)

    # Redundancy management
    lstGeomRemain=[geomAoi]*(red+1)
    j=[-1]*(red+1)
    if disp: print('r'+'\tr'.join([str(i) for i in list(range(red+1))])+'\tB/H')
    objOut=tempGeojson.copy() # Output file
    setScene=set()  # Scene IDs
    lstPairId=[]    # Stereopair IDs
    i=-1
    while True in [poly.area>0 for poly in lstGeomRemain] and i<nbPair-1 :
        i+=1
        geomPair=Polygon(lstPair[i]['geometry']['coordinates'][0])

        # Pair filtering  
        if geomPair.area<dicTolerance['bhAreaPair']: continue
        
        # Redundacy polygons
        geomOut={}
        k=-1
        while not geomOut and k<red:
            k+=1
            #geomRemain=lstGeomRemain[k] # RAM issue: Segmentation fault (core dumped)
            
            # Pair filtering
            if not geomPair.intersects(lstGeomRemain[k]): continue
            geomInter=geomPair.intersection(lstGeomRemain[k])
            if geomInter.geom_type in dicTolerance['bhBadGeom']: continue
            if geomInter.geom_type=='GeometryCollection':
                checkBadGeom=set([part.geom_type in dicTolerance['bhBadGeom'] for part in geomInter])
                if len(checkBadGeom)==1 and True in checkBadGeom: continue
            if geomInter.area<dicTolerance['bhAreaInter']: continue

            j[k]+=1
            if disp:
                lstStdout=['-']*(red+1)
                lstStdout[k]=str(j[k])
                print('\t'.join(lstStdout)+'\t%.4f'% SortBH(lstPair[i]))
            #print('i:%i-j:%i-k:%i'% (i,j[k],k))
            if j[k]==0: SubLogger('INFO', 'Max BH (r:%i): %.4f'% (k,SortBH(lstPair[i])))
            # Store
            for sceneId in lstPair[i]['properties']['scenes'].split(';'):
                setScene.add(sceneId)
            lstPairId.append(lstPair[i]['id'])
            lstGeomRemain[k]=lstGeomRemain[k].difference(geomPair)
            
            # Output
            geomOut={"id":j[k], 
                     "type": "Feature", 
                     "properties": {"idStep": j[k], 
                                    "idRed": k, 
                                    "idOrder":i, 
                                    "idPair": lstPair[i]['id'], 
                                    "bh": SortBH(lstPair[i]),
                                    }, 
                     "geometry": {"type": 'MultiPolygon', 'coordinates':[[]]}}
            if lstGeomRemain[k].geom_type=='Polygon':
                lstGeomRemain[k]=MultiPolygon([lstGeomRemain[k],])
            elif lstGeomRemain[k].geom_type=='GeometryCollection' and lstGeomRemain[k].area==0:
                lstGeomRemain[k]=Point(0,0)
                continue
            elif not lstGeomRemain[k].geom_type=='MultiPolygon':
                print(lstGeomRemain[k])
                SubLogger('CRITICAL', 'Unknown geometry type: %s'% lstGeomRemain[k].geom_type)
            
            for geomCur in lstGeomRemain[k]:
                geomOut["geometry"]["coordinates"][0].append(list(geomCur.exterior.coords))
                if len(geomCur.interiors):
                    for ringCur in geomCur.interiors:
                        geomOut["geometry"]["coordinates"][0].append(list(ringCur.coords))
                 
            objOut["Features"].append(geomOut)
    
    SubLogger('INFO', 'Min BH (r:%i): %.4f'% (k,SortBH(lstPair[i])))
    if i==nbPair-1: SubLogger('WARNING', 'Not enough stereopairs to fill the AOI')
    # Output file
    with open(pathOut, 'w') as fileOut:
        fileOut.write(json.dumps(objOut, indent=2))

    # Update object: stereo combinaison updeated by new run of stereo coupling
    #lstDel=[i for i in range(len(lstBCoupleCur)) if not lstBCoupleCur[i]['id'] in lstPairId]
    #for i,j in enumerate(lstDel):
    #    del lstBCoupleCur[j-i]
    
    lstDel=[i for i in range(len(lstBFeatCur)) if not lstBFeatCur[i]['id'] in setScene]
    for i,j in enumerate(lstDel):
        del lstBFeatCur[j-i]
    
def SortBH(a):
    return a['properties']['bh']

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
