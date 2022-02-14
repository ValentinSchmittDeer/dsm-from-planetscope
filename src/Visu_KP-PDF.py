#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
import json
import numpy as np
from numpy.linalg import norm
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from pprint import pprint

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
Print key point dispalcement Power Density Functions (geographic coordinates 
only). It requires "_residuals_no_loss_function_pointmap_point_log.geojson" 
files.
**************************************************************************
> 
**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------


#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------

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
        #Mandatory input
        parser.add_argument('-t',required=True,help='Truth')
        parser.add_argument('-p',required=True, nargs='+',help='Proj')
        
        args = parser.parse_args()
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        logger.info("Arguments: " + str(vars(args)))
        #sys.exit()
        #---------------------------------------------------------------
        # Read
        #---------------------------------------------------------------
        logger.info(os.path.basename(os.path.dirname(args.t)))
        with open(args.t) as fileIn:
            objGeojsonTrue=json.load(fileIn)['Features']
        matTrue=np.array([item['geometry']['coordinates'] for item in objGeojsonTrue])

        for pathCur in args.p:
            logger.info(os.path.basename(os.path.dirname(pathCur)))
            with open(pathCur) as fileIn:
                objGeojsonProj=json.load(fileIn)['Features']
             
            matProj=np.array([item['geometry']['coordinates'] for item in objGeojsonProj])
            
            matPts=np.append(matTrue[:,:,np.newaxis],
                             -matProj[:,:,np.newaxis],
                             axis=2)
            
            if not 'matDiff' in locals():
                matDiff=np.sum(matPts, axis=2)[:,:,np.newaxis]
            else:
                matDiff=np.append(matDiff, np.sum(matPts, axis=2)[:,:,np.newaxis], axis=2)
        
        #---------------------------------------------------------------
        # Stats
        #---------------------------------------------------------------
        print('\n\tLong \tLat \tHeight')
        logger.info('Mean:')
        print(np.mean(matDiff, axis=0).T)
        #logger.info('RMS: '+str(norm(matDiff, axis=0).T/matDiff.shape[0]))
        logger.info('Std: ')
        print(str(np.std(matDiff, axis=0).T))
        
        #---------------------------------------------------------------
        # Stats
        #---------------------------------------------------------------
        fig, graph = plt.subplots(3)
        lstColours=list(mcolors.TABLEAU_COLORS.values())
        barLen=0.05
        for i in range(3): 
            graph[i].plot((0, 0), (0, 0.1), 'k-')
            graph[i].plot((np.amin(matDiff[:, i, :]), np.amax(matDiff[:, i, :])), (0, 0), 'k-')

        #graph.hist(matDiff[:, 0], bins='auto', histtype='step', label='Long')
        #graph.hist(matDiff[:, 1], bins='auto', histtype='step', label='Lat')
        #graph.hist(matDiff[:, 2], bins='auto', histtype='step', label='Hei')
        for i in range(matDiff.shape[2]):
            dirCur=os.path.basename(os.path.dirname(args.p[i]))
            for j, name in ((0, 'Long'), (1, 'Lat'), (2, 'Hei')):
                matHisto, bin_edges=np.histogram(matDiff[:, j, i], bins='auto')
                matHisto_n=matHisto/matDiff.shape[0]
                matHisto_cum=np.cumsum(matHisto_n)
                x68Min=bin_edges[np.where(matHisto_cum<0.16)[0][-1]]
                x68Max=bin_edges[np.where(matHisto_cum>0.84)[0][0]+1]
                barWidth=bin_edges[1]-bin_edges[0]
                graph[j].bar(bin_edges[:-1], matHisto_n, barWidth, align='edge', color=lstColours[i], alpha=0.3, label=dirCur)
                #graph[j].plot((x68Min, x68Min), (0, barLen), '--', color=lstColours[i])
                #graph[j].plot((x68Max, x68Max), (0, barLen), '--', color=lstColours[i])
                ave=np.mean(matDiff, axis=0)[j,i]
                sig=np.std(matDiff, axis=0)[j,i]
                #graph[j].plot((ave-sig, ave-sig), (0, barLen), '--', color=lstColours[i])
                #graph[j].plot((ave+sig, ave+sig), (0, barLen), '--', color=lstColours[i])
                graph[j].plot((ave, ave), (0, barLen), '-.', color=lstColours[i])
                graph[j].set_title(name)

                matStd=matHisto_n[np.where(np.logical_and(ave-sig<bin_edges[:-1], bin_edges[:-1]<ave+sig))[0]]
                #logger.info('%s std [%%]: %.2f'% (name, np.sum(matStd)*100))
                #break

        for i in range(3): graph[i].legend()
        
        
        fig.suptitle('Histogram')
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
