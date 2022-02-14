#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import logging
from subprocess import run as Run
from subprocess import PIPE, Popen
from pprint import pprint

from OutLib.LoggerFunc import *
from VarCur import *
from PCT.dataFunc import CheckPC

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['AspPython', 'PdalPython', 'GdalPython']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
checkPC=CheckPC()
lstDockerImgs=[lineCur.split()[0] for lineCur in os.popen('docker images').readlines()][1:]
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class AspPython():
    '''
    ASP command lines in python env. 
    The list of available function is returned by AspPython.__dir__()

    ASP is installed as Docker image with the name:
        us.gcr.io/planet-ci-prod/stereo_docker2:latest

    The class initialistion selct the proper environment (local/planet_common through vagrant)
    '''
    nameImage='us.gcr.io/planet-ci-prod/stereo_docker2'

    def __init__(self):
        if not self.nameImage in lstDockerImgs: SubLogger('CRITICAL', 'sudo docker pull %s'% self.nameImage)  

        # Vagrant or GVM 
        if checkPC:
            # mount data directories
            self.rootFolder='/vagrant'

            # mount stereo.default
            #pathModule= sys._getframe().f_code.co_filename
            #pathSteDef=os.path.join(os.path.dirname(pathModule), 'stereo.default')
            # All arguments can be passed in command lines.
            # If you still wnat to use stereo.default file, create it next to ASP.py and add -v path/BlockProc/stereo.default:/app/stereo.default

        # Local system
        else:
            self.rootFolder='/home'
        
        self.cmdDocker='docker run -it -v {0}:{0} {1}:latest'.format(self.rootFolder, self.nameImage)

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
        strCmd='{} {} '.format(self.cmdDocker, fun)
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
        strCmd='{} {} '.format(self.cmdDocker, fun)
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
        return self._RunCmd_debug('stereo', subArgs)

    def parallel_stereo(self, subArgs):
        return self._RunCmd('stereo', subArgs)

    def point2dem(self, subArgs):
        return self._RunCmd_debug('point2dem', subArgs)

    def point2las(self, subArgs):
        return self._RunCmd_debug('point2las', subArgs)

class PdalPython():
    '''
    PDL command lines in python env. 
    The list of available function is returned by PdalPython.__dir__()

    PDAL is installed as Docker image with the name:
        pdal/pdal:latest

    The class initialistion selct the proper environment (local/planet_common through vagrant)
    '''
    nameImage='pdal/pdal'

    def __init__(self):
        if not self.nameImage in lstDockerImgs: SubLogger('CRITICAL', 'sudo docker pull %s'% self.nameImage)  

        # Vagrant or GVM 
        if checkPC:
            # mount data directories
            self.rootFolder='/vagrant'

            # mount stereo.default
            #pathModule= sys._getframe().f_code.co_filename
            #pathSteDef=os.path.join(os.path.dirname(pathModule), 'stereo.default')
            # All arguments can be passed in command lines.
            # If you still wnat to use stereo.default file, create it next to ASP.py and add -v path/BlockProc/stereo.default:/app/stereo.default

        # Local system
        else:
            self.rootFolder='/home'
        
        self.cmdDocker='docker run -it -v {0}:{0} {1}:latest'.format(self.rootFolder, self.nameImage)

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
        
        lstAbsPath=[arg.strip('"').split('=')[-1].startswith(self.rootFolder) for arg in subArgs if '/' in arg]
        if False in lstAbsPath and not 'assign.value' in subArgs[lstAbsPath.index(False)]: 
            pprint(subArgs)
            SubLogger('CRITICAL', 'All paths must be absolute: %s'% str(lstAbsPath))
        return 0
    
    def _RunCmd_debug(self, fun, subArgs, checkCmd=None):
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.cmdDocker, fun)
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
        
    def _RunCmd(self, fun, subArgs, checkCmd=None, checkInfo=False):
        '''
        Run the given function with the argumets. The checkCmd argument
        
        '''
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.cmdDocker, fun)
        strCmd+=' '.join(subArgs)
        out=Run(strCmd,
                shell=True,
                check=checkCmd is not None,
                stdout=PIPE,
                )
        
        if checkCmd and not any([checkCmd in lineCur for lineCur in out.stdout.decode("utf-8").split('\n')]):
            print('strCmd:\n', strCmd)
            SubLogger('CRITICAL', 'That command returned 0 but the process failed: key={!r}'.format(checkCmd))

        if checkInfo and not out.returncode:
            return json.loads(out.stdout.decode("utf-8"))
        else:
            return out.returncode

    def info(self, subArgs):
        return self._RunCmd('pdal info', subArgs, checkInfo=True)

    def merge(self, subArgs):
        return self._RunCmd('pdal merge', subArgs)

    def tile(self, subArgs):
        return self._RunCmd('pdal tile', subArgs)

    def pipeline(self, subArgs):
        return self._RunCmd('pdal pipeline', subArgs)

    def translate(self, subArgs):
        return self._RunCmd('pdal translate', subArgs)

class GdalPython():
    '''
    PDL command lines in python env. 
    The list of available function is returned by PdalPython.__dir__()

    PDAL is installed as Docker image with the name:
        pdal/pdal:latest

    The class initialistion selct the proper environment (local/planet_common through vagrant)
    '''
    nameImage='osgeo/gdal'

    def __init__(self):
        if not self.nameImage in lstDockerImgs: SubLogger('CRITICAL', 'sudo docker pull %s'% self.nameImage)  

        # Vagrant or GVM 
        if checkPC:
            # mount data directories
            self.rootFolder='/vagrant'

            # mount stereo.default
            #pathModule= sys._getframe().f_code.co_filename
            #pathSteDef=os.path.join(os.path.dirname(pathModule), 'stereo.default')
            # All arguments can be passed in command lines.
            # If you still wnat to use stereo.default file, create it next to ASP.py and add -v path/BlockProc/stereo.default:/app/stereo.default

        # Local system
        else:
            self.rootFolder='/home'
        
        self.cmdDocker='docker run -it -v {0}:{0} {1}:latest'.format(self.rootFolder, self.nameImage)

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
        
        lstAbsPath=[arg.strip('"').split('=')[-1].startswith(self.rootFolder) for arg in subArgs if '/' in arg]
        if False in lstAbsPath and not 'calc' in [arg for arg in subArgs if '/' in arg][lstAbsPath.index(False)]: 
            pprint(subArgs)
            SubLogger('CRITICAL', 'All paths must be absolute: %s'% str(lstAbsPath))
        return 0
    
    def _RunCmd_debug(self, fun, subArgs, checkCmd=None):
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.cmdDocker, fun)
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
        
    def _RunCmd(self, fun, subArgs, checkCmd=None, checkInfo=False):
        '''
        Run the given function with the argumets. The checkCmd argument
        
        '''
        if self._ValidArgs(subArgs): return 1
        strCmd='{} {} '.format(self.cmdDocker, fun)
        strCmd+=' '.join(subArgs)
        out=Run(strCmd,
                shell=True,
                check=checkCmd is not None,
                stdout=PIPE,
                )
        
        if checkCmd and not any([checkCmd in lineCur for lineCur in out.stdout.decode("utf-8").split('\n')]):
            print('strCmd:\n', strCmd)
            SubLogger('CRITICAL', 'That command returned 0 but the process failed: key={!r}'.format(checkCmd))

        if checkInfo and not out.returncode:
            return [lineCur.strip() for lineCur in out.stdout.decode("utf-8").split('\n')]
        else:
            return out.returncode

    def gdalinfo(self, subArgs):
        return self._RunCmd('gdalinfo', subArgs, checkInfo=True)

    def gdal_translate(self, subArgs):
        return self._RunCmd('gdal_translate', subArgs)

    def gdal_merge(self, subArgs):
        return self._RunCmd('gdal_merge.py', subArgs)

    def gdal_calc(self, subArgs):
        return self._RunCmd('gdal_calc.py', subArgs)

    def gdal_retile(self, subArgs):
        return self._RunCmd('gdal_retile.py', subArgs)

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
