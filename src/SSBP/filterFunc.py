#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from shapely.geometry import Polygon

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

def FilterBlock(objIn, fType, lstBName=False):
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
            objIn.lstBFeat[bI]=Filter_Footprint(objIn.lstBFeat[bI])
        elif fType=='bh':
            objIn.lstBFeat[bI]=Filter_BHratio(objIn.lstBFeat[bI])
        
        objIn.lstBId[bI]=(objIn.lstBId[bI][0], len(objIn.lstBFeat[bI]))

    return objIn

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
    
    if setFeatPop:
         return [lstBFeatCur[i] for i in range(nbFeat) if not i in setFeatPop]
    else:
        return lstBFeatCur

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

def Filter_BHratio(lstBFeatCur):
    '''
    From the given filtered scene list (may be One or Month block, 
    may be pre-filtered using footprint), it select the best scenes
    according to their B/H ratio. It relies on Pairs.geojson which
    must include the B/H ratio (from extented MD)
    '''
    print('B/H')
    pass

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
