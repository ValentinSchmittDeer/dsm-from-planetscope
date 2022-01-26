#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, argparse, time
from pprint import pprint
import numpy as np
from numpy. linalg import inv
from math import pi

# dsm_from_planetscope libraries
from OutLib.LoggerFunc import *
from VarCur import *
from BlockProc import DockerLibs, ASfMFunc, GeomFunc, MSSFunc
from PCT import pipelDFunc

#from BlockProc import MSSFunc, ASP
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
def f(x):
    return x*x

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
        parser.add_argument('img1', help='image 1')
        parser.add_argument('rpc1', help='rpc 1')
        parser.add_argument('img2', help='image 2')
        parser.add_argument('rpc2', help='rpc 2')

        parser.add_argument('-o', required=True, help='output folder')

        args = parser.parse_args()
        logger.info("Arguments: " + str(vars(args)))

        asp=DockerLibs.AspPython()
        pathGeoid='/vagrant/Data/04_Stuttgart/Geoid_fromDiff.tif'

        #---------------------------------------------------------------
        # Copy
        #---------------------------------------------------------------
        lstImgIn=(args.img1, args.img2)
        lstRpcIn=(args.rpc1, args.rpc2)
        lstImg=[os.path.join(args.o, os.path.basename(pathCur)) for pathCur in lstImgIn]
        lstRpc=[os.path.join(args.o, os.path.basename(pathCur)) for pathCur in lstRpcIn]
        for i in range(2):
            #os.system('cp %s %s'% (lstImgIn[i], lstImg[i]))
            ASfMFunc.SingleBandImg(lstImgIn[i], lstImg[i], imgType='green')
            os.system('cp %s %s'% (lstRpcIn[i], lstRpc[i]))

        #---------------------------------------------------------------
        # Case 1
        #---------------------------------------------------------------
        if 0:
            logger.info("Case 1")
            lstCam=[lstImg[i].replace('.tif', '.tsai') for i in range(2)]
            for i in range(2):
                idImg=os.path.basename(lstImg[i])[:-19]
                
                ASfMFunc.SRS_OCV(idImg, lstRpc[i], None, lstCam[i])

            lstPath=[(lstImg[i], lstCam[i]) for i in range(2)]
            prefOut=os.path.join(args.o, 'Case1', 'C1')
            asp.stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=True))
            asp.point2dem(MSSFunc.SubArgs_P2D(prefOut+'-PC.tif', 32632))

            #---------------------------------------------------------------
            # Case 2
            #---------------------------------------------------------------
            logger.info("Case 2")
            lstCam=[lstImg[i].replace('.tif', '.tsai') for i in range(2)]
            for i in range(2):
                idImg=os.path.basename(lstImg[i])[:-19]
                
                ASfMFunc.SRS_OCV(idImg, lstRpc[i], pathGeoid, lstCam[i])

            lstPath=[(lstImg[i], lstCam[i]) for i in range(2)]
            prefOut=os.path.join(args.o, 'Case2', 'C2')
            asp.stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=True))
            asp.point2dem(MSSFunc.SubArgs_P2D(prefOut+'-PC.tif', 32632))
            sys.exit()
        #---------------------------------------------------------------
        # Case 3
        #---------------------------------------------------------------
        logger.info("Case 3")
        lstCam=[lstImg[i].replace('.tif', '.tsai') for i in range(2)]
        for i in range(2):
            idImg=os.path.basename(lstImg[i])[:-19]
            pathRpcIn=lstRpc[i]
            pathRpcOut=pathRpcIn[:-4]+'_Alti.TXT'
            print()
            rpcIn=GeomFunc.RPCin(pathRpcIn)
            rpcOut=GeomFunc.RPCin.InputNorm(GeomFunc.RPCin(), rpcIn.Offset(), rpcIn.Scale())

            meshRange=np.meshgrid(np.linspace(-1.0, 1.0, num=11), # Long
                                  np.linspace(-1.0, 1.0, num=11), # Lat
                                  np.linspace(-0.2, 0.2, num=11)) # H
            matPtsGeo_Alti=np.vstack((meshRange[0].flatten(), meshRange[1].flatten(), meshRange[2].flatten())).T*rpcIn.Scale(d=3)+rpcIn.Offset(d=3)
            matPtsImg=rpcIn.Obj2Img(matPtsGeo_Alti)
            matPtsGeo_EH=GeomFunc.Alti2ElliH(matPtsGeo_Alti, pathGeoid)
            rpcOut.Comput_RPC(matPtsGeo_EH, matPtsImg)
            print('error', rpcOut.error_RpcCoef)

            os.system('cp %s %s'% (pathRpcIn, pathRpcOut))
            with open(pathRpcIn,'w') as fileOut:
                fileOut.writelines(rpcOut.__write__())
            
            ASfMFunc.SRS_OCV(idImg, pathRpcIn, None, lstCam[i])

        lstPath=[(lstImg[i], lstCam[i]) for i in range(2)]
        prefOut=os.path.join(args.o, 'Case3', 'C3')
        asp.stereo(MSSFunc.SubArgs_Stereo(lstPath, prefOut, epip=True))
        asp.point2dem(MSSFunc.SubArgs_P2D(prefOut+'-PC.tif', 32632))





    #matPtsImg_d=np.vstack((meshRange[0].flatten(), meshRange[1].flatten())).T*objRpcIn.Scale(d=2)+objRpcIn.Offset(d=2)
    #matPtsH=meshRange[2].reshape(-1,1)*objRpcIn.heiScale+objRpcIn.heiOffset
    #matPtsGeo=objRpcIn.Img2Obj_Z(matPtsImg_d,matPtsH)
    #if pathGeoid: matPtsGeo=GeomFunc.Alti2ElliH(matPtsGeo, pathGeoid, eh2a=False)
    #matPtsCart=GeomFunc.Geo2Cart_Elli(matPtsGeo)



    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
