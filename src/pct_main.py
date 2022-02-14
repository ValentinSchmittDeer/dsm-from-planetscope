#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob
from select import select

from OutLib.LoggerFunc import *
from VarCur import *
from SSBP.blockFunc import SceneBlocks 
from PCT.dataFunc import *
#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task
Planet common interface for product creation and downloading. It holds the
default repository sturcture and variable and runs planet_common tools
(scripts, functions) to read, create or download scenes according to the 
requested action: info|match|list|create|download
**************************************************************************
> info: list available buckets on GCP and compare them to descriptors and 
    local storage
> match: compare descriptors, local and cloud files
> list: list descriptors, local and cloud files
> create: fire off product creation requests to the GCP
> download: download scene from GCP to local storage (and resume failed downloads)
**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        print()
        logger = SetupLogger(name=__title__)
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        parser.add_argument('-i', required=True, help='Working directory')
        parser.add_argument('-n', required=True, help='Aoi Name')
        
        # Optional arguments
        parser.add_argument('-b',nargs='+', default=False, help='Block name to process (default: Fasle means all)')
        parser.add_argument('-l', help='Product process level (default: from VarCur)')
        parser.add_argument('-a', nargs='+', default=['info'], help='Action(s) <info|match|list|create|download> (default: info)')
        

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        if any([l.isupper() for l in args.n]): raise RuntimeError("Name AOI must be low case")
        if '_' in args.n or '-' in args.n: raise RuntimeError("Name AOI cannot contain '_' or '-'")
        
        if not args.l: 
            args.l= sorted(list(dicLevel.keys()))[0]
        else:
            if not args.l in lstLevel: raise RuntimeError("-l must be one of %s"% str(lstLevel))
        
        if False in [act in lstAction for act in args.a]: raise RuntimeError("-a must be one of %s"% str(lstAction))
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        print()
        #---------------------------------------------------------------
        # Check planet_common 
        #---------------------------------------------------------------
        logger.info('# Check planet_common ')
        if not CheckPC(): raise RuntimeError("The script must run in planet_common's env")
        
        logger.warning('%s mode(s)'% str(args.a))
        if __name__ == "__main__" and ('create' in args.a or 'download' in args.a):
            ans=input('Are you sure? (y|[n]):')
            if not ans=='y': raise RuntimeError("No creation mode")
        
        #---------------------------------------------------------------
        # Read Repo
        #---------------------------------------------------------------
        logger.info('# Read Repo')
        objInfo=SceneBlocks(args.i)
        if not objInfo.nbB: raise RuntimeError('No block available')

        #---------------------------------------------------------------
        # Loop per block
        #---------------------------------------------------------------
        logger.info('# Action per block')
        if args.b:
            lstBId=[objInfo.lstBId.index(blockCur) for blockCur in objInfo.lstBId if blockCur[0] in args.b]
        else: 
            lstBId=range(objInfo.nbB)

        for iB in lstBId:
            nameB, nbFeat=objInfo.lstBId[iB]
            logger.info(nameB)
            objCur=SceneBlocks(args.i, meth='dir', b=nameB)

            newBucket=PCTBucket(args.n, nameB, args.l, objCur.lstBFeat[0], args.i)
            
            if 'info' in args.a:
                logger.info(newBucket)

            if 'match' in args.a:
                print('Descriptors, Cloud and Local match: ', newBucket.Match())
            
            if 'create' in args.a:
                newBucket.Create()
            
            if 'list' in args.a:
                print(newBucket.List())

            if 'download' in args.a:
                newBucket.Down()

        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)