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
        objBlocks=SceneBlocks([], args.i, 'dir')
        
        #---------------------------------------------------------------
        # Loop per block
        #---------------------------------------------------------------
        logger.info('# Action per block')
        
        if not args.b:
            lstLoop=range(objBlocks.nbB)
        else:
            lstLoop=[i for i in range(objBlocks.nbB) if objBlocks.lstBId[i][0] in args.b]
        
        for iB in lstLoop:
            nameB=objBlocks.lstBId[iB][0]

            print()
            logger.info(nameB)
            newBucket=PCTBucket(nameB, args.l, objBlocks.lstBFeat[iB], args.i)
            
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
        parser.add_argument('-b',nargs='+', default=False, help='Block name to process (default: Fasle means all)')
        parser.add_argument('-l', help='Product process level (default: from VarCur)')
        parser.add_argument('-a', nargs='+', default=['info'], help='Action(s) <info|match|list|create|download> (default: info)')
        

        argsMain = parser.parse_args()
        
        Main(argsMain)

        print('\nEND, Continue with bundle adjsut')        
