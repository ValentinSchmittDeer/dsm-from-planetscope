#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
from glob import glob
import numpy as np

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0]).split('.')[0]
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
        parser.add_argument('-dir', nargs='+')


        args = parser.parse_args()

        #---------------------------------------------------------------
        # Read
        #---------------------------------------------------------------
        fig, graph = plt.subplots(len(args.dir))
        
        lstColours=list(mcolors.TABLEAU_COLORS.values())

        for i,dirIn in enumerate(args.dir):
            pathIn=glob(os.path.join(dirIn, '*.cam_gen'))[0]
            lstIn=[]
            with open(pathIn) as fileIn:
                for lineCur in fileIn:
                    if not lineCur.startswith('Corner and error'): continue
                    txtIn=lineCur.strip().split(':')[1].strip('( ')
                    
                    r,c=[float(i) for i in txtIn.split(')')[0].split()]
                    e=float(txtIn.split(')')[1])
                    lstIn.append((r,-c,e))
            
            matIn=np.array(lstIn)
            #print(matIn)
            #print(matIn.shape)
            #---------------------------------------------------------------
            # Plot
            #---------------------------------------------------------------
            graph[i].add_patch(Rectangle([0,0], 6600, -2134, fill=False, color='k'))
            #graph[i].plot(matIn[:,0], matIn[:,1], '.', color=lstColours[i])
            [graph[i].add_patch(plt.Circle((matIn[j,0], matIn[j,1]), matIn[j,2]*10, color='r', fill=True)) for j in range(matIn.shape[0]//2)]
            [graph[i].add_patch(plt.Circle((matIn[j,0], matIn[j,1]), matIn[j,2]*10, color='g', fill=True)) for j in range(matIn.shape[0]//2,matIn.shape[0])]
            
            
            graph[i].axis('equal')
            graph[i].set_title(os.path.basename(dirIn))
        
        plt.show()
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
