#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob
import numpy as np
from numpy.linalg import norm
from math import acos, pi

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc import GeomFunc

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


def Table_Line(iCur, kind, lstVal, iLen=5, wordLen=20):
    strOut= str(iCur).ljust(iLen)+' | '
    strOut+=kind.ljust(wordLen)+' | '
    strOut+=' | '.join([str(word).ljust(wordLen) for word in lstVal])
    print(strOut)

def Table_Sum(matIn, iLen=5, wordLen=20):
    Table_Line('-'*iLen, '-'*wordLen, ['-'*wordLen]*(matIn.shape[1]))
    ave=np.round(np.average(matIn, axis=0), 3)
    Table_Line('Mean', 'Diff '+kind, ave)
    rms=np.round(np.sqrt(np.average(np.square(matIn), axis=0)), 3)
    Table_Line('RMS', 'Diff '+kind, rms)
    std=np.round(np.std(matIn, axis=0), 3)
    Table_Line('Std', 'Diff '+kind, std)
    maxCur=np.round(np.amax(matIn, axis=0), 3)
    Table_Line('Max', 'Diff '+kind, maxCur)
    minCur=np.round(np.amin(matIn, axis=0), 3)
    Table_Line('Min', 'Diff '+kind, minCur)


def set_axes_equal(ax):
    '''Make axes of 3D plot have equal scale so that spheres appear as spheres,
    cubes as cubes, etc..  This is one possible solution to Matplotlib's
    ax.set_aspect('equal') and ax.axis('equal') not working for 3D.

    Input
      ax: a matplotlib axis, e.g., as output from plt.gca().
    '''

    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    x_middle = np.mean(x_limits)
    y_range = abs(y_limits[1] - y_limits[0])
    y_middle = np.mean(y_limits)
    z_range = abs(z_limits[1] - z_limits[0])
    z_middle = np.mean(z_limits)

    # The plot bounding box is a sphere in the sense of the infinity
    # norm, hence I call half the max range the plot radius.
    plot_radius = 0.5*max([x_range, y_range, z_range])

    ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
    ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
    ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])

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
        #Positional input
        parser.add_argument('-init', required=True, help='path to initial setting (ProcData)')
        parser.add_argument('-ba',required=True ,nargs='+' ,help='path to next BA folder in the right order')
        
        #Optional arguments
        parser.add_argument('-pref', default='',help='Additional prefix')
        parser.add_argument('-graph',action='store_true',help='Return the graph (interactive graph with matplotlib)')
        parser.add_argument('-table',action='store_true',help='Return the table')
        parser.add_argument('-longTable',action='store_true',help='Long table version (make use of scipy 1.7)')
        parser.add_argument('-s', type=int, default=100, help='Graph: scale factor')
        parser.add_argument('-ori',action='store_true',help='Graph: orienation arrow')
        parser.add_argument('-e', action='store_true', help='Graph: display the Earth')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.init): raise RuntimeError("Initial folder not found")
        if False in [os.path.isdir(pathCur) for pathCur in args.ba]: raise RuntimeError("Some BA folder not found")
        
        if args.init.endswith('/') or True in [pathCur.endswith('/')for pathCur in args.ba]: raise RuntimeError("Please remove the last / from folder path")
        
        objTemp=PathCur('', '', '', checkRoutine=False)
        prefix=''.join([os.path.basename(getattr(objTemp,key)) for key in objTemp.__dict__ if key.startswith('pref')])
        prefix+='-'
        prefix+=args.pref

        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        print()

        #---------------------------------------------------------------
        # Read initial step
        #---------------------------------------------------------------
        logger.info('# Read initial step')
        dicTsai={}

        grepTsai=os.path.join(args.init,'*.tsai')
        for pathCur in glob(grepTsai):
            if os.path.basename(pathCur) in dicTsai: continue
            
            grepCur='_'.join(pathCur.split('_')[:-1])+'*.tsai'
            pathIn=sorted(glob(grepCur))[-1]
            name=os.path.basename(pathIn)
            if name in dicTsai: continue

            dicTsai[name]=[GeomFunc.ObjTsai(pathIn),]
        
        #---------------------------------------------------------------
        # Read next steps
        #---------------------------------------------------------------
        logger.info('Prefix: %s'% prefix)
        lstBaName=[]

        for pathBA in args.ba:
            logger.info('# Read %s'% os.path.basename(pathBA))
            # Read camera
            lstBaName.append(os.path.basename(pathBA))
            grepTsai=os.path.join(pathBA,'*.tsai')
            for pathCur in glob(grepTsai):
                name=os.path.basename(pathCur).strip(prefix)
                if not name in dicTsai: raise RuntimeError("Image name not found, add prefix (-pref): %s"% name) 
                dicTsai[name].append(GeomFunc.ObjTsai(pathCur))

            
            # Read residuals
            for step in ('initial', 'final'):
                pathResInit=glob(os.path.join(pathBA,'*%s_residuals_no_loss_function_averages.txt'% step))
                if not pathResInit: raise RuntimeError("%s residuals not found, please check name"% step)
                pathResInit=pathResInit[0]
                with open(pathResInit) as fileIn:
                    checkCamPart=False
                    for lineCur in fileIn:
                        lineClean=lineCur.strip()
                        if lineClean.startswith('Camera'): checkCamPart=True
                        if not lineClean.startswith('/'): continue
                        
                        words=lineClean.split(', ')
                        name=os.path.basename(words[0]).strip(prefix)
                        
                        if not checkCamPart:
                            dicTsai[name][-1]['resiKP-%s'% step]=float(words[1])
                            dicTsai[name][-1]['numKP-%s'% step]=float(words[2])
                        else:
                            dicTsai[name][-1]['resiTrans-%s'% step]=float(words[1])
                            dicTsai[name][-1]['resiRot-%s'% step]=float(words[2])

        if len(dicTsai)==1: logger.warning('Only one scene in the assessment')
        
        #---------------------------------------------------------------
        # Tables
        #---------------------------------------------------------------
        if args.table or args.longTable:
            #---------------------------------------------------------------
            # Difference table
            #---------------------------------------------------------------
            logger.info('# Differences table')
            Table_Line('ImgID','Key', ['Init']+lstBaName)
            for kind in ('3DCentre[m]', 'Angles[°]', 'Focal[mm]', '2DPP[mm]'):
                print('\n'+kind+':')

                mat=np.zeros([len(dicTsai), 1+len(args.ba)])
                for i, sceneId in enumerate(dicTsai):                    
                    lstCur=dicTsai[sceneId]
                    if not len(lstCur)==1+len(args.ba): continue

                    if kind=='3DCentre[m]':
                        mat[i,:]=[np.round(norm(obj['matC']-lstCur[0]['matC']), 3) 
                                        for obj in lstCur]
                    elif kind=='Angles[°]':
                        lstVect=[obj['matR']@np.array([[0],[0],[1]]) for obj in lstCur]
                        mat[i,:]=[round(acos(round(np.vdot(vect,lstVect[0]), 13))*180/pi, 4) for vect in lstVect]
                    elif kind=='Focal[mm]':
                        mat[i,:]=[round(obj['fu'][0]-lstCur[0]['fu'][0], 3) 
                                        for obj in lstCur]
                    elif kind=='2DPP[mm]':
                        mat[i,:]=[np.round(norm(obj['matPP']-lstCur[0]['matPP']), 3)
                                        for obj in lstCur]




                    if args.longTable: Table_Line(i, 'Diff '+kind, list(mat[i,:]))
                
                Table_Sum(mat)
            
            #---------------------------------------------------------------
            # Residual table
            #---------------------------------------------------------------
            logger.info('# Residuals table')
            Table_Line('ImgID', 'Key', ['Init']+lstBaName)
            
            for kind in ('Tranlation[m]', 'Rotation[°]', 'KeyPoints[pxl]'):
                print('\n'+kind+':')

                mat=np.zeros([len(dicTsai), 1+len(args.ba)])
                for i, sceneId in enumerate(dicTsai):
                    lstCur=dicTsai[sceneId]
                    
                    if kind=='Tranlation[m]':
                        mat[i,:]=[0]+[round(obj['resiTrans-final'], 3) for obj in lstCur[1:]]
                    elif kind=='Rotation[°]':
                        mat[i,:]=[0]+[round(obj['resiRot-final'], 3) for obj in lstCur[1:]]
                    elif kind=='KeyPoints[pxl]':
                        mat[i,:]=[0]+[round(obj['resiKP-final'], 1) for obj in lstCur[1:]]
                    
                    if args.longTable: Table_Line(i,'Resid '+kind, list(mat[i,:]))
                
                Table_Sum(mat)
        
        #---------------------------------------------------------------
        # Graph
        #---------------------------------------------------------------
        if args.graph:
            logger.info('# Graph')
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            import matplotlib.colors as mcolors
        
            fig = plt.figure(1,[15,9])
            graph=fig.add_subplot(111, projection='3d')
            
            lstColours=list(mcolors.TABLEAU_COLORS.values())

            i=-1
            for key in dicTsai:
                if len(dicTsai[key])==1: continue

                i+=1
                lstCur=dicTsai[key]

                matPts=np.array([obj['C'] for obj in lstCur])
                matSclPts=np.vstack((matPts[[0],:],
                                    (matPts[1:,:]-matPts[0,:])*args.s+matPts[0,:]
                                    ))

                # Camera journey
                graph.plot(matSclPts[:,0], matSclPts[:,1], matSclPts[:,2],'k--')
                
                vect=np.array([[0],[0],[1]])*args.s
                for j in range(1,matSclPts.shape[0]):
                    if not i:
                        labelStr=lstBaName[j-1]
                    else:
                        labelStr=''
                    # Camera centre BA
                    graph.plot(matSclPts[j,0], matSclPts[j,1], matSclPts[j,2],'o', color=lstColours[j],label=labelStr)
                    # Camera orientation BA 
                    vectR=lstCur[j]['matR']@vect
                    if args.ori: graph.quiver(matSclPts[j,0], matSclPts[j,1], matSclPts[j,2],
                                              vectR[0], vectR[1], vectR[2],
                                              length=50,color='k')
                
                # Camera centre Init
                graph.plot(matPts[0,0], matPts[0,1], matPts[0,2],'r^',label='', markersize=10)
                graph.text(matPts[0,0]+args.s, matPts[0,1]+args.s, matPts[0,2]+args.s,str(i))

                # Camera orientation Init
                vectR=lstCur[0]['matR']@vect
                if args.ori: graph.quiver(matSclPts[0,0], matSclPts[0,1], matSclPts[0,2],
                                          vectR[0], vectR[1], vectR[2],
                                          length=50, color='r')
                
            #Earth shape
            set_axes_equal(graph)

            if args.e:
                rEarth=6.371e6
                u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
                x = np.cos(u)*np.sin(v)*rEarth
                y = np.sin(u)*np.sin(v)*rEarth
                z = np.cos(v)*rEarth
                #graph.plot_surface(x, y, z, color='b')
                graph.plot_wireframe(x, y, z, color="b")


            graph.set_xlabel('X (ECEF)')
            graph.set_ylabel('Y (ECEF)')
            graph.set_zlabel('Z (ECEF)')
            graph.legend()
            
            fig.suptitle('Camera centres (scale %i)'% args.s)
            plt.show()


        
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
