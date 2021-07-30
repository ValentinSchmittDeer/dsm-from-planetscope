#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import json
from datetime import datetime
from shutil import copy2

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
> Authentication
> Create filter with input arguments
> Fire off the request and store it
> Block creation and filtering
> Scene pair retrieval 
> Coverge image creation
> Create data repository and block desciptors

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

def Main(args):
    try:
        print()
        logger = SetupLogger(name=__title__)
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
            nameAoiOut=os.path.basename(args.i).split('.')[0]
            nameSearch=os.path.basename(args.iSrch).split('.')[0]
            checkSearch=False
        else:
            checkSearch=True
            nameSearch=nameSearchFull.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
            nameAoiOut=nameAoi.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
                
        if not os.path.isdir(args.o): raise RuntimeError("-o working directory not found")
        
        # Optional search parameters
        if not 0<=args.cloudUnder<=100: raise RuntimeError("-cloudUnder must be [0-100]")
        
        if args.dateAcq:
            if not len(args.dateAcq)==2: raise RuntimeError("-dateAcq must be 2 dates")
            for i in range(2):
                dateStr=args.dateAcq[i]
                dateObj=datetime.strptime(dateStr,'%Y-%m-%d')

                if i==1 and not dateObj>args.dateAcq[0]: raise RuntimeError("-dateAcq must be written in correct order")

                args.dateAcq[i]=dateObj
        
        if False in [instCur in lstInst for instCur in args.inst]: raise RuntimeError("-inst must be <PS2|PS2.SD|PSB.SD>")

        if not args.b in methodB: raise RuntimeError("-b must be one of %s"% str(methodB))        

        if args.fBH and not args.extMD: raise RuntimeError("The BH filtering needs access to extended metadata")
        
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

            filterJson=searchFunc.MakeFiter(jsonParam,nameSearch)
            
            #---------------------------------------------------------------
            # Fire off request
            #---------------------------------------------------------------
            logger.info('# Fire off request ')
            lstFeat=searchFunc.PostRequest(session, filterJson)

            #PrintPsItem(lstFeat)

            # Store search
            pathOut=os.path.join(args.o, nameAoiOut+'.geojson')
            copy2(args.i,pathOut)

            pathOut= os.path.join(args.o, nameSearch+'.json')
            with open(pathOut,'w') as fileOut:
                strOut=json.dumps(lstFeat, indent=2)
                fileOut.write(strOut)

            pathOut=pathOut.replace('json','geojson')
            with open(pathOut,'w') as fileOut:
                objOut=tempGeojson.copy()
                objOut['name']=nameSearch
                objOut['features']=lstFeat.copy()
                fileOut.write(json.dumps(objOut, indent=2))

        logger.info('%i found scenes'% len(lstFeat))
        
        #---------------------------------------------------------------
        # Block creation
        #---------------------------------------------------------------
        logger.info('# Block creation')
        objBlocks=blockFunc.SceneBlocks(lstFeat, args.o, args.b)
        logger.info(objBlocks)
        
        #---------------------------------------------------------------
        # Block first filtering
        #---------------------------------------------------------------
        if args.fFP:
            logger.info('# Block footprint filtering')
            filterFunc.FilterBlocks(objBlocks, 'fp')
            logger.info(objBlocks)

        #---------------------------------------------------------------
        # Include Ext MD
        #---------------------------------------------------------------
        if args.extMD:
            logger.info('# Include Ext MD')
            if metaDFunc.CheckPC():
                lstMdCur=('sat:alt', 'sat:lat', 'sat:lng', 'sat:off_nadir', 'sat:satellite_azimuth_mean')
                metaDFunc.ExtractMD_Blocks(objBlocks,lstMdCur)
                objBlocks.SatGeo2Cart()
            else:
                logger.error('The extended metadata retrieval needs planet_common env and it is not accessible. You can use -extMD to stop reading extended MD and -fBH to stop the B/H filtering (which needs B/H info from extended MD). The process will continue without extended MD and B/H filtering')
                args.extMD=False
                args.fBH=False
        
        #---------------------------------------------------------------
        # Scene coupling
        #---------------------------------------------------------------
        logger.info('# Scene coupling')
        objBlocks.StereoCoupling()
        logger.info(objBlocks)
        
        #---------------------------------------------------------------
        # Block Coverage
        #---------------------------------------------------------------
        if args.cov:
            logger.info('# Block Coverage')
            objBlocks.Coverage(featAoi)

        #---------------------------------------------------------------
        # Block storage
        #---------------------------------------------------------------
        logger.info('# Block storage')
        objBlocks.WriteBlocks()
        
        
        #---------------------------------------------------------------
        # Block B/H filtering
        #---------------------------------------------------------------
        ####
        #objBlocks=blockFunc.SceneBlocks(lstFeat, args.o, 'dir')
        if args.fBH:
            logger.info('# Block B/H filtering')
            filterFunc.FilterBlocks(objBlocks, 'bh', aoi=featAoi, red=args.fBHred)
            logger.info(objBlocks)
            sys.exit()
            # Update Coverage
            if args.cov:
                logger.info('# Update Coverage')
                objBlocks.Coverage(featAoi)

            # Update block descriptors
            objBlocks.WriteBlocks()

    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
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
        parser.add_argument('-dateAcq', nargs='+', help='Acquisition date yyyy-mm-dd past in the order')
        parser.add_argument('-inst', nargs='+', default=['PS2'], help='Dove generation(s) <PS2|PS2.SD|PSB.SD> (default:PS2)')
        parser.add_argument('-viewAngle', type=float, help='Maximum view angle')
        parser.add_argument('-gsd', type=float, help='Maximum gsd')
        parser.add_argument('-quali', help='Product quality')
        lstKeySearch=('itemType', 'assetType', 'cloudUnder', 'dateAcq', 'inst', 'viewAngle', 'gsd', 'quali')

        argsMain = parser.parse_args()

        Main(argsMain)

        print('\nEND, Continue with scene creation')

