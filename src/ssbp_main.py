#!/usr/bin/env python
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import json

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, ProcessStdout
#from PVL.PVL_Rpc import *

# dsm_from_planetscope libraries
import lib_auth
from SSBP import *

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0])[:-3]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task

**************************************************************************
> Steps
**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class Obj():
    '''
    Desciption
    
    arg1 (int):
    arg2 (float): [default=0]
    arg3 (sting):
    arg4 tuple=(x, y):
    
    out:
        jojo (int):
    '''
    
    def __init__(self, arg1, arg3, arg4, arg2=0):
        self.arg2=arg2
    
    def __str__(self):
        return string(self.arg2)
    
    def __obj__(self):
        return self.arg2
    
    def Funct1(self,arg5):
        '''Desciption'''

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
        parser.add_argument('-i',required=True,help='Input geometry geojson')
        parser.add_argument('-o',required=True,help='Working directory for outputs')

        # Optional parameters
        parser.add_argument('-itemType',nargs='+',default=['PSScene3Band', 'PSScene4Band'] ,help='Item type from Planet API list (default: \'PSScene3Band\', \'PSScene4Band\')')

        args = parser.parse_args()
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isfile(args.i) or not args.i.endswith('geojson'): raise RuntimeError("Wrong input file")
        if not os.path.isdir(args.o): raise RuntimeError("Wrong working directory")
        
        #---------------------------------------------------------------
        # Setup Auth
        #---------------------------------------------------------------
        logger.info('## Setup Auth')
        session=lib_auth.PlAuth()
        errDic={1:'PL_API_KEY does not exist'}
        if type(session)==int: raise RuntimeError(errDic[session])

        #---------------------------------------------------------------
        # Item searching 
        #---------------------------------------------------------------
        logger.info('## Item searching ')
        
        jsonParam=vars(args).copy()
        del jsonParam['i']
        del jsonParam['o']
        
        with open(args.i) as fileIn:
            geomIn=json.load(fileIn)
        jsonParam['geom']=geomIn

        filterJsonCur=lib_search.MakeFiter(jsonParam)
        errDic={1:'Unknown key', 2:'Only 1 feature is managened in geometry file for the moment'}
        if type(filterJsonCur)==int: raise RuntimeError(errDic[filterJsonCur])
        



        #---------------------------------------------------------------
        # Step
        #---------------------------------------------------------------
        logger.info('## Step')
        
        #---------------------------------------------------------------
        # Step
        #---------------------------------------------------------------
        #logger.info('## Step')
        #logger.info('This is a info')
        #logger.warning('This is a warning')
        #logger.error('This is an error')
        #logger.critical('This is critical')
        
        #imax=30
        #procBar=ProcessStdout(name='Loop i',inputCur=imax)
        #for i in range(imax):
        #    procBar.ViewBar(i)
        #    for i in list(range(20000)):
        #        if not i in list(range(20000)): continue
        #        str(list(range(20000)).index(i))
        
        #lst=['a','b','c','d','e','f','g']
        #procBar=ProcessStdout(name='Loop List',mode='list',inputCur=lst)
        #for i in range(len(lst)):
        #    logger.info(procBar.ViewList(i))
        #    for i in list(range(20000)):
        #        if not i in list(range(20000)): continue
        #        str(list(range(20000)).index(i))
        
        #sys.exit()
        
        #---------------------------------------------------------------
        # Matplotlib Stdout
        #---------------------------------------------------------------
        # Simple figure with subplots
        '''import matplotlib.pyplot as plt
        fig, graph = plt.subplots(2, 2)
        
        graph[0, 0].plot(x,y,'',label='')
        
        graph[0, 0].set_title('subplot')
        graph[0, 0].set_xlabel('X')
        graph[0, 0].set_ylabel('Y')
        graph[0, 0].legend()
        
        fig.suptitle('BigTitle')
        plt.show()
        '''
        
        #Figure with merged subplots
        '''import matplotlib.pyplot as plt
        fig = plt.figure(1,[15,9])
        
        graph = fig.subplot(rci)
        graph.plot(x,y,'',label='')
        
        graph = plt.subplot(r,c,(i1, i2))
        graph.plot(x,y,'',label='')
        
        graph.set_title('subplot')
        graph.set_xlabel('X')
        graph.set_ylabel('Y')
        graph.legend()
        
        fig.suptitle('BigTitle')
        plt.show()'''
        
        #Figure 3D
        '''import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(1,[15,9])
        graph=fig.add_subplot(111, projection='3d')
        graph.plot(x,y,z,'',label='')
        
        graph.set_title('subplot')
        graph.set_xlabel('X')
        graph.set_ylabel('Y')
        graph.legend()
        
        fig.suptitle('BigTitle')
        plt.show()'''
        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
