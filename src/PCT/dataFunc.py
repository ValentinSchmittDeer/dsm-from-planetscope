#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from datetime import datetime
from glob import glob
from pprint import pprint

from OutLib.LoggerFunc import *

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

    nameBlock (str): block name
    pathSceneID (str): scene id file
    out:
        PCTBucket (obj):
            nameBuck (str): bucket name
            level (str): scene process level
            nbLocFeat (int): number of scene from local
            lstLocFeat (tuple): list of scene id from local
            exists (bool): existing bucket on cloud
            nbCloFeat (int): number of scene from cloud
            sizeClo (int): bucket size from cloud 
    '''
    def __init__(self, nameBlock, pathSceneID, levelCur):
        from PCT import nameBucket, dicLevel
        

        self.bId=nameBlock
        self.nameBuck=nameBucket.format(nameBlock, levelCur)
        #self.nameBuck='aaa_seths_test_collects_413_l1b_multispectral'
        self.tupleLevel=dicLevel[levelCur]
        
        # Local
        if not os.path.exists(pathSceneID): SubLogger('CRITICAL', 'pathSceneID not found')
        with open(pathSceneID) as fileIn:
            self.lstLocFeat=tuple([lineCur.strip() for lineCur in fileIn.readlines()])
        self.nbLocFeat=len(self.lstLocFeat)
        
        
        # Directory
        self.dir=os.path.dirname(pathSceneID)
        self.dirData=os.path.join(self.dir, self.nameBuck)
        if os.path.exists(self.dirData):
            self.sizeLoc=0
            for pathCur in glob(os.path.join(self.dirData, '*')):
                if pathCur.endswith('json'): continue
                self.sizeLoc+=os.path.getsize(pathCur)
        else:
            self.sizeLoc=-1
        
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
        self.sizeClo=0
        try:
            for scene_json in it:
                self.sizeClo+=scene_json['file_size']
                if scene_json['name'].endswith('.tif'):
                    self.lstCloFeat.append([scene_json['name'],scene_json['file_size']])
                else:
                    grepClo=self.tupleLevel[1].replace('{}','')
                    i=[j 
                        for j in range(len(self.lstCloFeat)) 
                            if scene_json['name'].startswith(self.lstCloFeat[j][0].replace(grepClo,''))][0]
                    self.lstCloFeat[i]+=[scene_json['name'],scene_json['file_size']]
            
            self.exists=True
            self.nbCloFeat=len(self.lstCloFeat)
        except HTTPError:
            self.exists=False
            self.nbCloFeat=-1
            self.sizeClo=-1

    def __str__(self):
        strOut='{obj.nameBuck} (exist: {obj.exists})\n'.format(obj=self)
        strOut+='       |  Local  |  Cloud  |\n'
        strOut+='Nb Feat|  {obj.nbLocFeat:5}  |  {obj.nbCloFeat:5}  |\n'.format(obj=self)
        
        sizeTup=[self.sizeLoc,self.sizeClo]
        sizeFact=[]
        for i in range(2):
            j=0
            while sizeTup[i]>1024:
                sizeTup[i]/=1024
                j+=1
            sizeFact.append(('B','KB','MB','GB')[j])
        strOut+='Size   |  {0[0]:.1f}{1[0]} |  {0[1]:.1f}{1[1]} |'.format(sizeTup,sizeFact)
        return strOut

    def Match(self):
        '''
        Check the equivalence between local files and cloud bucket

        out:
            match (bool): local desciptor and cloud bucket match
        '''
        if not self.exists:
            SubLogger('ERROR', 'cloud bucket not found')
            return False

        if not self.nbCloFeat==self.nbLocFeat:
            SubLogger('ERROR', 'different scene numbers')
            return False

        from PCT import nameFeat
        grepLoc=nameFeat.replace('{}','')
        grepClo=self.tupleLevel[1].replace('{}','')
        
        countLoc=[1 
                    for itemLoc in self.lstLocFeat 
                        if itemLoc.replace(grepLoc,grepClo) in [i for i,j,k,l in self.lstCloFeat]]
        if not self.nbLocFeat==sum(countLoc):
            SubLogger('ERROR', 'missing scenes on cloud bucket')
            return False

        countClo=[1 
                    for itemClo,j,k,l in self.lstCloFeat 
                        if itemClo.replace(grepClo,grepLoc) in self.lstLocFeat]
        
        if not self.nbCloFeat==sum(countClo):
            SubLogger('ERROR', 'additional scenes on cloud bucket')
            return False

        if not self.sizeLoc==self.sizeClo:
            SubLogger('ERROR', 'cloud and local with different size')
            return False

        return True
        
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

        from PCT import dicLevel, nameFeat
        grepLoc=nameFeat.replace('{}','')
        grepClo=self.tupleLevel[1].replace('{}','')
        lstDirData=[os.path.basename(pathCur) for pathCur in glob(os.path.join(self.dirData, '*'))]

        strOut='Descriptor => Cloud => Local\n{0} => {1} => {1}\n'.format(grepLoc,grepClo)
        # Descriptor
        for itemLoc in self.lstLocFeat:
            strOut+=itemLoc.replace(grepLoc,'')
            
            # Cloud bucket
            if itemLoc.replace(grepLoc,grepClo) in [i for i,j,k,l in self.lstCloFeat]:
                strOut+=' => %s'% itemLoc.replace(grepLoc,'')
            
            # Local directory   
            if itemLoc.replace(grepLoc,grepClo) in lstDirData:
                strOut+=' => %s'% itemLoc.replace(grepLoc,'')

            strOut+='\n'

        strOut+='\nMatch: %s'% self.Match()
        return strOut

    def Create(self):
        '''
        Create the bucket by job system batch. It stores every 
        information into a txt file 'nameJobFile'

        out:
            out (bool): return code 0=ok, 1=error
            PCTBucket (obj): updated object
                batchId (str):
        '''
        # Create job system batch
        if self.exists:
            SubLogger('ERROR', 'cloud bucket already exists')
            return True

        from PCT import nameJobFile, nameFeat
        from planet_common.client import jobs, urls

        # Job system batch
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
        fileOut.write('Batch Status: plj_query.py -c pl --limit %i --batch %s\n'% (self.nbLocFeat+10, self.batchId))
        fileOut.write('\nCommands (%i):\n'% self.nbLocFeat)

        # Upload processes
        grepLoc=nameFeat.replace('{}','')
        grepClo=self.tupleLevel[1].replace('{}','')

        procBar=ProcessStdout(name='Upload processes',inputCur=self.nbLocFeat)
        for i in range(self.nbLocFeat):
            procBar.ViewBar(i)
            featID=self.lstLocFeat[i]
            if featID.replace(grepLoc,grepClo) in [i for i,j,k,l in self.lstCloFeat]: continue

            fileOut.write(featID+': ')

            strSubArgs='cmo -c pl --product={levelCode} --output-storage-bucket={bucketCur} --disable-cache-read --disable-cache-write --input-bucket={bucketIn} --input-scene={sceneId} --udm disabled --xml disabled'.format(
                        levelCode=self.tupleLevel[2],
                        bucketCur=self.nameBuck,
                        bucketIn='flock1',
                        sceneId=featID)
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
        return False

    def Download_old(self):
        '''
        Download the bucket to a folder data_<level>

        out:
            out (bool): return code 0=ok, 1=error
        '''
        if os.path.exists(self.dirData):
            SubLogger('ERROR', 'Local data directory already exists')
            return True
        os.mkdir(self.dirData)

        cmd='cur=$(pwd) ; cd {dir} ; pls.py download -c pl --fast-skip {bucket} ; cd $cur'.format(dir=pathDataDir,
                                                                                            bucket=self.nameBuck)
        print(cmd)
        os.system(cmd)

    def Down(self):
        '''
        Main download function leading to Down_Download or Down_Sync

        out:
            out (bool): return code 0=ok, 1=error
        '''
        if not self.exists:
            SubLogger('ERROR', 'cloud bucket not found')
            return True

        from PCT import nameFeat
        grepLoc=nameFeat.replace('{}','')
        grepClo=self.tupleLevel[1].replace('{}','')

        if not os.path.exists(self.dirData): os.mkdir(self.dirData)
        
        procBar=ProcessStdout(name='Download features',inputCur=self.nbCloFeat)
        for i in range(self.nbCloFeat):
            procBar.ViewBar(i)
            
            if not self.lstCloFeat[i][0].replace(grepClo,grepLoc) in self.lstLocFeat: continue

            cmd='cur=$(pwd) ; cd %s '% self.dirData
            for j in range(len(self.lstCloFeat[i])):
                if not type(self.lstCloFeat[i][j])==str: continue
                featCloId=self.lstCloFeat[i][j]
                
                pathLocFeat=os.path.join(self.dirData,featCloId)
                if os.path.exists(pathLocFeat) and os.path.getsize(pathLocFeat)==self.lstCloFeat[i][j+1]: continue

                cmd+='; pls.py download -c pl -q {bucket} {sceneId}'.format(
                        bucket=self.nameBuck,
                        sceneId=featCloId)
            
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
        
