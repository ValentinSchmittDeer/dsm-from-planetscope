#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
import json
from datetime import datetime
from shutil import copy2
from pprint import pprint

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from SSBP import *
from PCT import metaDFunc

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task
Run a scene search command through custumer API and build up scene bocks
based on found products. Also create the data repository and block desciptors.
If a previous search result is fit in, the 'former search' mode skips 
the API search request.

**************************************************************************
> Create strict filter with input arguments
> Fire off the request and store it
> Create blocks
> Filter blocks (footprint)
> Extract extended metadata
> Couple block scenes (pairs)
> Record coverage image
> Filter blocks (B/H ratio)
> Replace coverage image
> Couple block scenes (pairs, triplet, etc)

**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
lstInst=('PS2', 'PS2.SD', 'PSB.SD')

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
        parser.add_argument('-i', required=True, help='Input geometry (geojson)')
        parser.add_argument('-o', required=True, help='Working directory for outputs')

        # Optional search parameters
        parser.add_argument('-iSrch', help='Input former search result (json), cancels another search step')
        
        # Block parameters
        parser.add_argument('-b', default='month', help='Block creation mode <month|one> (default: month)')
        parser.add_argument('-extMD', action='store_true', help='Read extended metadata (default: False)')
        parser.add_argument('-cov', action='store_true', help='Compute a coverage image with the number of scenes (default: False)')
        
        # Filter parameters
        parser.add_argument('-fFP', action='store_false', help='Footprint filtering (default: True)')
        parser.add_argument('-fBH', action='store_true', help='B/H filtering (default: False)')
        parser.add_argument('-fBHred', default=0, type=int, help='B/H filtering redundancy (default: 0)')

        # Database search strict parameters
        parser.add_argument('-itemType', nargs='+', default=['PSScene3Band', 'PSScene4Band'], help='Item type from Planet API list <PSScene3Band|PSScene4Band|...> (default: PSScene3Band, PSScene4Band)')
        parser.add_argument('-assetType', nargs='+', default=['basic_analytic', ], help='Asset type from Planet API list <basic_analytic|analytic|...> (default: basic_analytic)')
        parser.add_argument('-cloudUnder', type=int, default=10, help='Maximum cloud coverage, %% integer (default: 10)')
        parser.add_argument('-dateAcq', nargs=2, help='Acquisition date yyyy-mm-dd past in the order')
        parser.add_argument('-inst', nargs='+', default=['PS2'], help='Dove generation(s) <PS2|PS2.SD|PSB.SD> (default:PS2)')
        parser.add_argument('-viewAngle', type=float, help='Maximum view angle')
        parser.add_argument('-gsd', type=float, help='Maximum gsd')
        parser.add_argument('-quali', help='Product quality')
        parser.add_argument('-sunElevation', default=20, help='Minimum sun elevation (default: 20°)')
        lstKeySearch=('itemType', 'assetType', 'cloudUnder', 'dateAcq', 'inst', 'viewAngle', 'gsd', 'quali')

        args = parser.parse_args()

        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isfile(args.i) or not args.i.endswith('geojson'): raise RuntimeError("-i file not found")
        with open(args.i) as fileIn:
            featAoi=json.load(fileIn)
            crs=featAoi['crs']['properties']['name']
            if not crs=="urn:ogc:def:crs:OGC:1.3:CRS84": raise RuntimeError("Input geometry must be in WGS84 (EPSG:4326)")

        if args.iSrch:
            with open(args.iSrch) as fileIn:
                try:
                    lstFeat=json.load(fileIn)
                except json.decoder.JSONDecodeError as msg:
                    raise RuntimeError("Input search holds mistake: %s"% msg)
            checkSearch=False
        else:
            checkSearch=True
            
                
        if not os.path.isdir(args.o): raise RuntimeError("-o working directory not found")
        
        # Optional search parameters
        if not 0<=args.cloudUnder<=100: raise RuntimeError("-cloudUnder must be [0-100]")
        
        if args.dateAcq:
            for i in range(2):
                dateStr=args.dateAcq[i]
                dateObj=datetime.strptime(dateStr,'%Y-%m-%d')

                if i==1 and not dateObj>args.dateAcq[0]: raise RuntimeError("-dateAcq must be written in correct order")

                args.dateAcq[i]=dateObj
        
        if False in [instCur in lstInst for instCur in args.inst]: raise RuntimeError("-inst must be <PS2|PS2.SD|PSB.SD>")

        if not args.b in methodB: raise RuntimeError("-b must be one of %s"% str(methodB))        

        if args.fBH: 
            args.extMD=True
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        print()
        if not checkSearch: 
            logger.warning('Former search mode')
        else:
            logger.warning('New search mode')
            #---------------------------------------------------------------
            # Setup Auth
            #---------------------------------------------------------------
            logger.info('# Setup Auth')
            session=searchFunc.PlAuth()
            
            #---------------------------------------------------------------
            # Filter creation
            #---------------------------------------------------------------
            logger.info('# Strict Filtering')
            
            jsonParam=vars(args).copy()
            for keyCur in list(jsonParam.keys()):
                if not keyCur in lstKeySearch: del jsonParam[keyCur]
            
            jsonParam['geom']=featAoi
            
            nameSearchFull=fileSearchFull.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
            
            filterJson=searchFunc.MakeFiter(jsonParam,nameSearchFull)
            
            #---------------------------------------------------------------
            # Fire off request
            #---------------------------------------------------------------
            logger.info('# Fire off request ')
            lstFeat=searchFunc.PostRequest(session, filterJson)

            #PrintPsItem(lstFeat)

            # Store data
            pathOut=os.path.join(args.o, fileAoi.format(datetime.now().strftime('%Y%m%d_%H%M%S')))
            copy2(args.i,pathOut)


            pathJson= os.path.join(args.o, nameSearchFull)
            pathGeojson=pathJson.replace('json','geojson')
            logger.info('Saved in %s'% pathOut)

            objOut=tempGeojson.copy()
            objOut['name']=nameSearchFull.split('.')[0]
            del objOut['Features']

            fileGeojson=open(pathGeojson,'w')
            fileJson=open(pathJson,'w')
            fileGeojson.write(json.dumps(objOut, indent=2)[:-2])
            fileGeojson.write(',\n  "Features":[\n')
            fileJson.write('[\n')
            
            for i, feat in enumerate(lstFeat):
                lineEnd=',\n'
                if not i: lineEnd=''
                fileGeojson.write(lineEnd+json.dumps(feat))
                fileJson.write(lineEnd+json.dumps(feat))

            fileGeojson.write(']\n}')
            fileGeojson.close()
            fileJson.write(']')
            fileJson.close()

            del jsonParam, objOut, feat, filterJson

        logger.info('%i found scenes'% len(lstFeat))
        
        #---------------------------------------------------------------
        # Block creation
        #---------------------------------------------------------------
        logger.info('# Block creation')
        objBlocks=blockFunc.SceneBlocks(args.o, meth='dir')
        if not objBlocks.nbB:
            del objBlocks
            objBlocks=blockFunc.SceneBlocks(args.o, lstIn=lstFeat, meth=args.b)
        
        logger.info(objBlocks)
        del lstFeat, objBlocks

        #---------------------------------------------------------------
        # Block first filtering
        #---------------------------------------------------------------
        if args.fFP:
            logger.info('# Block footprint filtering')
            filterFunc.FilterBlocks(args.o, 'fp')
            objBlocks=blockFunc.SceneBlocks(args.o, meth='dir')
            logger.info(objBlocks)
            del objBlocks

        #---------------------------------------------------------------
        # Include Ext MD
        #---------------------------------------------------------------
        if args.extMD:
            logger.info('# Include extended metadata')
            if metaDFunc.CheckPC():
                lstMdCur=('sat:alt', 'sat:lat', 'sat:lng', 'sat:off_nadir', 'sat:satellite_azimuth_mean')
                metaDFunc.ExtractMD_Blocks(args.o,lstMdCur)
                del lstMdCur
            else:
                logger.error('The extended metadata retrieval needs planet_common env and it is not accessible. You can use -extMD to stop reading extended MD and -fBH to stop the B/H filtering (which needs B/H info from extended MD). The process will continue without extended MD and B/H filtering')
                args.extMD=False
                args.fBH=False
        
        #---------------------------------------------------------------
        # Scene coupling
        #---------------------------------------------------------------
        logger.info('# Scene coupling')
        blockFunc.StereoCoupling(args.o)
        
        #---------------------------------------------------------------
        # Block Coverage
        #---------------------------------------------------------------
        if args.cov:
            logger.info('# Block Coverage')
            blockFunc.Coverage(args.o, featAoi)
        
        #---------------------------------------------------------------
        # Block B/H filtering
        #---------------------------------------------------------------
        if args.fBH:
            logger.info('# Block B/H filtering and block update')

            filterFunc.FilterBlocks(args.o, 'bh', aoi=featAoi, red=args.fBHred)
            objBlocks=blockFunc.SceneBlocks(args.o, meth='dir')
            logger.info(objBlocks)
            del objBlocks

            # Update Coverage
            if args.cov: blockFunc.Coverage(args.o, featAoi)
            
            # Update stereo
            blockFunc.StereoCoupling(args.o, moreComb=True)

            

    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
