#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob
import numpy as np

# PyValLib packages
from PVL.PVL_Logger import SetupLogger, ProcessStdout
from PVL.PVL_Rpc import *

# dsm_from_planetscope libraries
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
addiPrefix='KPIEO-All'

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

def ObjTsai(pathIn):
    dic={}
    with open(pathIn) as fileIn:
        for line in fileIn:
            if not '=' in  line: continue

            words=[part.strip() for part in line.strip().split('=')]
            dic[words[0]]=[float(part) for part in words[1].split()]
    return dic

def Table_Line(lstWords, iLen=5, wordLen=20):
    strOut= lstWords[0].ljust(iLen)+' | '
    strOut+=' | '.join([word.ljust(wordLen) for word in lstWords[1:]])
    print(strOut)

def Table_3DCentre(obj1, obj2):
    pt1=np.array(obj1['C'])
    pt2=np.array(obj2['C'])
    diff=sum(np.power(pt1-pt2, 2))**0.5
    return str(round(diff, 3))
def Table_Direction(obj1, obj2):
    pt1=np.array(obj1['C'])
    pt2=np.array(obj2['C'])
    diff=(pt1-pt2)>0
    lstStr=[]
    for i in diff:
        if i:
            lstStr.append('+')
        else:
            lstStr.append('-')
    return ','.join(lstStr)
def Table_Angles(obj1, obj2):
    from scipy.spatial.transform import Rotation as R
    pt1=np.array(obj1['R']).reshape(3,3)
    pt2=np.array(obj2['R']).reshape(3,3)
    rot1=R.from_matrix(pt1)
    rot2=R.from_matrix(pt2)
    diff=rot1.as_euler('zxy', degrees=True)-rot2.as_euler('zxy', degrees=True)
    lstStr=tuple(np.round(diff,3).astype(str))
    return ','.join(lstStr)
def Table_2DPP(obj1, obj2):
    pt1=np.array(obj1['cu']+obj1['cv'])
    pt2=np.array(obj2['cu']+obj2['cv'])
    diff=sum(np.power(pt1-pt2, 2))**0.5
    return str(round(diff, 2))
def Table_Focal(obj1, obj2):
    return str(round(obj1['fu'][0]-obj2['fu'][0], 3))

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
        parser.add_argument('-init', required=True, help='path to initial setting (ProcData')
        parser.add_argument('-ba',required=True ,nargs='+' ,help='path to next BA folder in the right order')
        
        #Optional arguments
        parser.add_argument('-noGraph',action='store_false',help='Do not return the graph (intactive graph with matplotlib)')
        parser.add_argument('-noTable',action='store_false',help='Do not return the table')
        parser.add_argument('-longTable',action='store_true',help='Long table version (make use of scipy 1.7)')
        parser.add_argument('-s', type=int, default=100, help='Graph: scale factor')
        parser.add_argument('-ori',action='store_true',help='Graph: orienation arrow')
        parser.add_argument('-e', action='store_false', help='Graph: do not display the Earth')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.init): raise RuntimeError("Initial folder not found")
        if False in [os.path.isdir(pathCur) for pathCur in args.ba]: raise RuntimeError("Some BA folder not found")
        
        if args.init.endswith('/') or True in [pathCur.endswith('/')for pathCur in args.ba]: raise RuntimeError("Please remove the last / from folder path")
        
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        #---------------------------------------------------------------
        # Read initial
        #---------------------------------------------------------------
        logger.info('# Read initial')
        dicTsai={}

        grepTsai=os.path.join(args.init,'*.tsai')
        for pathCur in glob(grepTsai):
            name=os.path.basename(pathCur)
            dicTsai[name]=[ObjTsai(pathCur),]
        

        #---------------------------------------------------------------
        # Read next steps
        #---------------------------------------------------------------
        logger.info('# Read next steps')
        lstBaName=[]

        for pathBA in args.ba:
            # Read camera
            lstBaName.append(os.path.basename(pathBA))
            grepTsai=os.path.join(pathBA,'*.tsai')
            for pathCur in glob(grepTsai):
                name=os.path.basename(pathCur).strip(addiPrefix)
                dicTsai[name].append(ObjTsai(pathCur))

            
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
                        name=os.path.basename(words[0]).strip(addiPrefix)
                        
                        if not checkCamPart:
                            dicTsai[name][-1]['resiKP-%s'% step]=float(words[1])
                            dicTsai[name][-1]['numKP-%s'% step]=float(words[2])
                        else:
                            dicTsai[name][-1]['resiTrans-%s'% step]=float(words[1])
                            dicTsai[name][-1]['resiRot-%s'% step]=float(words[2])





        #---------------------------------------------------------------
        # Summary table
        #---------------------------------------------------------------
        if args.noTable:
            # Difference table
            logger.info('# Summary table (Differences to original state)')
            Table_Line(['ImgID','Key', 'Init']+lstBaName)
            for kind in ('3DCentre', 'Direction', 'Angles', 'Focal', '2DPP'):
                print(kind+':')
                i=-1
                for key in dicTsai:
                    if len(dicTsai[key])==1: continue
                    
                    i+=1
                    lstCur=dicTsai[key]
                    
                    if kind=='3DCentre':
                        lstOut=[Table_3DCentre(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='Direction':
                        if not args.longTable: continue
                        lstOut=[Table_Direction(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='Angles':
                        if not args.longTable: continue
                        lstOut=[Table_Angles(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='Focal':
                        lstOut=[Table_Focal(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='2DPP':
                        lstOut=[Table_2DPP(obj, lstCur[0]) for obj in lstCur]



                    Table_Line([str(i),'Diff '+kind]+lstOut)
            
            # Residual table
            logger.info('# Summary table (Residuals initial=>final)')
            Table_Line(['ImgID','Key', 'Init']+lstBaName)
            
            for kind in ('Tranlation', 'Rotation', 'KeyPoint'):
                print(kind+':')
                if not args.longTable: continue
                i=-1
                for key in dicTsai:
                    if len(dicTsai[key])==1: continue
                    
                    i+=1
                    lstCur=dicTsai[key]
                    
                    if kind=='Tranlation':
                        lstOut=['{0[resiTrans-final]:.3f}'.format(obj) for obj in lstCur[1:]]
                    elif kind=='Rotation':
                        lstOut=['{0[resiRot-final]:.3f}'.format(obj) for obj in lstCur[1:]]
                    elif kind=='KeyPoint':
                        
                        lstOut=['{0[resiKP-initial]:.3f} => {0[resiKP-final]:.3f} ({0[numKP-final]:.0f} : {1:.0f})'.format(obj, obj['numKP-final']-obj['numKP-initial']) for obj in lstCur[1:]]
                    
                    Table_Line([str(i),'Resid '+kind, '/']+lstOut)

        
        #---------------------------------------------------------------
        # Graph
        #---------------------------------------------------------------
        if args.noGraph:
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
                    matR=np.array(lstCur[j]['R']).reshape(3,3)
                    vectR=matR@vect
                    if args.ori: graph.quiver(matSclPts[j,0], matSclPts[j,1], matSclPts[j,2],
                                              vectR[0], vectR[1], vectR[2],
                                              length=50,color='k')
                
                # Camera centre Init
                graph.plot(matPts[0,0], matPts[0,1], matPts[0,2],'r^',label='', markersize=10)
                graph.text(matPts[0,0]+args.s, matPts[0,1]+args.s, matPts[0,2]+args.s,str(i))

                # Camera orientation Init
                matR=np.array(lstCur[0]['R']).reshape(3,3)
                vectR=matR@vect
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
