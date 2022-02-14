#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
import json
import rasterio

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP import *
from PCT import *
from BlockProc import *

# dsm_from_planetscope main scripts
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
Fully automatic process not ready yet. It misses results assessment during 
the scene creation, the bundle adjustement controle (for to moment with 
tables and plots), etc. Nevertheless, that script prints out the commands
lines according to the incoming arguments
**************************************************************************
> SSBP
> PCT
> ASfM
> controle with Visu_AssessBa, Visu_EpipolarGeometry, visu_KP-PDF
> MSS
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
        parser.add_argument('-i', required=True, help='Input geometry (geojson)')
        parser.add_argument('-o', required=True, help='Working directory for outputs')
        parser.add_argument('-n', required=True, help='Aoi Name')
        parser.add_argument('-dem', required=True, help='Reference DEM path (SRTM) with ellipsoidal height (WGS84)')
        parser.add_argument('-epsg', required=True, help='Current ESPG used by initial ortho')
        
        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isfile(args.i) or not args.i.endswith('geojson'): raise RuntimeError("-i file not found")
        with open(args.i) as fileIn:
            featAoi=json.load(fileIn)
            crs=featAoi['crs']['properties']['name']
            if not crs=="urn:ogc:def:crs:OGC:1.3:CRS84": raise RuntimeError("Input geometry must be in WGS84 (EPSG:4326)")
        if not os.path.isdir(args.o): raise RuntimeError("-o working directory not found")
        if any([l.isupper() for l in args.n]): raise RuntimeError("Name AOI must be low case")
        if '_' in args.n or '-' in args.n: raise RuntimeError("Name AOI cannot contain '_' or '-'")
        if not os.path.isfile(args.dem): raise RuntimeError("DEM file not found")
        with rasterio.open(args.dem) as fileIn: 
            if not fileIn.crs==4326: raise RuntimeError("DEM EPSG must be 4326 (WGS 84, geographic)")
        args.l= sorted(list(dicLevel.keys()))[0]

        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        print()

        #---------------------------------------------------------------
        # Command lines
        #---------------------------------------------------------------
        print(parser.description)
        logger.info('# Command line SSBP')
        print('./src/ssbp_main.py -i %s -o %s -fBH -fBHred 2 -cov'% (args.i, args.o))
        print()
        logger.info('# Command line PCT')
        print('./src/pct_main.py -i %s -n %s -a create'% (args.o, args.n))
        print('./src/pct_main.py -i %s -n %s -a info'% (args.o, args.n))
        print('./src/pct_main.py -i %s -n %s -a download'% (args.o, args.n))
        print()
        logger.info('# Command line ASfM')
        print('./src/asfm_main.py -i %s -dem %s -epsg %s'% (args.o, args.dem, args.epsg))
        print()
        logger.info('# Command line Visu_AssessBa')
        strOut='./src/Visu_AssessBa.py -init '
        strOut+=os.path.join(args.o, 'Bx', nameBucket.format(args.n, 'Bx', args.l)+'_ProcData')
        strOut+=' -ba '
        strOut+=os.path.join(args.o, 'Bx', 'ASP_KeyPoints')+' '
        strOut+=os.path.join(args.o, 'Bx', 'ASP_Extrinsic')+' '
        strOut+=os.path.join(args.o, 'Bx', 'ASP_Intrinsic')+' '
        print(strOut+'-table -eo -io ')
        print(strOut+'-graphEO -e -ori')
        print(strOut+'-graphKP')
        print()
        logger.info('# Command line Visu_EpipolarGeometry')
        strOut='./src/mss_main.py -img1 '
        strOut+=os.path.join(args.o, 'Bx', nameBucket.format(args.n, 'Bx', args.l)+'_ProcData', 'Image1.tif')
        strOut+=' -img2 '
        strOut+=os.path.join(args.o, 'Bx', nameBucket.format(args.n, 'Bx', args.l)+'_ProcData', 'Image2.tif')
        print(strOut)
        print()
        logger.info('# Command line Visu_KP-PDF')
        strOut='./src/Visu_KP-PDF.py -t '
        strOut+=os.path.join(args.o, 'Bx', 'ASP_KeyPoints', 'KP-initial_residuals_no_loss_function_pointmap_point_log.geojson')
        strOut+=' -p '
        strOut+=os.path.join(args.o, 'Bx', 'ASP_Extrinsic', 'EO-initial_residuals_no_loss_function_pointmap_point_log.geojson')+' '
        strOut+=os.path.join(args.o, 'Bx', 'ASP_Extrinsic', 'EO-final_residuals_no_loss_function_pointmap_point_log.geojson')
        print(strOut)
        print()
        logger.info('# Command line MSS')
        print('./src/mss_main.py -i %s -dem %s -epsg %s'% (args.o, args.dem, args.epsg))

        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
