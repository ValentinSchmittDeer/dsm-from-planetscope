#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging


from PVL.PVL_Logger import SetupLogger, SubLogger

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['CheckPlCom', 'Bucket_Status', 'MakeScript_JSBatchMake']
SetupLogger(name=__name__)

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def CheckPC():
    from importlib.util import find_spec
    moduleSpec=find_spec('planet_common')
    return (moduleSpec is not None)


class PCTBucket:
    '''
    Local python object for bucket management. It embeds planet_comon commannds 
    for Storage and Job System management.

    nameBlock (str): block name
    pathSceneID (str): scene id file
    out:
        PCTBucket (obj):
            nameBuck (str): bucket name
            lstSceneLocal (tuple): list of scene id from local
    '''
    def __init__(self, nameBlock, pathSceneID):
        from PCT import prodLevel, nameBucket

        self.nameBuck=nameBucket.format(nameBlock, prodLevel)
        if not os.path.exists(pathSceneID): SubLogger(logging.CRITICAL, 'pathSceneID not found')
        with open(pathSceneID) as fileIn:
            self.lstSceneLocal=tuple([lineCur.strip() for lineCur in fileIn.readlines()])

    def __str__(self):
        return '{} should have {} scenes'.format(self.nameBuck, len(self.lstSceneLocal))

    def exists(self):
        '''
        Test whether the bucket alreadyy exists

        out:
            exists (bool): the bucket exists 
        '''
        pc_cmd='pls.py -c pl summarize {}'
        cmd=pc_cmd.format(self.nameBuck)
        cmdOut=os.poen(cmd).readlines()
        SubLogger(logging.CRITICAL, cmdOut)

    def full(self):
        '''
        Test whether the bucket containts the same scene than the local list.
        It test the number of scene and match each of them

        out:
            full (bool): the bucket is full
        '''
        pass

    def script(self):
        '''
        Create a bash script for Job system creation

        out:
            script (str): script text
        '''
        pass




#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
