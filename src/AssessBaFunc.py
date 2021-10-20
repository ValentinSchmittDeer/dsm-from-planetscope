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
colLen=(5, 20)
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class ReadBA:
    '''
    Read ASP folder of bundle adjustment. Initialisation function reads
    initial camera and AddBA function include new folders.
    '''
    def __init__(self, pathInit, strTsai, pref):
        self.strTsai=strTsai
        self.prefix=pref
        self.dicTsai={}

        grepTsai=os.path.join(pathInit, strTsai.format('*'))
        for pathCur in glob(grepTsai):
            name=os.path.basename(pathCur).strip(self.prefix)
            if name in self.dicTsai: continue

            self.dicTsai[name]=[GeomFunc.ObjTsai(pathCur),]
    
    def __str__(self,name=''):
        strOut=''
        for sceneKey in self.dicTsai:
            if name and not sceneKey==name: continue
            strOut+='\n%s <%s, %i>:'% (sceneKey, type(self.dicTsai[sceneKey]).__name__, len(self.dicTsai[sceneKey]))
            
            for i in range(len(self.dicTsai[sceneKey])):
                strOut+='\n\t%i <%s, %i>:'% (i, type(self.dicTsai[sceneKey][i]).__name__, len(self.dicTsai[sceneKey][i]))

                for itemKey in self.dicTsai[sceneKey][i]:
                    strOut+='\n\t\t%s: <%s,'% (itemKey, type(self.dicTsai[sceneKey][i][itemKey]).__name__)
                    if not type(self.dicTsai[sceneKey][i][itemKey])==float:
                        strOut+=' %i'% len(self.dicTsai[sceneKey][i][itemKey])
                    strOut+='>,'

        return strOut
    
    def AddCam(self, pathDir):
        # Read camera
        grepTsai=os.path.join(pathDir, self.strTsai.format('*'))
        for pathCur in glob(grepTsai):
            name=os.path.basename(pathCur).strip(self.prefix)
            if not name in self.dicTsai: continue 
            
            self.dicTsai[name].append(GeomFunc.ObjTsai(pathCur))

    def AddBA(self, pathDir): 
        # Read residuals
        for step in ('initial', 'final'):
            pathResInit=glob(os.path.join(pathDir,'*%s_residuals_no_loss_function_averages.txt'% step))
            if not pathResInit: continue

            with open(pathResInit[0]) as fileIn:
                checkCamPart=False
                for lineCur in fileIn:
                    if lineCur.startswith('Camera'): checkCamPart=True
                    if not lineCur.startswith('/'): continue
                    
                    words=lineCur.strip().split(', ')
                    name=os.path.basename(words[0]).strip(self.prefix)
                    
                    if not checkCamPart:
                        self.dicTsai[name][-1]['resiKP-%s'% step]=float(words[1])
                        self.dicTsai[name][-1]['numKP-%s'% step]=float(words[2])
                    else:
                        self.dicTsai[name][-1]['resiTrans-%s'% step]=float(words[1])
                        self.dicTsai[name][-1]['resiRot-%s'% step]=float(words[2])
            
    def Valid(self, checkBA):
        if len(self.dicTsai)==1: logger.warning('Only one scene in the assessment')
        
        msg=''
        lstLength=[len(self.dicTsai[key])-1 for key in self.dicTsai]
        if not all(lstLength): msg='Not enough BA for every images (check and add prefix -pref)'
        
        if not checkBA: return msg
        lstCheck=[]
        for step in ('initial', 'final'):
            lstCheck+=['numKP-%s'% step in self.dicTsai[key][i] for key in self.dicTsai for i in range(1,len(self.dicTsai[key]))]
        if not all(lstCheck): msg='Residuals (initial and/or final) not found'
        return msg

def KP2Matrix(pathDir):
    '''
    Read initial and final point coordinate and store them into a matrix
    '''

    # Long0, Lat0, Height0, Res0, Long1, Lat1, Height1, Res1, GcpBool
    matIn=np.empty([9])

    # Read KP
    for i,step in enumerate(('initial', 'final')):
        pathKpCsv=glob(os.path.join(pathDir,'*%s_residuals_no_loss_function_pointmap_point_log.csv'% step))
        if not pathKpCsv: continue

        pathKpCsv=pathKpCsv[0]
        with open(pathKpCsv) as fileIn:
            txtIn=[lineCur for lineCur in fileIn.readlines() if not lineCur.startswith('#')]
        if not i :
            # Long0, Lat0, Height0, Res0, Long1, Lat1, Height1, Res1, GcpBool
            matIn=np.ones([len(txtIn),9])*np.nan

        for j,lineCur in enumerate(txtIn):
            if lineCur.startswith('#'): continue
            
            words=lineCur.strip().split(', ')

            matIn[j,i*4:i*4+4]=[float(k) for k in words[:4]]
            if i and words[-1].endswith('GCP'):
                matIn[j,-1]=1
            else:
                matIn[j,-1]=0

    # Long0, Lat0, Height0, Res0, DLong, DLat1, DHeight, DRes, GcpBool
    #matOut=np.hstack((matIn[:,:4],matIn[:,4:8]-matIn[:,0:4], matIn[:, [-1]]))

    return matIn

def TableDiff(dicTsai, nbBa, argsCur):
    '''
    Table function
    '''
    shapeCur=(len(dicTsai), 1+nbBa)
    
    # Difference table
    print('='*(colLen[0]+10)+'{:^26}'.format('Differences Table')+'='*(13+colLen[1]*nbBa+3*(nbBa-1)))
    Table_Line('ImgID','Name', ['Init']+lstBaName)
    lstKind=['3DCentre[m]', 'Angles[°]']
    if argsCur.io: lstKind+=['Focal[mm]', '2DPP[mm]']
    for kind in lstKind:
        print(kind+':')

        mat=np.ones(shapeCur)*np.nan
        for i, sceneId in enumerate(sorted(dicTsai)):                    
            lstCur=dicTsai[sceneId]
            if not len(lstCur)==1+nbBa: continue

            if kind=='3DCentre[m]':
                mat[i,:]=[np.round(norm(obj['matC']-lstCur[0]['matC']), 3) 
                                for obj in lstCur]
            elif kind=='Angles[°]':
                lstVect=[obj['matR']@np.array([[0],[0],[1]]) for obj in lstCur]
                lstCos=[round(1-abs(1-(np.vdot(vect,lstVect[0]))), 7) for vect in lstVect]
                mat[i,:]=[round(acos(valCos)*180/pi, 4) for valCos in lstCos]
            elif kind=='Focal[mm]':
                mat[i,:]=[round(obj['fu'][0]-lstCur[0]['fu'][0], 3) 
                                for obj in lstCur]
            elif kind=='2DPP[mm]':
                mat[i,:]=[np.round(norm(obj['matPP']-lstCur[0]['matPP']), 3)
                                for obj in lstCur]

            if argsCur.longTable: Table_Line(i, 'Diff '+kind, list(mat[i,:]))
        
        Table_Sum(mat, 'Diff '+kind)
    print('.'*(colLen[0]+colLen[1]*(2+nbBa)+9+3*(nbBa-1)))

def TableRes(dicTsai, nbBa, argsCur):
    # Residual table
    shapeCur=(len(dicTsai), 1+nbBa)

    print('='*(colLen[0]+10)+'{:^26}'.format('Residuals Table')+'='*(13+colLen[1]*nbBa+3*(nbBa-1)))
    Table_Line('ImgID', 'Name', ['Init']+lstBaName)
    
    for kind in ('Tranlation[m]', 'Rotation[°]', 'KeyPoints[pxl]'):
        print(kind+':')

        mat=np.ones(shapeCur)*np.nan
        for i, sceneId in enumerate(sorted(dicTsai)):
            lstCur=dicTsai[sceneId]
            
            if kind=='Tranlation[m]':
                mat[i,:]=[0]+[round(obj['resiTrans-final'], 3) for obj in lstCur[1:]]
            elif kind=='Rotation[°]':
                mat[i,:]=[0]+[round(obj['resiRot-final'], 3) for obj in lstCur[1:]]
            elif kind=='KeyPoints[pxl]':
                mat[i,:]=[0]+[round(obj['resiKP-final'], 1) for obj in lstCur[1:]]
            
            if argsCur.longTable: Table_Line(i,'Resid '+kind, list(mat[i,:]))
        
        Table_Sum(mat, 'Res '+kind)
    print('='*(colLen[0]+colLen[1]*(2+nbBa)+9+3*(nbBa-1)))

def Table_Line(iCur, kindCur, lstVal, lenCur=colLen):
    strOut= str(iCur).ljust(lenCur[0])+' | '
    strOut+=kindCur.ljust(lenCur[1])+' | '
    strOut+=' | '.join([str(word).ljust(lenCur[1]) for word in lstVal])
    print(strOut)

def Table_Sum(matIn, kindCur, lenCur=colLen):
    Table_Line('-'*lenCur[0], '-'*lenCur[1], ['-'*lenCur[1]]*(matIn.shape[1]))
    ave=np.round(np.nanmean(matIn, axis=0), 3)
    Table_Line('Mean', kindCur, ave)
    rms=np.round(np.sqrt(np.nanmean(np.square(matIn), axis=0)), 3)
    Table_Line('RMS', kindCur, rms)
    std=np.round(np.nanstd(matIn, axis=0), 3)
    Table_Line('Std', kindCur, std)
    maxCur=np.round(np.nanmax(matIn, axis=0), 3)
    Table_Line('Max', kindCur, maxCur)
    minCur=np.round(np.nanmin(matIn, axis=0), 3)
    Table_Line('Min', kindCur, minCur)

def GraphEO(dicTsai, argsCur):
    '''
    3D Graph function with camera centre and orientation.
    '''
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    import matplotlib.colors as mcolors

    fig = plt.figure(1,[15,9])
    graph=fig.add_subplot(111, projection='3d')
    
    lstColours=list(mcolors.TABLEAU_COLORS.values())

    i=-1
    for key in dicTsai:
        ###
        argsCur.s=1
        ###
        if len(dicTsai[key])==1: continue

        i+=1
        lstCur=dicTsai[key]

        matPts=np.array([obj['C'] for obj in lstCur])
        matSclPts=np.vstack((matPts[[0],:],
                            (matPts[1:,:]-matPts[0,:])*argsCur.s+matPts[0,:]
                            ))

#sat:lng_deg       sat:lat_deg     sat:alt_km       ecefX_m           ecefY_m                ecefZ_m             
#-115.716020192 35.2848819683 492.364006937               
        
        ############
        ptSat=np.array([-2436039.819383114, -5058097.105275761, 3948121.8757154937])
        graph.plot(ptSat[0], ptSat[1], ptSat[2] ,'g^',label='Sat', markersize=10)
        vect=np.array([[0],[0],[100]])*argsCur.s
        
        graph.plot((ptSat[0],matSclPts[1,0]),
                    (ptSat[1],matSclPts[1,1]), 
                    (ptSat[2],matSclPts[1,2]),
                    'g--',label='', markersize=10)
        print(norm(ptSat-matSclPts[1,:]))
        ##############

        # Camera centre Init
        graph.plot(matPts[0,0], matPts[0,1], matPts[0,2],'r^',label='', markersize=10)
        graph.text(matPts[0,0]+args.s, matPts[0,1]+args.s, matPts[0,2]+args.s,str(i))

        # Camera orientation Init
        #vect=np.array([[0],[0],[10]])*argsCur.s
        vectR=lstCur[0]['matR']@vect
        if argsCur.ori: graph.quiver(matSclPts[0,0], matSclPts[0,1], matSclPts[0,2],
                                  vectR[0], vectR[1], vectR[2],
                                  length=50, color='r')

        # Camera journey
        graph.plot(matSclPts[:,0], matSclPts[:,1], matSclPts[:,2],'k--')
        
        
        for j in range(1,matSclPts.shape[0]):
            if not i:
                labelStr=lstBaName[j-1]
            else:
                labelStr=''
            # Camera centre BA
            graph.plot(matSclPts[j,0], matSclPts[j,1], matSclPts[j,2],'o', color=lstColours[j],label=labelStr)
            # Camera orientation BA 
            vectR=lstCur[j]['matR']@vect
            if argsCur.ori: graph.quiver(matSclPts[j,0], matSclPts[j,1], matSclPts[j,2],
                                      vectR[0], vectR[1], vectR[2],
                                      length=50,color='k')
        
    #Earth shape
    set_axes_equal(graph)

    if argsCur.e:
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
    
    fig.suptitle('Camera centres (scale %i)'% argsCur.s)
    plt.show()

def GraphKP(matIn, argsCur):
    '''
    Graph function with KP
    '''
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    nbBA=matIn.shape[0]
    fig, graph = plt.subplots()
    lstColours=list(mcolors.TABLEAU_COLORS.values())

    for i in range(nbBA):
        graph.quiver(matIn[i,:,0], matIn[i,:,1], # matSclPts[j,2],
                    matIn[i,:,4]-matIn[i,:,0], matIn[i,:,5]-matIn[i,:,1], #vectR[2],
                    color=lstColours[i],
                    label=lstBaName[i])
        
    graph.set_xlabel('Long')
    graph.set_ylabel('Lat')
    graph.legend()
    graph.axis('equal')
    fig.suptitle('Key point displacement')
    plt.show()

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
        parser.add_argument('-ba',nargs='+', default=[] ,help='path to next BA folder in the right order')
        parser.add_argument('-cam',nargs='+', default=[] ,help='path to next camera folder in the right order')

        #Optional arguments
        parser.add_argument('-pref', default='',help='Additional prefix')
        parser.add_argument('-table',action='store_true',help='Return the table')
        parser.add_argument('-longTable',action='store_true',help='Long table version')
        parser.add_argument('-io', action='store_true', help='Tabe: print intrinsic parameter difference')

        parser.add_argument('-graphEO',action='store_true',help='Return the graph (interactive graph with matplotlib)')
        parser.add_argument('-s', type=int, default=100, help='Graph: scale factor')
        parser.add_argument('-ori',action='store_true',help='Graph: orienation arrow')
        parser.add_argument('-e', action='store_true', help='Graph: display the Earth')

        parser.add_argument('-graphKP',action='store_true',help='Return the KP sketch and stats (interactive graph with matplotlib)')

        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        if not os.path.isdir(args.init): raise RuntimeError("Initial folder not found")
        
        if args.ba:
            if False in [os.path.isdir(pathCur) for pathCur in args.ba]: raise RuntimeError("Some BA folder not found")
        elif args.cam:
            if False in [os.path.isdir(pathCur) for pathCur in args.cam]: raise RuntimeError("Some Cam folder not found")
        else:
            raise RuntimeError("Either -ba or -cam argument is required")
        if args.init.endswith('/') or True in [pathCur.endswith('/')for pathCur in args.ba+args.cam]: raise RuntimeError("Please remove the last / from folder path")
        
        objTemp=PathCur('', '', '', checkRoutine=False)
        prefix=''.join([os.path.basename(getattr(objTemp,key)) for key in objTemp.__dict__ if key.startswith('pref')])
        prefix+='-.tsai'
        prefix+=args.pref

        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        print()


        #---------------------------------------------------------------
        # Read BA
        #---------------------------------------------------------------
        if args.table or args.longTable or args.graphEO:
            logger.info('# Read BA')
            logger.info('Prefix: %s'% prefix)

            objBa=ReadBA(args.init, objTemp.nTsai[0], prefix)
            
            lstBaName=[]
            for pathBA in args.ba+args.cam:
                logger.info(os.path.basename(pathBA))
                lstBaName.append(os.path.basename(pathBA))
                objBa.AddCam(pathBA)

                if pathBA in args.ba: objBa.AddBA(pathBA)

            if objBa.Valid(len(args.ba)): 
                print(objBa)
                raise RuntimeError(objBa.Valid(len(args.ba)))
        #---------------------------------------------------------------
        # Read KP
        #---------------------------------------------------------------
        if args.graphKP:
            logger.info('# Read KP')

            # Long0, Lat0, Height0, Res0, DLong, DLat1, DHeight, DRes, GcpBool
            lstKpGeo=[]
            lstBaName=[]
            for pathBA in args.ba:
                logger.info(os.path.basename(pathBA))
                lstBaName.append(os.path.basename(pathBA))
                lstKpGeo.append(KP2Matrix(pathBA))

            #(BA, pt, component)
            #   Long0, Lat0, Height0, Res0, Long1, Lat1, Height1, Res1, GcpBool
            matKpGeo=np.array(lstKpGeo)
            #   X0, Y0, Z0, X1, Y1, Z1, GcpBool
            matKpCart=np.array([np.hstack((
                                            GeomFunc.Geo2Cart_Elli(mat[:,0:3]),
                                            GeomFunc.Geo2Cart_Elli(mat[:,4:7]),
                                            mat[:,[-1]]
                                        )) 
                                for mat in lstKpGeo])
            
        #---------------------------------------------------------------
        # Tables
        #---------------------------------------------------------------
        if args.table or args.longTable:
            if args.longTable:
                logger.info('# Longue Table:')
            else:
                logger.info('# Summary Table:')
            TableDiff(objBa.dicTsai, len(args.ba+args.cam), args)
            if args.ba:
                TableRes(objBa.dicTsai, len(args.ba+args.cam), args)
        
        #---------------------------------------------------------------
        # Graph
        #---------------------------------------------------------------
        if args.graphEO:
            logger.info('# Camera Position Graph')
            GraphEO(objBa.dicTsai, args)

        #---------------------------------------------------------------
        # Key Point Sketch
        #---------------------------------------------------------------
        if args.graphKP:
            logger.info('# Key Point Displacement')
            print('='*(colLen[0]+10)+'{:^26}'.format('Statistics')+'='*(13+colLen[1]*(len(lstBaName)-1)+3*(len(lstBaName)-2)))
            Table_Line('ImgID', 'Key', lstBaName)
            print('3D Adjustment:')
            Table_Sum(norm(matKpCart[:,:,0:3]-matKpCart[:,:,3:6], axis=2).T, 'Diff 3D coords')
            print('Height Adjustment:')
            Table_Sum((matKpGeo[:,:,2]-matKpGeo[:,:,6]).T, 'Diff Height')
            print('Initial Residuals:')
            Table_Sum(matKpGeo[:,:,3].T, 'Init res')
            print('Final Residuals:')
            Table_Sum(matKpGeo[:,:,7].T, 'Final res')

            logger.info('# Key Point Graph')
            GraphKP(matKpGeo, args)
        
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
