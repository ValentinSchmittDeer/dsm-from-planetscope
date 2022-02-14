#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
from pprint import pprint
import numpy as np

from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from BlockProc.GeomFunc import Geo2Cart_Elli

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['CheckPC', 'ExtractMD_Blocks', 'ExtractMD_Scene']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def CheckPC():
    '''
    Control whether it runs in planet_common environement.
    
    out:
        out (bool): True=planet_comon
    '''
    from importlib.util import find_spec
    moduleSpec=find_spec('planet_common')
    return (moduleSpec is not None)

def ExtractMD_Blocks(pathIn, lstMD, lstBName=False):
    '''
    Manage the metadata extraction from a "select" file. It runs the metadata 
    extraction function for each found scene and add them into the features 
    properties before "select" file update. It skips existing values.

    objBlock (obj): object SSBP:BlockFunc:SceneBlocks
    lstMD (list): list of metadata path (e.g.: 'sat:alt')
    out:
        objBlock (obj): updated object
    '''
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

        ptsGeo=np.zeros([nbFeat,3])

        procBar=ProcessStdout(name='Read extended metadata',inputCur=nbFeat)
        for j in range(nbFeat):
            procBar.ViewBar(j)
            
            checkAttrib=[any([keyExists.startswith(key) for keyExists in objCur.lstBFeat[0][j]['properties']]) for key in lstMD]
            if not all(checkAttrib): ExtractMD_Scene(objCur.lstBFeat[0][j], lstMD)

            checkAttrib=[any([keyExists.startswith(key) for keyExists in objCur.lstBFeat[0][j]['properties']]) for key in lstMD]
            if not all(checkAttrib) and not checkAttrib.count(False)==1 and 'satellite_azimuth_mean' in lstMD[checkAttrib.index(False)]: 
                SubLogger('ERROR', 'extended MD not available, requires %s: %s'% (str(lstMD), str(checkAttrib)))
                continue
            
            ptsGeo[j,:]=np.array([objCur.lstBFeat[0][j]['properties']['sat:lng_deg'], 
                                  objCur.lstBFeat[0][j]['properties']['sat:lat_deg'],
                                  objCur.lstBFeat[0][j]['properties']['sat:alt_km']*1e3])
             
        ptsCart=Geo2Cart_Elli(ptsGeo)

        # Update
        for i in range(nbFeat):
            for j, key in enumerate(('ecefX_m', 'ecefY_m', 'ecefZ_m')):
                objCur.lstBFeat[0][i]['properties'][key]=ptsCart[i,j]

        # Selection Geojson
        pathOut=os.path.join(objInfo.dirOut, nameB, fileSelec.format(nameB))
        if os.path.exists(pathOut): print('Overwrite %s'% os.path.basename(pathOut))
        
        objOut=tempGeojson.copy()
        objOut['name']=fileSelec.format(nameB).split('.')[0]
        del objOut['Features']
        strOut=json.dumps(objOut, indent=2)

        fileOut=open(pathOut,'w')
        fileOut.write(strOut[:-2])
        fileOut.write(',\n  "Features":[\n')
        for i, feat in enumerate(objCur.lstBFeat[0]):
            lineEnd=',\n'
            if not i: lineEnd=''
            fileOut.write(lineEnd+json.dumps(feat))
        fileOut.write(']\n}')
        fileOut.close()

        del objCur

def ExtractMD_Scene(descripScene, lstMD):
    '''
    Extract metadata of the given scene and return it updated.
    
    descripScene (obj): feature description from search or (SSBP:BlockFunc:SceneBlocks:lstBFeat)
    lstMD (lst): list of metadata path (e.g.: 'sat:alt')
    out:
        descripScene (obj): updated description
    '''
    from planet_common.client import urls
    from planet_common.client import storage

    urls.set_urls('pl')

    nameScene=descripScene['id']+'.cmo'
    mdFullScene=storage.get_scene_json(None, 'flock1', nameScene)
    mdExtScene=mdFullScene['extended']
    #pprint(mdExtScene)

    for pathTag in lstMD:
        mdCur=mdExtScene.copy()
        try:
            for stepTag in pathTag.split(':'):
                mdCur=mdCur[stepTag]
        except KeyError:
            if stepTag=='satellite_azimuth_mean': continue 
            SubLogger('CRITICAL', 'Not found in extended MD of scene %s:\n%s \nAvailable keys: %s\n'% (descripScene['id'], pathTag, str(mdCur.keys())))
            continue
        
        if pathTag.split(':')[-1] in dicUnits:
            nameTag=pathTag+'_'+dicUnits[pathTag.split(':')[-1]]
        else:
           SubLogger('CRITICAL', '"%s" tag unit unknown. List stored in dicUnits'% pathTag)
           nameTag=pathTag

        try:
            descripScene['properties'][nameTag]=int(mdCur)
        except ValueError:
            try:
                descripScene['properties'][nameTag]=float(mdCur)
            except ValueError:
                descripScene['properties'][nameTag]=str(mdCur)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
