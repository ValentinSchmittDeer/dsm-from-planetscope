#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from subprocess import run as Run
from subprocess import PIPE
from pprint import pprint

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
        
        # Check whether the container exists
        outCmd=os.popen('docker images').readlines()
        imgName=''
        for lineCur in outCmd:
            if 'stereo_docker2' in lineCur.strip().split()[0]:
                imgName=lineCur.strip().split()[0]
        if not imgName: SubLogger('CRITICAL', 'sudo docker pull us.gcr.io/planet-ci-prod/stereo_docker2:latest')  

        # Vagrant or GVM 
        if moduleSpec:
            # mount data directories
            self.rootFolder='/vagrant'

            # mount stereo.default
            #pathModule= sys._getframe().f_code.co_filename
            #pathSteDef=os.path.join(os.path.dirname(pathModule), 'stereo.default')
            # All arguments can be passed in command lines.
            # If you still wnat to use stereo.default file, create it next to ASP.py and add -v path/BlockProc/stereo.default:/app/stereo.default

        # Local system
        else:
            self.rootFolder='/home/valentinschmitt'
        
        self.aspCmd='docker run -it -v {0}:{0} {1}'.format(self.rootFolder, imgName)

    def _ValidArgs(self, subArgs):
        '''
        Check the whether all path in the argument list a absolute. It is 
        mandatory due to root folder link in Docker usage (-v /vagrant:/vagrant)

        subArgs (list): list of all arguments
        out:
            
        '''
        if not subArgs: return 1
        lstStrArgs=[type(arg)==str for arg in subArgs]
        if False in lstStrArgs: 
            pprint(subArgs)
            SubLogger('CRITICAL', 'All arguments must be string type')
        
        lstAbsPath=[arg.startswith(self.rootFolder) for arg in subArgs if '/' in arg]
        if False in lstAbsPath: 
            pprint(subArgs)
            SubLogger('CRITICAL', 'All paths must be absolute')
        return 0
    
    def _RunCmd_debug(self, fun, subArgs, checkCmd=None):
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.aspCmd, fun)
        strCmd+=' '.join(subArgs)
        SubLogger('INFO', strCmd)
        #sys.exit()
        out=Run(strCmd,
                shell=True,
                check=checkCmd is not None,
                )
        
        #if not any([checkCmd in lineCur for lineCur in out.stdout.decode("utf-8").split('\n')]):
        #    print('strCmd:\n', strCmd)
        #    SubLogger('CRITICAL', 'That command returned 0 but the process failed: key={!r}'.format(checkCmd))

        return out.returncode
        
    def _RunCmd(self, fun, subArgs, checkCmd=None):
        '''
        Run the given function with the argumets. The checkCmd argument
        
        '''
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.aspCmd, fun)
        strCmd+=' '.join(subArgs)
        out=Run(strCmd,
                shell=True,
                check=checkCmd is not None,
                stdout=PIPE,
                )
        
        if checkCmd and not any([checkCmd in lineCur for lineCur in out.stdout.decode("utf-8").split('\n')]):
            print('strCmd:\n', strCmd)
            SubLogger('CRITICAL', 'That command returned 0 but the process failed: key={!r}'.format(checkCmd))

        return out.returncode

    def cam_gen(self, subArgs):
        return self._RunCmd('cam_gen', subArgs)

    def convert_pinhole_model(self, subArgs):
        return self._RunCmd_debug('convert_pinhole_model', subArgs)

    def cam2rpc(self, subArgs):
        return self._RunCmd('cam2rpc', subArgs)

    def mapproject(self, subArgs):
        return self._RunCmd('mapproject', subArgs)

    def orbitviz(self, subArgs):
        return self._RunCmd('orbitviz', subArgs)

    def ipfind(self, subArgs):
        return self._RunCmd('ipfind', subArgs)

    def bundle_adjust(self, subArgs, boolConv=True):
        if boolConv:
            checkStr='Termination:                      CONVERGENCE'
        else:
            checkStr='Termination:                   NO_CONVERGENCE'
        return self._RunCmd_debug('bundle_adjust', subArgs, checkCmd=checkStr)  

    def parallel_bundle_adjust(self, subArgs, boolConv=True):
        if boolConv:
            checkStr='Termination:                      CONVERGENCE'
        else:
            checkStr='Termination:                   NO_CONVERGENCE'
        return self._RunCmd('parallel_bundle_adjust', subArgs, checkCmd=checkStr)

    def camera_solve(self, subArgs):
        return self._RunCmd('camera_solve', subArgs)

    def stereo_pprc(self, subArgs):
        return self._RunCmd('stereo_pprc', subArgs)

    def stereo(self, subArgs):
        return self._RunCmd('stereo', subArgs)

    def parallel_stereo(self, subArgs):
        return self._RunCmd_debug('parallel_stereo', subArgs)

    def point2dem(self, subArgs):
        return self._RunCmd('point2dem', subArgs)

    def point2las(self, subArgs):
        return self._RunCmd('point2las', subArgs)




#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
