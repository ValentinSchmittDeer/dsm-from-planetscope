#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob
from select import select

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
    lstGlob=glob(regexDir)
    lstGlob.sort()
    
    lstDir=[]
    for pathCur in lstGlob:
        nameB= os.path.basename(pathCur)
        lstDir.append((nameB, os.path.join(pathCur, nameBlockFile.format(nameB, 'SceneId.txt'))))
    return lstDir

def Main(args):
    try:
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.i): raise RuntimeError("Working directory not found")
        
        if not args.l: 
            args.l= list(dicLevel.keys())[0]
        else:
            if not args.l in lstLevel: raise RuntimeError("-l must be one of %s"% str(lstLevel))
        
        if False in [act in lstAction for act in args.action]: raise RuntimeError("-action must be one of %s"% str(lstAction))
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        #---------------------------------------------------------------
        # Check planet_common 
        #---------------------------------------------------------------
        logger.info('# Check planet_common ')
        if not PCTlib_product.CheckPC(): raise RuntimeError("The script must run in planet_common's env")
        
        logger.warning('%s mode'% args.action)
        if __name__ == "__main__" and (args.action=='create' or args.action=='download'):
            ans=input('Are you sure? (y|[n]):')
            if not ans=='y': raise RuntimeError("No creation mode")
        
        #---------------------------------------------------------------
        # Read Repo
        #---------------------------------------------------------------
        logger.info('# Read Repo')
        lstBlock=FindBDir(args.i)
        
        #---------------------------------------------------------------
        # Loop per block
        #---------------------------------------------------------------
        logger.info('# Action per block')
        
        lstPathScp=[]
        for nameB, pathTxt in lstBlock:
            if args.b and not nameB in args.b: continue
            
            print()
            logger.info(nameB)
            newBucket=PCTlib_product.PCTBucket(nameB,pathTxt, args.l)
            
            if 'match' in args.action:
                logger.info(newBucket)
                newBucket.Match()
            
            if 'create' in args.action:
                newBucket.Create()
            
            if 'list' in args.action:
                print(newBucket.List())

            if 'download' in args.action:
                newBucket.Down()

        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    
        print()
        logger = SetupLogger(name=__title__)
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        parser.add_argument('-i', required=True, help='Working directory')
        
        # Optional arguments
        parser.add_argument('-b',nargs='+', default=[], help='Block name to process (default: [] means all')
        parser.add_argument('-l', help='Product process level (default: from PCT.__ini__)')
        parser.add_argument('-action', nargs='+', default=['match'], help='script kind of action <match|list|create|download> (default: match)')
        

        argsMain = parser.parse_args()
        
        Main(argsMain)

        print('\nEND, Continue with bundle adjsut')        
