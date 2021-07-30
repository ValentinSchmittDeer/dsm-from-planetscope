#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
from pprint import pprint

from OutLib.LoggerFunc import *
from VarCur import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['CheckPC', ]
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def CheckPC():
    from importlib.util import find_spec
    moduleSpec=find_spec('planet_common')
    return (moduleSpec is not None)

def ExtractMD_Blocks(objBlock, lstMD):
    '''
    Manage the metadata extraction from a block object (SSBP:BlockFunc:SceneBlocks).
    It runs the metadata extraction function for each found scene and add them 
    into the features properties (SSBP:BlockFunc:SceneBlocks:lstBFeat). These will 
    be stored in the geojson file (xx_Serach) and used by scene coupling if 
    they are available.

    objBlock (obj): object SSBP:BlockFunc:SceneBlocks
    lstMD (list): list of metadata path (e.g.: 'sat:alt')
    out:
        objBlock (obj): updated object
    '''
    

    for iB in range(objBlock.nbB):
        SubLogger('INFO', objBlock.lstBId[iB][0])
        procBar=ProcessStdout(name='Read extended metadata',inputCur=objBlock.lstBId[iB][1])
        for j in range(objBlock.lstBId[iB][1]):
            procBar.ViewBar(j)
            ExtractMD_Scene(objBlock.lstBFeat[iB][j], lstMD)

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
            SubLogger('WARNING', '"%s" tag not found in extended MD, continue:\n%s \nAvailable keys: %s'% (stepTag, pathTag, str(mdCur.keys())))
            continue
        
        if pathTag.split(':')[-1] in dicUnits:
            nameTag=pathTag+'_'+dicUnits[pathTag.split(':')[-1]]
        else:
           SubLogger('WARNING', '"%s" tag unit unknown. List stored in dicUnits'% pathTag)
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
        
