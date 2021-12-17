#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
from glob import glob
import numpy as np
from numpy.linalg import norm

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
k1Rem_pxl = -3.94502713e-10
k1Add_pxl = 4.00255009e-10
k1Add_N = 4.00255009e-10*699**2/5.5e-3**2

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def AddDisto(ptsU, k1, k2, p1, p2, PP=np.array([18.15, 12.1]), f=699):
    ptsOff=ptsU-PP/5.5e-3
    ptsN=ptsOff/f*5.5e-3
    r2N=np.square(norm(ptsN, axis=1))[:,np.newaxis]
    dRad=r2N*(k1+k2*r2N)
    sumP1yP2x=np.sum(np.array([p2, p1])*ptsN*2, axis=1)
    dTang=np.array([p2, p1])*r2N/ptsN+sumP1yP2x[:, np.newaxis]

    return ptsU+ptsOff*(dRad+dTang)

def AddConfig(ptsU, k1, PP=None):
    
    if not PP is None:
        ptsOff=ptsU-PP/5.5e-3
    r2Off=np.square(norm(ptsOff, axis=1))[:,np.newaxis]

    return ptsU+ptsOff*k1*r2Off

def SatPlot(PP1, PP2, PP3, i, c):
    txtoff=5
    if c=='b':
        col=(mcolors.CSS4_COLORS['deepskyblue'], mcolors.CSS4_COLORS['royalblue'])
    elif c=='r':
        col=(mcolors.CSS4_COLORS['lightcoral'], mcolors.CSS4_COLORS['firebrick'])
    elif c=='g':
        col=(mcolors.CSS4_COLORS['limegreen'], mcolors.CSS4_COLORS['darkgreen'])

    if not i:
        nameCur='Sat %s, Planet disto'% Sat
    else:
        nameCur=''

    rD=norm(AddConfig(pts_pxl_u, k1Add_pxl, PP=PP1)-centre, axis=1)
    graph.plot(rU, rD-rU, '--', color=col[0], label=nameCur)
    graph.text(rU[0]+txtoff, rD[0]-rU[0], txt, color=col[0])
    txtoff+=5

    if not i:
        nameCur='Sat %s, Refined disto'% Sat #from Tsai PP 
    else:
        nameCur=''
    
    rD=norm(AddConfig(pts_pxl_u, k1Add_pxl, PP=PP2)-centre, axis=1)
    graph.plot(rU, rD-rU, '-', color=col[1], label=nameCur)
    graph.text(rU[0]+txtoff, rD[0]-rU[0], txt, color=col[1])
    txtoff+=5

    if not i:
        nameCur='Sat %s, Refined disto'% Sat #from centre
    else:
        nameCur=''
    
    rD=norm(AddConfig(pts_pxl_u, k1Add_pxl, PP=PP3)-centre, axis=1)
    #graph.plot(rU, rD-rU, '-', color=col[1], label=nameCur)
    #graph.text(rU[0]+txtoff, rD[0]-rU[0], txt, color=col[1])
    txtoff+=5
    
    
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
        #parser.add_argument('-dir', nargs='+')


        #args = parser.parse_args()
        fig, graph = plt.subplots()
        

        lstBounds=( (0, 3300, 0, 2200, 'TL'),
                    (0, 3300, 4400, 2200, 'BL'),
                    (6600, 3300, 0, 2200, 'TR'),
                    (6600, 3300, 4400, 2200, 'BR'))
        # 1048: -22
        # 0f15: -8
        # 1003: -8
        Sat='1003'
        offset=np.array([0, -8])

        for i, tupCur in enumerate(lstBounds):
            print('-------------')
            xMin, xMax, yMin, yMax, txt=tupCur
            pts_pxl_u=np.vstack((np.linspace(xMin, xMax, num=50)-offset[0],
                                 np.linspace(yMin, yMax, num=50)-offset[1])).T
            centre=np.array([3300.0, 2200.0])-offset
            rU=norm(pts_pxl_u-centre, axis=1)

            if not i: 
                rD=norm(AddDisto(pts_pxl_u, k1Add_N, 0, 0, 0)-centre, axis=1)
                graph.plot(rU, rD-rU, 'k-.', label='Reference')

            #---------------------------------------------------------------
            # Basics
            #---------------------------------------------------------------
            
            
            # PP config 1048
            if '1048' in Sat: SatPlot(np.array([18.20167646, 12.26080339]),
                                    np.array([18.200815257490785, 12.466116650818485]),
                                    np.array([18.164650863728347, 12.289035064263382]),
                                    i,
                                    'b')
            
            # PP config 0f15
            if '0f15' in Sat: SatPlot(np.array([18.257318475, 11.955084405]),
                                    np.array([18.256454639818841, 12.155278249112426]),
                                    np.array([18.164650863728347, 12.368027943464341]),
                                    i,
                                    'r')

            # PP config 1003
            if '1003' in Sat: SatPlot(np.array([18.31432559, 11.99389972]),
                                    np.array([18.313459057557928, 12.194743545899009]),
                                    np.array([18.164650863728347, 12.368027943464341]),
                                    i,
                                    'g')
            

        graph.set_title('Distortion adjustment along 4 diagonals')
        graph.set_xlabel('Radius [pxl]')
        graph.set_ylabel('Distortion [pxl]')
        plt.xlim([3850, 3990])
        plt.ylim([23, 26])

        graph.legend()   
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
