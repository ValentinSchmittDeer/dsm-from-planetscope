#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from glob import glob
from pprint import pprint
import numpy as np
from numpy. linalg import inv
from math import pi
import json

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc import DockerLibs, ASfMFunc, GeomFunc, MSSFunc
from PCT import pipelDFunc
from SSBP.blockFunc import SceneBlocks 


#from BlockProc import MSSFunc, ASP
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
def f(x):
    return x*x

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
        # 20200922_100156_1014 20200922_100155_1014
        parser.add_argument('dir', help='')

        args = parser.parse_args()
        logger.info("Arguments: " + str(vars(args)))

        gdal=DockerLibs.GdalPython()

        #---------------------------------------------------------------
        # Prepa
        #---------------------------------------------------------------
        dirIn=os.path.join(args.dir,'PDAL_DSM-Tiles')
        dirOut=os.path.join(args.dir,'PDAL_DSM-Tiles_Correct')
        if not os.path.exists(dirOut): os.mkdir(dirOut)
        #---------------------------------------------------------------
        # Epipolar
        #---------------------------------------------------------------
        lstPath=glob(os.path.join(dirIn,'*.tif'))
        lstPath.sort()
        out=ProcessStdout(name='Path', mode='list', inputCur=[os.path.basename(path) for path in lstPath] )
        for i in range(len(lstPath)):
            logger.info(out.ViewList(i))
            pathIn=lstPath[i]
            pathOut=pathIn.replace(dirIn, dirOut)
            print(gdal.gdal_calc(['--NoDataValue=-32767', '--overwrite',
                            '-A', pathIn, '--A_band 1',
                            '-B', pathIn, '--B_band 2',
                            '-C', pathIn, '--C_band 3',
                            '-D', pathIn, '--D_band 4',
                            '-E', pathIn, '--E_band 5',
                            '--calc "A" "C+numpy.sqrt((D*D+1)/E)" "E"',
                            '--outfile', pathOut,
                            ]))

    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
