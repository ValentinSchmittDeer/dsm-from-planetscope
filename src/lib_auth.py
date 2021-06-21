#!/usr/bin/env python
# -*- coding: UTF-8 -*-'''

import os, sys

import requests

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0])[:-3]
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['PlAuth',]
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def PlAuth():
    '''
    Create python web session using the env var $PL_API_KEY.
    The env var can be added in ~/.bashrc: export PL_API_KEY='xxx'

    out:
        session (request obj): active session
        OR
        error (int): {1:'PL_API_KEY does not exist'}
    ''' 
    PLANET_API_KEY = os.getenv('PL_API_KEY')
    if not PLANET_API_KEY: return 1

    session = requests.Session()
    session.auth = (PLANET_API_KEY, '')

    return session
#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
