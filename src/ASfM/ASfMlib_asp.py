#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from PVL.PVL_Logger import SetupLogger, SubLogger

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['AspUtility']
SetupLogger(name=__name__)

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class AspUtility():
    '''
    '''
    rootFolder='/vagrant'
    aspCmd='docker run -it -v {0}:{0} us.gcr.io/planet-ci-prod/stereo_docker2 '.format(rootFolder)
    lstAspCmd=('add_spot_rpc','disparitydebug','image_calc','parallel_stereo','aster2asp','export_matches_file_to_vw','image_mosaic','pc_align','build_reconstruction','export_reconstruction_to_vw','ipfind','pc_merge','bundle_adjust','extract_icebridge_ATM_points.py','ipmatch','point2dem','cam2map4stereo.py','gdal_rasterize','lasinfo','point2las''cam2rpc','gdal_translate','lronac2mosaic.py','point2mesh','cam_gen','gdalbuildvrt','lronacjitreg','qi2txt''camera_calibrate','gdaldem','lvis2kml.py','sfs','camera_footprint','gdalinfo','mapproject','sparse_disp''camera_solve','gdaltransform','mer2camera','stereo''colormap','gdalwarp','n_align','stereo_blend''convert','geodiff','nav2cam','stereo_corr','convert_pinhole_model','h5dump','orbitviz','stereo_fltr''correct_icebridge_l3_dem','hiedr2mosaic.py','orbitviz_pinhole','stereo_gui','coverage_fraction','hillshade','ortho2pinhole','stereo_pprc''datum_convert','historical_helper.py','pansharp','stereo_rfne''dem_geoid','hsv_merge','parallel','stereo_tri''dem_mosaic','icebridge_kmz_to_csv.py','parallel_bundle_adjust','undistort_image''dg_mosaic','image2qtree','parallel_sfs','wv_correct')

    def __init__(self):
        #if vágrant ... else:

        # Check Docker image
        outCmd=os.popen('docker images').readlines()
    
        checkDocker=False
        i=0
        while i<len(outCmd) and not checkDocker:
            i+=1
            lineCur=outCmd[i]
            if lineCur.strip().split()[0]=='us.gcr.io/planet-ci-prod/stereo_docker2':
                checkDocker=True
        if not checkDocker: SubLogger(logging.CRITICAL, 'sudo docker pull us.gcr.io/planet-ci-prod/stereo_docker2:latest')  

    def ValidArgs(self, subArgs):
        '''
        Check the whether all path in the argument list a absolute. It is 
        mandatory due to root folder link in Docker usage (-v /vagrant:/vagrant)

        subArgs (list): list of all arguments
        out:
            
        '''
        if not subArgs: return 1
        lstStrArgs=[type(arg)==str for arg in subArgs]
        if False in lstStrArgs: SubLogger(logging.CRITICAL, 'All arguments must be string type')
        
        lstAbsPath=[arg.startswith(self.rootFolder) for arg in subArgs if '/' in arg]
        if False in lstAbsPath: SubLogger(logging.CRITICAL, 'All paths must be absolute')
        return 0

    def cam_gen(self, subArgs):
        fun='cam_gen'
        if self.ValidArgs(subArgs): return 1
        strCmd=fun+' '
        strCmd+=' '.join(subArgs)
        out=os.popen(self.aspCmd+strCmd).readlines()
        pathOut=[arg for arg in subArgs if arg.endswith('tif')][0].replace('.tif', '.'+fun)
        with open(pathOut, 'w') as fileOut:
            fileOut.writelines(out)
        return 0

    def convert_pinhole_model(self, subArgs):
        fun='convert_pinhole_model'
        if self.ValidArgs(subArgs): return 1
        strCmd=fun+' '
        strCmd+=' '.join(subArgs)
        out=os.popen(self.aspCmd+strCmd).readlines()
        pathOut=[arg for arg in subArgs if arg.endswith('tif')][0].replace('.tif', '.'+fun)
        with open(pathOut, 'w') as fileOut:
            fileOut.writelines(out)
        return 0

    def orbitviz(self, subArgs):
        fun='orbitviz'
        if self.ValidArgs(subArgs): return 1
        strCmd=fun+' '
        strCmd+=' '.join(subArgs)
        out=os.popen(self.aspCmd+strCmd).readlines()
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0].replace('.kml', '.'+fun)
        with open(pathOut, 'w') as fileOut:
            fileOut.writelines(out)
        return 0

    def ipfind(self, subArgs):
        fun='ipfind'
        if self.ValidArgs(subArgs): return 1
        strCmd=fun+' '
        strCmd+=' '.join(subArgs)
        out=os.popen(self.aspCmd+strCmd).readlines()
        SubLogger(logging.CRITICAL, 'Adjust log path')
        pathOut=[arg for arg in subArgs if arg.endswith('tif')][0].replace('.tif', '.'+fun)
        with open(pathOut, 'w') as fileOut:
            fileOut.writelines(out)
        return 0


    def bundle_adjust(self, subArgs):
        fun='bundle_adjust'
        if self.ValidArgs(subArgs): return 1
        strCmd=fun+' '
        strCmd+=' '.join(subArgs)
        ####
        print(self.aspCmd+strCmd)
        os.system(self.aspCmd+strCmd)
        return 0
        ####
        out=os.popen(self.aspCmd+strCmd)
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        with open(pathOut, 'w') as fileOut:
            fileOut.writelines(out)
        return 0

    def camera_solve(self, subArgs):
        fun='camera_solve'
        #if self.ValidArgs(subArgs): return 1
        strCmd=fun+' '
        strCmd+=' '.join(subArgs)
        print(strCmd)
        os.system(self.aspCmd+strCmd)
        print('END')
        return 0


#SubLogger(logging.WARNING, 'jojo')

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
