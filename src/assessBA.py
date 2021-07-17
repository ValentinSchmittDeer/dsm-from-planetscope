#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
from glob import glob
import numpy as np
#from scipy.spatial.transform import Rotation as R

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


def ObjTsai(pathIn):
    dic={}
    with open(pathIn) as fileIn:
        for line in fileIn:
            if not '=' in  line: continue

            words=[part.strip() for part in line.strip().split('=')]
            dic[words[0]]=[float(part) for part in words[1].split()]
    return dic

def Table_Line(lstWords, iLen=5, wordLen=15):
    strOut= lstWords[0].ljust(iLen)+' | '
    strOut+=' | '.join([word.ljust(wordLen) for word in lstWords[1:]])
    print(strOut)

def Table_3DCentre(obj1, obj2):
    pt1=np.array(obj1['C'])
    pt2=np.array(obj2['C'])
    diff=sum(np.power(pt1-pt2, 2))**0.5
    return str(round(diff, 3))
def Table_Omega(obj1, obj2):
    pt1=np.array(obj1['R']).reshape(3,3)
    pt2=np.array(obj2['R']).reshape(3,3)
    rot1=R.from_matrix(pt1)
    rot2=R.from_matrix(pt2)

    print(rot1.as_euler('zxy', degrees=True))
    sys.exit()
    diff=sum(np.power(pt1-pt2, 2))**0.5
    return str(round(diff, 3))
def Table_2DPP(obj1, obj2):
    pt1=np.array(obj1['cu']+obj1['cv'])
    pt2=np.array(obj2['cu']+obj2['cv'])
    diff=sum(np.power(pt1-pt2, 2))**0.5
    return str(round(diff, 2))
def Table_Focal(obj1, obj2):
    return str(round(obj1['fu'][0]-obj2['fu'][0], 3))
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
        parser.add_argument('-noGraph',action='store_false',help='do not return the graph')
        parser.add_argument('-noTable',action='store_false',help='do not return the table')
        
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
            lstBaName.append(os.path.basename(pathBA))
            grepTsai=os.path.join(pathBA,'*.tsai')
            for pathCur in glob(grepTsai):
                name=os.path.basename(pathCur).strip('KPIEO-')
                dicTsai[name].append(ObjTsai(pathCur))

        #---------------------------------------------------------------
        # Summary table
        #---------------------------------------------------------------
        if args.noTable:
            logger.info('# Summary table')
            Table_Line(['ImgID','Key', 'Init']+lstBaName)
            for kind in ('3DCentre', 'Omega', 'Focal', '2DPP'):
                print(kind+':')
                i=-1
                for key in dicTsai:
                    if len(dicTsai[key])==1: continue
                    
                    i+=1
                    lstCur=dicTsai[key]
                    
                    if kind=='3DCentre':
                        lstOut=[Table_3DCentre(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='Omega':
                        pass
                        #lstOut=[Table_Omega(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='Focal':
                        lstOut=[Table_Focal(obj, lstCur[0]) for obj in lstCur]
                    elif kind=='2DPP':
                        lstOut=[Table_2DPP(obj, lstCur[0]) for obj in lstCur]



                    Table_Line([str(i),'Diff '+kind]+lstOut)
        
        #---------------------------------------------------------------
        # Graph
        #---------------------------------------------------------------
        if args.noGraph:
            logger.info('# Graph')
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            
            #fig = plt.figure(1,[15,9])
            #graph=fig.add_subplot(111, projection='3d')
            
            i=-1
            for key in dicTsai:
                if len(dicTsai[key])==1: continue

                i+=1
                lstCur=dicTsai[key]
                
                # Camera journey
                matPts=np.array([obj['C'] for obj in lstCur])
                graph.plot(matPts[:,0], matPts[:,1], matPts[:,2],'k-')

                print(matPts)
                sys.exit()
                # Camera points
                graph.plot(matPts[0,0], matPts[0,1], matPts[0,2],'g^',label='')
                graph.text(matPts[0,0]+1, matPts[0,1]+1, matPts[0,2]+1,str(i))

                if j in range(1,matPts.shape[0]):
                    graph.plot(matPts[0,0], matPts[0,1], matPts[0,2],'bo',label='')
                


            #graph.set_xlabel('X')
            #graph.set_ylabel('Y')
            #graph.set_ylabel('Z')
            #graph.legend()
            #
            #fig.suptitle('Camera centres')
            #plt.show()


        
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
