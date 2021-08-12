#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from subprocess import run as Run
from subprocess import PIPE

from OutLib.LoggerFunc import *
from VarCur import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['AspPython']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class AspPython():
    '''
    ASP command lines in python env. The list of available function is returned by AspPython.__dir__()
    '''
    
    def __init__(self):
        # Automatic environement selection
        from importlib.util import find_spec
        moduleSpec=find_spec('planet_common')
        
        # Vagrant or GVM 
        if moduleSpec:
            # Check whether the container exists
            outCmd=os.popen('docker images').readlines()
            imgName=''
            for lineCur in outCmd:
                if 'stereo_docker2' in lineCur.strip().split()[0]:
                    imgName=lineCur.strip().split()[0]
            if not imgName: SubLogger('CRITICAL', 'sudo docker pull us.gcr.io/planet-ci-prod/stereo_docker2:latest')  

            self.rootFolder='/vagrant'
            self.aspCmd='docker run -it -v {0}:{0} {1}'.format(self.rootFolder, imgName)

        # Local system
        else:
            self.rootFolder='/'
            self.aspCmd=''
        
    def _ValidArgs(self, subArgs):
        '''
        Check the whether all path in the argument list a absolute. It is 
        mandatory due to root folder link in Docker usage (-v /vagrant:/vagrant)

        subArgs (list): list of all arguments
        out:
            
        '''
        if not subArgs: return 1
        lstStrArgs=[type(arg)==str for arg in subArgs]
        if False in lstStrArgs: SubLogger('CRITICAL', 'All arguments must be string type')
        
        lstAbsPath=[arg.startswith(self.rootFolder) for arg in subArgs if '/' in arg]
        if False in lstAbsPath: SubLogger('CRITICAL', 'All paths must be absolute')
        return 0

    def _RunCmd_old(self, fun, subArgs, pathLog):
        '''
        Run the given function with the argumets. Then, it stores the output in a text file at pathLog
        '''
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.aspCmd, fun)
        strCmd+=' '.join(subArgs)
        #SubLogger('INFO', strCmd)
        out=os.popen(strCmd).readlines()
        with open(pathLog, 'w') as fileOut:
            fileOut.writelines(out)
        return 0
    
    def _RunCmd_debug(self, fun, subArgs, pathLog):
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.aspCmd, fun)
        strCmd+=' '.join(subArgs)
        SubLogger('INFO', strCmd)
        #sys.exit()
        os.system(strCmd)
        
    def _RunCmd(self, fun, subArgs, pathLog):
        '''
        Run the given function with the argumets. Then, it stores the output in a text file at pathLog
        '''
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.aspCmd, fun)
        strCmd+=' '.join(subArgs)
        #SubLogger('INFO', strCmd)
        out=Run(strCmd,
                shell=True,
                check=True,
                stdout=PIPE, # set as comment, it display the process stdout 
                )
        if pathLog and out.stdout:
            with open(pathLog, 'w') as fileOut:
                fileOut.write(out.args)
                fileOut.write('\n\n')
                fileOut.write(out.stdout.decode("utf-8"))
        return out.returncode

    def cam_gen(self, subArgs):
        fun='cam_gen'
        if not subArgs: return 1
        pathOut=[arg for arg in subArgs if arg.endswith('tif')][0].replace('.tif', '.'+fun)
        return self._RunCmd(fun, subArgs, pathOut)

    def convert_pinhole_model(self, subArgs):
        fun='convert_pinhole_model'
        if not subArgs: return 1
        pathOut=[arg for arg in subArgs if arg.endswith('tif')][0].replace('.tif', '.'+fun)
        return self._RunCmd(fun, subArgs, pathOut)

    def orbitviz(self, subArgs):
        fun='orbitviz'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0].replace('.kml', '.'+fun)
        return self._RunCmd(fun, subArgs, pathOut)

    def ipfind(self, subArgs):
        fun='ipfind'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='--output-folder'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)

    def bundle_adjust(self, subArgs):
        fun='bundle_adjust'
        if not subArgs: return 1
        #pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        pathOut=None
        return self._RunCmd_debug(fun, subArgs, pathOut)

    def parallel_bundle_adjust(self, subArgs):
        fun='parallel_bundle_adjust'
        if not subArgs: return 1
        #pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        pathOut=None
        return self._RunCmd(fun, subArgs, pathOut)

    def camera_solve(self, subArgs):
        fun='camera_solve'
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)

    def stereo_pprc(self, subArgs):
        fun='stereo_pprc'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)

    def stereo(self, subArgs):
        fun='stereo'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)

    def parallel_stereo(self, subArgs):
        fun='parallel_stereo'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)

    def point2dem(self, subArgs):
        fun='point2dem'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)

    def point2las(self, subArgs):
        fun='point2las'
        if not subArgs: return 1
        pathOut=[subArgs[i+1] for i in range(len(subArgs)) if subArgs[i]=='-o'][0]+'log-long.'+fun
        return self._RunCmd(fun, subArgs, pathOut)




#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
