#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, logging, argparse
from PVL_Logger import SetupLogger, ProcessStdout
from pprint import pprint

import json

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
     Main Task
Loop the USGS tile download from the Amazon AWS bucket. It follows a tile
geojson descriptor with tile name asa "location" attribute.

**************************************************************************
> 
**************************************************************************
'''% (__name__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
dicProj={'CA': ('CA_MountainPass_2019_D19', 'CA_MountainPass_B1_2019', 'USGS_OPR_CA_MountainPass_2019_D19_{}.tif'),
         'WA': ('WA_FEMAHQ_2018_D18', 'WA_FEMAHQ_B2A_2018', 'USGS_OPR_WA_FEMAHQ_2018_D18_be_{}.tif')}

urlDown='https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/OPR/Projects/{0[0]}/{0[1]}/TIFF'

engDown='curl'
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        print()
        logger = SetupLogger()
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        #Optional arguments
        parser.add_argument('-i', required=True, help='Tile file .geojson from LiDAR expolrer')
        parser.add_argument('-p', required=True, help='USGS mission shortcut (CA|WA)')
        parser.add_argument('-o', required=True, help='Output directory')

        args = parser.parse_args()
        
        logger.info("Arguments: " + str(vars(args)))
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.exists(args.i) or not args.i.endswith('.geojson'): raise RuntimeError("Input file incorrect")
        if not os.path.isdir(args.o): raise RuntimeError("Output directory incorrect")
        if not args.p in dicProj: raise RuntimeError("Unknown project shortcut:"+ str(dicProj.keys()))
        #---------------------------------------------------------------
        # Read file
        #---------------------------------------------------------------
        with open(args.i) as fileIn:
            objIn=json.load(fileIn)

        if not objIn: raise RuntimeError("Input file empty")

        lstId=[str(i['properties']['fid']) for i in objIn['features']]
        #---------------------------------------------------------------
        # Download
        #---------------------------------------------------------------
        procLog=ProcessStdout(name='Down Tiles', mode='list', inputCur=lstId)

        for i,featCur in enumerate(objIn['features']):
            tileName=os.path.basename(featCur['properties']['location']).split('.')[0]
            fileName=dicProj[args.p][-1].format(tileName)

            urlTile=os.path.join(urlDown.format(dicProj[args.p]), fileName)
            
            pathOut=os.path.join(args.o, fileName)
            logger.info(procLog.ViewList(i))

            if not os.path.exists(pathOut):
                cmd='{} {} > {}'.format(engDown,
                                        urlTile,
                                        pathOut)
                print(cmd)
                os.system(cmd)
            
            
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
