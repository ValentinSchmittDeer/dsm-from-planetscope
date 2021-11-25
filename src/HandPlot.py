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

def AddConfig(ptsU, k1, dPP=None, PP=None):
    
    if not dPP is None:
        print(np.round(np.array([3300.0, 2200.0])-dPP, 2))
        ptsOff=ptsU-(np.array([3300.0, 2200.0])-dPP)
    elif not PP is None:
        print(np.round(PP/5.5e-3, 2))
        ptsOff=ptsU-PP/5.5e-3
    r2Off=np.square(norm(ptsOff, axis=1))[:,np.newaxis]

    return ptsU+ptsOff*k1*r2Off

def PolarPlot(ptsU, lstPtsD):
    fig, graph = plt.subplots()

    lstColours=list(mcolors.TABLEAU_COLORS.values())
    lstLabel=('Basics', 
            'PP config 1048', 
            'PP adjust 1048',
            #'PP config 0f22', 
            #'PP adjust 0f22',
            #'PP config 0f15',
            #'PP adjust 0f15',
            'PP config 103c',
            'PP adjust 103c',
            )
    rU=norm(ptsU-np.array([3300.0, 2200.0]), axis=1)
    for i in range(1, len(lstPtsD)):
        rD=norm(lstPtsD[i]-np.array([3300.0, 2200.0]), axis=1)
        if 'config' in lstLabel[i]:
            sym='.'
        else:
            sym='x'
        graph.plot(rU, rD-rU, sym, color=lstColours[(i+1)//2], label=lstLabel[i])
    
    rD=norm(lstPtsD[0]-np.array([3300.0, 2200.0]), axis=1)
    graph.plot(rU, rD-rU, 'k+', label=lstLabel[0])
    graph.legend()   
    plt.show()
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

        meshRange=np.meshgrid(np.linspace(0, 6600, num=50), # x
                              np.linspace(0, 4400, num=50)) # y
        pts_pxl_u=np.vstack((meshRange[0].flatten(), meshRange[1].flatten())).T

        #---------------------------------------------------------------
        # Basics
        #---------------------------------------------------------------
        k1Rem_pxl = -3.94502713e-10
        k1Add_pxl = 4.00255009e-10
        k1Add_N = 4.00255009e-10*699**2/5.5e-3**2

        lstPts_d=[]
        # Basics
        lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N, 0, 0, 0))
        # K1 OCV 
        #lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N+0.193, 0, 0, 0))
        # K1 ASP
        #lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N+0.155, 0, 0, 0))
        # K1,P1,P2 OCV CamWei 20
        #lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N+0.253, 0, -3.197e-4, -1.035e-4))
        # PP Adjust
        #lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N, 0, 0, 0, PP=np.array([18.16467731, 12.354787059])))
        #print(np.array([18.16467731, 12.354787059])/5.5e-3)
        # Focal
        #lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N, 0, 0, 0, f=698.9823494966))
        # P1,P2 without K1
        #lstPts_d.append(AddDisto(pts_pxl_u, k1Add_N, 0, -3.197e-4, -1.035e-4))
        print('Ref\n'+str(np.array(['X', 'Y']))+'\n'+str(np.array([3300.0, 2200.0])))
        # PP config 1048
        print('Sat 1048')
        lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, dPP=np.array([-9.39572, -51.23698])))
        # PP adjust 1048
        lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, PP=np.array([18.20009441098933, 12.530117372677196])))
        # PP config 0f22
        #print('Sat 0f22')
        #lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, dPP=np.array([11.77371, -78.89346])))
        # PP adjust 0f22
        #lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, PP=np.array([18.08367266598664, 12.684050052174625])))
        # PP config 0f15
        #print('Sat 0f15')
        #lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, dPP=np.array([-19.51245, 18.34829])))
        # PP adjust 0f15
        #lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, PP=np.array([18.255731584720117, 12.142814090967438])))
        # PP config 103c
        print('Sat 103c')
        lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, np.array([-48.14095, 6.91236])))
        # PP adjust 103c
        lstPts_d.append(AddConfig(pts_pxl_u, k1Add_pxl, np.array([18.413174648888521, 12.206465117990133])))


        PolarPlot(pts_pxl_u, lstPts_d)


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
