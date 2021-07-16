#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, ProcessStdout
from PVL.PVL_Rpc import *

# dsm_from_planetscope libraries
from ASfM.ASfMlib_asp import AspUtility as AspObj
from ASfM import *
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
        pathRepo='/vagrant/Data/02_Providence/'
        pathDem='/vagrant/Data/01_RefData/02_Providence/n35_w11X_1arc_v3_Providence_EPSG4326_ElliH.tif'
        bId='B202010'
        featIdTest=['20210328_151810_1020_1A_Analytic_gB.tif','20210328_151811_1020_1A_Analytic_gB.tif']
        #featIdTest=['20210328_151810_1020_1A_Analytic_gB.tif','20210412_151407_0f21_1A_Analytic_gB.tif']

        logger.info(bId)
        pathDict=ASfMlib_ba.BlockPathDict(pathRepo, bId, pathDem)
        #---------------------------------------------------------------
        # Test
        #---------------------------------------------------------------
        asp=AspObj()

        lstPath=[os.path.join(pathDict['pProcData'], name) for name in featIdTest]
        argsCur=ASfMlib_ba.BunAdjParam(pathDict, lstPath)
        pprint(argsCur.KeyPoints())
        asp.bundle_adjust(argsCur.KeyPoints())
        pprint(argsCur.EO())
        asp.bundle_adjust(argsCur.EO())
        pprint(argsCur.IO())
        asp.bundle_adjust(argsCur.IO())
        


    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
