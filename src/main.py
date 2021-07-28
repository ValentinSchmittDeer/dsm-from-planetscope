#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint

from PVL.PVL_Logger import SetupLogger, ProcessStdout
from PVL.PVL_Rpc import *

import ssbp_main
import pct_main 
import asfm_main
import mss_main 
#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task

**************************************************************************
> Steps
**************************************************************************
'''% (__name__,__version__,__author__),
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
        logger = SetupLogger(name=__name__)
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        #Positional input
        parser.add_argument('none',help='No args yet')
        
        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        #if os.path.isfile(args.juju): raise RuntimeError("juju exists")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        #---------------------------------------------------------------
        # Step
        #---------------------------------------------------------------
        logger.info('# Process')
        print('ssbp_main.Main(ssbp_main.GetArgs())')
        print('pct_main.Main(pct_main.GetArgs())')
        print('asfm_main.Main(asfm_main.GetArgs())')
        print('mss_main.Main(mss_main.GetArgs())')
        
        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
