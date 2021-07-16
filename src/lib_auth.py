#!/usr/bin/env python
# -*- coding: UTF-8 -*-'''

import os, sys
import requests
import logging
from PVL.PVL_Logger import SetupLogger, SubLogger

#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['PlAuth',]
SetupLogger(name=__name__)


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def PlAuth():
    '''
    Create python web session using the env var $PL_API_KEY.
    The env var can be added in ~/.bashrc: export PL_API_KEY='xxx'

    out:
        session (request obj): active session
    ''' 
    PLANET_API_KEY = os.getenv('PL_API_KEY')
    if not PLANET_API_KEY: SubLogger(logging.CRITICAL, '$PL_API_KEY not found in .bashrc')

    session = requests.Session()
    session.auth = (PLANET_API_KEY, '')

    return session
#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
