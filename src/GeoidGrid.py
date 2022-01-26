#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import numpy as np

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
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
        path='/home/valentinschmitt/pl/planet_common/Data/01_RefData/01_Stuttgart/GCG2016.csv'
        fileOut=open(path, 'w')
        fileOut.write('; '.join(['LatD', 'LongD', 'LatG', 'LongG', 'GCG2026\n']))
        for longD in np.linspace(9.0499,9.3147,10):
            for latD in np.linspace(48.6959,48.8797,10):
                lstOut=[str(round(latD,5)), str(round(longD,5)), str(round(latD*200/180,5)), str(round(longD*200/180,5))+'\n']
                fileOut.write('; '.join(lstOut))

        fileOut.close()

        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
