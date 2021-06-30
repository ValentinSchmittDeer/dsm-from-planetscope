#!/usr/bin/env python
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import json
from datetime import date, datetime
from shutil import copy2

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, PrintPsItem

# dsm_from_planetscope libraries
import lib_auth
from SSBP import *

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

def main(args):
    try:
        print()
        logger = SetupLogger(name=__title__)
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isfile(args.i) or not args.i.endswith('geojson'): raise RuntimeError("Wrong input file")
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
            logger.warning('Former search mode')
            nameAoiOut=os.path.basename(args.i).split('.')[0]
            nameSearch=os.path.basename(args.iSrch).split('.')[0]
            checkSearch=False
        else:
            logger.warning('New search mode')
            checkSearch=True
            nameSearch=nameOutFull.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
            nameAoiOut=nameAoi.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
                
        if not os.path.isdir(args.o): raise RuntimeError("Wrong working directory")
        
        # Optional search parameters
        if not 0<=args.cloudUnder<=100: raise RuntimeError("-cloudUnder must be [0-100]")
        
        if args.dateAcq:
            if not len(args.dateAcq)==2: raise RuntimeError("-dateAcq must be 2 dates")
            for i in range(2):
                dateStr=args.dateAcq[i]
                dateObj=date.fromisoformat(dateStr)

                if i==1 and not dateObj>args.dateAcq[0]: raise RuntimeError("-dateAcq must be written in correct order")

                args.dateAcq[i]=dateObj
        
        if False in [instCur in lstInst for instCur in args.inst]: raise RuntimeError("-inst must be <PS2|PS2.SD|PSB.SD>")

        if not args.b in lstBMethod: raise RuntimeError("-b must be one of %s"% str(lstBMethod))
        if not args.f in lstBFilter: raise RuntimeError("-f must be one of %s"% str(lstBFilter))
        

        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        print()
        if checkSearch:
            #---------------------------------------------------------------
            # Setup Auth
            #---------------------------------------------------------------
            logger.info('# Setup Auth')
            session=lib_auth.PlAuth()
            errDic={1:'PL_API_KEY does not exist'}
            if type(session)==int: raise RuntimeError(errDic[session])

            #---------------------------------------------------------------
            # Filter creation
            #---------------------------------------------------------------
            logger.info('# Filter creation ')
            
            jsonParam=vars(args).copy()
            for keyCur in list(jsonParam.keys()):
                if not keyCur in lstKeySearch: del jsonParam[keyCur]
            
            jsonParam['geom']=featAoi

            filterJson=SSBPlib_search.MakeFiter(jsonParam,nameSearch)
            
            #---------------------------------------------------------------
            # Fire off request
            #---------------------------------------------------------------
            logger.info('# Fire off request ')
            lstFeat=SSBPlib_search.PostRequest(session, filterJson)

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
                objOut=basicGeojson
                objOut['name']=nameSearch
                objOut['features']=lstFeat.copy()
                fileOut.write(json.dumps(objOut, indent=2))


        
        logger.info(f'{len(lstFeat)} found scenes')
        
        #---------------------------------------------------------------
        # Block creation
        #---------------------------------------------------------------
        logger.info('# Block creation')
        objBlocks=SSBPlib_block.SceneBlocks(lstFeat, args.o, args.b)
        logger.info(objBlocks)
        
        #---------------------------------------------------------------
        # Block filtering
        #---------------------------------------------------------------
        logger.info('# Block filtering')
        objBlocks.FilterBlock(args.f)
        logger.error('read extended MD and stor them in Json file')
        logger.error('compute B/H from sat_az and sat_elev')
        logger.info(objBlocks)
        objBlocks.StereoCoupling()
        objBlocks.Coverage(featAoi)
        

        #---------------------------------------------------------------
        # Block storage
        #---------------------------------------------------------------
        logger.info('# Block storage')
        objBlocks.WriteBlocks()
        #pprint(objBlocks.__dir__())
        
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

        # Block parameters
        parser.add_argument('-b', default='month', help='Block creation mode <month|one> (default: month)')
        parser.add_argument('-f', default='fp', help='Block filtering mode <fp|> (default: fp=footprint)')

        # Optional search parameters
        parser.add_argument('-iSrch', help='Input former search result (json), cancels another search step')
        parser.add_argument('-itemType', nargs='+', default=['PSScene3Band', 'PSScene4Band'], help='Item type from Planet API list <PSScene3Band|PSScene4Band|...> (default: PSScene3Band, PSScene4Band)')
        parser.add_argument('-assetType', nargs='+', default=['basic_analytic', ], help='Asset type from Planet API list <basic_analytic|analytic|...> (default: basic_analytic)')
        parser.add_argument('-cloudUnder', type=int, default=0.1, help='Maximum cloud coverage %% integer')
        parser.add_argument('-dateAcq', nargs='+', help='Acquisition date yyyy-mm-dd past in the order')
        parser.add_argument('-inst', nargs='+', default=['PS2'], help='Dove generation(s) <PS2|PS2.SD|PSB.SD> (default:PS2)')
        parser.add_argument('-viewAngle', type=float, help='Maximum view angle')
        parser.add_argument('-gsd', type=float, help='Maximum gsd')
        parser.add_argument('-quali', help='Product quality')
        lstKeySearch=('itemType', 'assetType', 'cloudUnder', 'dateAcq', 'inst', 'viewAngle', 'gsd', 'quali')

        argsMain = parser.parse_args()

        main(argsMain)

        print('\nEND, Continue with scene creation')

