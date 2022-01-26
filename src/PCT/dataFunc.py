#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from datetime import datetime
from glob import glob
from pprint import pprint

from OutLib.LoggerFunc import *
from VarCur import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['CheckPC', 'PCTBucket']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
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
    
    nameAoi (str): AOI name
    nameBlock (str): block name
    pathSceneID (str): scene id file
    out:
        PCTBucket (obj):
            # Descriptor
            bId (str): block name
            nameBuck (str): bucket name
            tupleLevel (tuple): tuple with standard names with respect to the product level
            lstDescFeat (tuple): from desciptor, list of scene ID 
            nbDescFeat (int): from desciptor, number of scenes
            # Local
            dir (str): block directory
            dirData (str): black data directory
            lstLocFeat (list): from local, list of scene id
            nbLocFeat (int): from local, number of scenes
            sizeLoc (float): from local, byte weight of the dataset
            # Cloud
            urlBuck (str): URL of the bucket
            exists (bool): is the bucket on cloud (storage)
            lstCloFeat (list): from the cloud, list of scene ID
            nbCloFeat (int): from the cloud, number of scenes
            sizeClo (int): from the cloud, byte weight of the dataset
            lstCloData (list of list): list with (sceneName.tif, size, sceneName.RPC, size, sceneName.json, size ...)
    '''
    def __init__(self, nameAoi, nameBlock, levelCur, lstFeat, pathWorkDir):        
        # Descriptor
        self.bId=nameBlock
        self.nameBuck=nameBucket.format(nameAoi, nameBlock, levelCur)
        self.tupleLevel=dicLevel[levelCur]
        
        if not lstFeat: SubLogger('CRITICAL', 'lstFeat is empty')
        self.lstDescFeat=tuple([feat['id'] for feat in lstFeat])
        self.nbDescFeat=len(self.lstDescFeat)
        
        
        # Local
        self.dir=os.path.join(pathWorkDir, nameBlock)
        self.dirData=os.path.join(self.dir, self.nameBuck)
        
        self.lstLocFeat=[]
        extLoc=self.tupleLevel[1].replace('{}','')
        if os.path.exists(self.dirData):
            self.sizeLoc=0
            grepLoc=os.path.join(self.dirData, self.tupleLevel[1].format('*'))
            for pathCur in glob(grepLoc):
                nameFeat=os.path.basename(pathCur).replace(extLoc, '')
                self.lstLocFeat.append(nameFeat)
                self.sizeLoc+=os.path.getsize(pathCur)
        else:
            self.sizeLoc=0
        self.nbLocFeat=len(self.lstLocFeat)


        # Storage cloud
        from planet_common.client import pls_summarize, urls
        from planet_common.client import storage
        from requests.exceptions import HTTPError

        self.cloud='pl'
        urls.set_urls(self.cloud)

        lstArgs=['-c', 'pl', self.nameBuck]
        subparser=pls_summarize.get_parser()
        subargs=subparser.parse_args(lstArgs)

        if subargs.storage_url is None:
            subargs.storage_url=urls.PL_STORAGE_URL
            self.urlBuck=os.path.join(urls.PL_STORAGE_URL, 'v0/scenes', self.nameBuck)

        it=storage.BucketIterator(subargs.bucket,
                    scene_filter=storage.SceneFilter(args=subargs))
        
        self.lstCloFeat=[]
        self.lstCloData=[]
        self.sizeClo=0
        extClo=self.tupleLevel[1].replace('{}','')
        try:
            for scene_json in it:
                if scene_json['name'].endswith('.tif'):
                    self.lstCloFeat.append(scene_json['name'].replace(extClo,''))
                    self.sizeClo+=scene_json['file_size']
                    self.lstCloData.append([scene_json['name'],scene_json['file_size']])
                else:
                    nb=len(self.lstCloFeat)
                    i=[j 
                        for j in range(-1,-nb-1,-1) 
                            if scene_json['name'].startswith(self.lstCloFeat[j])][0]
                    self.lstCloData[i]+=[scene_json['name'],scene_json['file_size']]
            
            self.exists=True
            self.nbCloFeat=len(self.lstCloFeat)
        except HTTPError:
            self.exists=False
            self.nbCloFeat=0
            self.sizeClo=0
        except IndexError:
            self.exists=True
            self.nbCloFeat=-1
            self.sizeClo=-1

    def __str__(self):
        #ljust(
        strOut='{obj.nameBuck} (exists: {obj.exists})\n'.format(obj=self)
        strOut+='       |   Descr  |   Cloud  |   Local  |\n'
        strOut+='Nb Feat|{obj.nbDescFeat:^10d}|{obj.nbCloFeat:^10d}|{obj.nbLocFeat:^10d}|\n'.format(obj=self)
        
        lstSize=[self.sizeClo, self.sizeLoc]
        lstStr=['','']
        for i in range(2):
            j=0
            while lstSize[i]>1024:
                lstSize[i]/=1024
                j+=1
            lstStr[i]='%.1f %s'% (lstSize[i],('B','KB','MB','GB')[j])
        strOut+='Size   |    /     |{0[0]:^10s}|{0[1]:^10s}|'.format(lstStr)
        return strOut

    def Match(self):
        '''
        Check the equivalence between descriptor, cloud bucket and local files

        out:
            match (bool): local desciptor and cloud bucket match
        '''
        if not self.exists:
            SubLogger('ERROR', 'cloud bucket not found')
            return False

        match=True
        SubLogger('INFO', 'Descriptor to Cloud')
        # Number
        if not self.nbDescFeat==self.nbCloFeat: 
            SubLogger('ERROR', 'different scene number')
            match=False
        # Descriptor 2 Cloud
        count=[1 for itemDesc in self.lstDescFeat 
                    if itemDesc in self.lstCloFeat]
        if not self.nbDescFeat==sum(count): 
            SubLogger('ERROR', 'missing scene on the cloud')
            match=False
        
        SubLogger('INFO', 'Cloud to Local')
        # Number
        if not self.nbCloFeat==self.nbLocFeat: 
            SubLogger('ERROR', 'different scene number')
            match=False
        # Cloud 2 Local
        count=[1 for itemClo in self.lstCloFeat 
                    if itemClo in self.lstLocFeat]
        if not self.nbDescFeat==sum(count): 
            SubLogger('ERROR', 'missing scene on the cloud')
            match=False
        # Size
        if not self.sizeLoc==self.sizeClo:
            SubLogger('ERROR', 'different size')
            match=False

        return match
        
    def List(self):
        '''
        List the feature ID

        out:
            PCTBucket (obj): updated object
                batchId (str):
        '''
        if not self.exists:
            SubLogger('ERROR', 'cloud bucket not found')
            return False

        strOut='|       Descriptor       | Cloud | Local |\n'
        strOUt='|                    |{0:s}|{0:s}|\n'.format(self.tupleLevel[1].replace('{}',''))
        for itemDesc in self.lstDescFeat:
            strOut+='|{0:<24s}|'.format(itemDesc)
            if itemDesc in self.lstCloFeat:
                strOut+='{0:^7s}|'.format('ok')
            else:
                strOut+='{0:^7s}|'.format('-')
            if itemDesc in self.lstLocFeat:
                strOut+='{0:^7s}|'.format('ok')
            else:
                strOut+='{0:^7s}|'.format('-')
            strOut+='\n'

        return strOut

    def Create(self):
        '''
        Create the bucket by job system batch. It stores every 
        information into a txt file 'nameJobFile'

        out:
            out (bool): return code 0=ok, 1=error
            PCTBucket (obj): updated object
                batchId (str): job system batch ID
                batchUrl (str): URL of the job system batch
        '''
        if self.exists:
            SubLogger('ERROR', 'cloud bucket already exists')
            return True

        from planet_common.client import jobs, urls

        # Create job system batch
        self.batchId = jobs.create_batch(submitter="valentin", description=self.nameBuck)
        #self.batchId = 1002409971
        SubLogger('INFO', '%s created by job batch %s'% (self.nameBuck, self.batchId))
        
        urls.set_urls(self.cloud)
        self.batchUrl='%s/v0/batch/%s' % (urls.PL_JOBS_URL, self.batchId)
        
        #Store info
        j=0
        pathTxt=os.path.join(self.dir, nameJobFile.format(self.bId, j))
        while os.path.exists(pathTxt):
            j+=1
            pathTxt=os.path.join(self.dir, nameJobFile.format(self.bId, j))
        fileOut=open(pathTxt, 'w')
        fileOut.write('Update time: %s\n'% datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        fileOut.write('Block ID: %s\n'% self.bId)
        fileOut.write('Bucket ID: %s\n'% self.nameBuck)
        fileOut.write('Bucket URL: %s\n'% self.urlBuck)
        fileOut.write('Batch ID: %s\n'% self.batchId)
        fileOut.write('Batch URL: %s\n'% self.batchUrl)
        fileOut.write('Batch Status: plj_query.py -c pl --limit %i --batch %s\n'% (self.nbDescFeat+10, self.batchId))
        fileOut.write('\nCommands (%i):\n'% self.nbDescFeat)

        # Upload processes
        procBar=ProcessStdout(name='Upload processes',inputCur=self.nbDescFeat)
        for i in range(self.nbDescFeat):
            procBar.ViewBar(i)
            itemDesc=self.lstDescFeat[i]
            if itemDesc in self.lstCloFeat: 
                fileOut.write(itemDesc+': exists\n')
                continue

            fileOut.write(itemDesc+': ')

            strSubArgs='cmo -c pl --product={levelCode} --output-storage-bucket={bucketCur} --disable-cache-read --disable-cache-write --input-bucket={bucketIn} --input-scene={sceneId} --udm disabled --xml disabled'.format(
                        levelCode=self.tupleLevel[2],
                        bucketCur=self.nameBuck,
                        bucketIn='flock1',
                        sceneId=itemDesc+extSceneIn)
            lstArgs=['-c', 'pl', '-q',
                    '--quota-ram-mb=7200', 
                    '--timeout=7200', 
                    '--priority=1', 
                    '--profile=spot',
                    '--batch=%s'% self.batchId,
                    'product-processor',
                    'ARGS="%s"'% strSubArgs]
            cmd='plj_run.py '+' '.join(lstArgs)
            fileOut.write(cmd+'\n')
            os.system(cmd)

        fileOut.close()
        print()
        return False

    def Down(self):
        '''
        Main download function leading to Down_Download or Down_Sync

        out:
            out (bool): return code 0=ok, 1=error
        '''
        if not self.exists:
            SubLogger('ERROR', 'cloud bucket not found')
            return True

        if not os.path.exists(self.dirData): os.mkdir(self.dirData)
        
        procBar=ProcessStdout(name='Download features',inputCur=self.nbDescFeat)
        for i in range(self.nbDescFeat):
            procBar.ViewBar(i)
            itemDesc=self.lstDescFeat[i]
            itemName=self.tupleLevel[1].format(itemDesc)

            if not itemDesc in self.lstCloFeat: 
                SubLogger('WARNING', 'Scene not found on the cloud bucket: %s'% itemDesc)
                continue

            tupCloData=[item for item in self.lstCloData if itemName==item[0]][0]
            if not tupCloData: SubLogger('CRITICAL', 'Devlopment issue')

            cmd='cur=$(pwd) ; cd %s '% self.dirData
            for j in range(len(tupCloData)):
                if not type(tupCloData[j])==str: continue
                
                pathLocFeat=os.path.join(self.dirData,tupCloData[j])
                if os.path.exists(pathLocFeat) and os.path.getsize(pathLocFeat)==tupCloData[j+1]: continue

                cmd+='; pls.py download -c pl -q {bucket} {sceneId}'.format(
                        bucket=self.nameBuck,
                        sceneId=tupCloData[j])
            
            if len(cmd.split(';'))==2: continue
            cmd+=' ; cd $cur'
            os.system(cmd)
        
        print()





#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
