#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
print (sys.version)
from pprint import pprint
from glob import glob

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, ProcessStdout

# dsm_from_planetscope libraries
from SSBP.SSBPlib_block import SceneBlocks 
from SSBP import nameBlock, nameBlockFile
from PCT import *
#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task

**************************************************************************
> Steps
**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def FindBDir(pathDir):
    regexDir=os.path.join(pathDir, nameBlock.format('*'))
    lstDir=[]
    for pathCur in glob(regexDir):
        nameB= os.path.basename(pathCur)
        lstDir.append((nameB, os.path.join(pathCur, nameBlockFile.format(nameB, 'SceneId.txt'))))
    return lstDir




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

        print('product level from PlIntern variable')
        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Wrong working directory")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        #---------------------------------------------------------------
        # Check planet_common 
        #---------------------------------------------------------------
        logger.info('# Check planet_common ')
        #if not PCTlib_product.CheckPC(): raise RuntimeError("The script must run in planet_common's env")
        
        #---------------------------------------------------------------
        # Read Repo
        #---------------------------------------------------------------
        logger.info('# Read Repo')
        #objBlocks=SceneBlocks([], args.i, 'dir')
        lstBlock=FindBDir(args.i)
        
        #---------------------------------------------------------------
        # Create sh script
        #---------------------------------------------------------------
        logger.info('# Create sh script')
        lstPathScp=[]
        for nameB, pathTxt in lstBlock:
            print(nameB)
            print('check available buckets')
            newBucket=PCTlib_product.PCTBucket(nameB,pathTxt)
            print(newBucket)
            sys.exit()
            print('create shell per block')
            pathScp= pathTxt.replace('SceneId.txt', 'CreationScp.sh')
            PIlib_creation.MakeScript_JSBatchMake(pathTxt, pathScp)
            lstPathScp.append(pathScp)

        
        print('create shell cript general')
        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
