#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''
# Copyright PythonValentinLibrary

import os, sys
from pprint import pprint
import xml.etree.ElementTree as ET
import json
import numpy as np
from numpy.linalg import matrix_rank, svd, inv
from scipy.linalg import lstsq
from sklearn.preprocessing import PolynomialFeatures
from math import pi

#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['RPCin','AffineTransfo','Geo2Cart_Elli','DisplayMat']

gdinfo='gdalinfo'

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class RPCin:
    """
    Create a RPC python object from metadata files. Currently able to read
    : WorldView xml, tiff tag, RPB file
    
    ## Order :
    # Sklearn poly from triple (x, y, z): REF
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, x, y, z, x2, xy, xz, y2, yz, z2, x3 , x2y, x2z, xy2, xyz, xz2, y3 , y2z, yz2, z3
    # 1, x0, x1, x2, x0^2, x0x1, x0x2, x1^2, x1x2, x2^2, x0^3, x0^2x1, x0^2x2, x0x1^2, x0x1x2, x0x2^2, x1^3, x1^2x2, x1x2^2, x2^3
    # RPC from geo (Long_L, Lat_P, Hei_H):
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, L, P, H, LP, LH, PH, L2, P2, H2, PLH, L3 , LP2, LH2, L2P, P3 , PH2, L2H, P2H, H3
    
    pathCur (string): file path
    
    out:
        self (RPC object): available features printable through str(RPCin) or dir(RPCin)
    """
    
    def __init__(self, pathCur=None):
        if pathCur and not os.path.isfile(pathCur): 
            print(self.__doc__)
            sys.exit()
        self.path=pathCur
        
        if pathCur and pathCur.split('.')[-1] in ['xml', 'XML']:
            self.src=pathCur.split('.')[-1]
            self.Read_Xml()
        elif pathCur and pathCur.split('.')[-1] in ['tif', 'TIF']:
            self.src=pathCur.split('.')[-1]
            self.Read_Tif()
        elif pathCur and pathCur.split('.')[-1] in ['rpb', 'RPB']:
            self.src=pathCur.split('.')[-1]
            self.Read_Rpb()
        elif pathCur and pathCur.split('.')[-1]=='TXT' and 'RPC' in os.path.basename(pathCur) :
            self.src=pathCur.split('.')[-1]
            self.Read_RpcTxt()
        else:
            self.src='Built-in'
    
    def __str__(self):
        strOut=str(self.__repr__())+':\n\t'
        strOut+='(),\n\t'.join([funct for funct in dir(self) if funct[0].isupper()])
        strOut+='\n'
        objDicOut=self.__dict__.copy()
        objDicOut.pop('matRpcCoef', None)
        objDicOut.pop('matInvCoef', None)
        strOut+=json.dumps(objDicOut, indent='\t', separators=(',', ':'))
        if 'matRpcCoef' in dir(self): strOut+='\t"matRpcCoef":\n'+str(self.matRpcCoef)
        if 'matInvCoef' in dir(self): strOut+='\t"matInvCoef":\n'+str(self.matInvCoef)
        return strOut
    
    def Read_Xml(self):
        tree=ET.parse(self.path)
        root=tree.getroot()
        
        imgPartLink='./RPB/IMAGE/'
        self.lineOffset=float(root.find(imgPartLink+'LINEOFFSET').text)
        self.sampOffset=float(root.find(imgPartLink+'SAMPOFFSET').text)
        self.latOffset =float(root.find(imgPartLink+'LATOFFSET').text)
        self.longOffset=float(root.find(imgPartLink+'LONGOFFSET').text)
        self.heiOffset =float(root.find(imgPartLink+'HEIGHTOFFSET').text)
        
        self.lineScale=float( root.find(imgPartLink+'LINESCALE').text)
        self.sampScale=float( root.find(imgPartLink+'SAMPSCALE').text)
        self.latScale =float( root.find(imgPartLink+'LATSCALE').text)
        self.longScale=float( root.find(imgPartLink+'LONGSCALE').text)
        self.heiScale =float( root.find(imgPartLink+'HEIGHTSCALE').text)
        
        idCur=[0, 1, 2, 3, 7 , 4 , 5 , 8 , 6 , 9 , 11 , 14 , 17 , 12 , 10 , 13 , 15 , 18 , 16 , 19]
        
        #test=np.array([[1, 'L', 'P', 'H', 'LP', 'LH', 'PH', 'L2', 'P2', 'H2', 'PLH', 'L3' , 'LP2', 'LH2', 'L2P', 'P3' , 'PH2', 'L2H', 'P2H', 'H3']])
        #print(test[:,idCur])
        
        matRpcCoef=np.zeros([4,20], dtype=float)
        for i,tagCur in enumerate(['SAMPNUMCOEF','SAMPDENCOEF','LINENUMCOEF','LINEDENCOEF']):
            tagLink=imgPartLink+tagCur+'List/'+tagCur
            coefStrList=root.find(tagLink).text.strip().split()
            matRpcCoef[i,:]=[float(num) for num in coefStrList]
        
        self.matRpcCoef=matRpcCoef[:,idCur]
    
    def Read_Tif(self):
        txtGD=os.popen(gdinfo+' -json '+self.path)
        imgInfo=json.load(txtGD)
        
        if not 'RPC' in imgInfo['metadata'].keys(): return 1
        rpcPart=imgInfo['metadata']['RPC']
        
        self.lineOffset=float(rpcPart['LINE_OFF'])
        self.sampOffset=float(rpcPart['SAMP_OFF'])
        self.latOffset =float(rpcPart['LAT_OFF'])
        self.longOffset=float(rpcPart['LONG_OFF'])
        self.heiOffset =float(rpcPart['HEIGHT_OFF'])
        
        self.lineScale=float( rpcPart['LINE_SCALE'])
        self.sampScale=float( rpcPart['SAMP_SCALE'])
        self.latScale =float( rpcPart['LAT_SCALE'])
        self.longScale=float( rpcPart['LONG_SCALE'])
        self.heiScale =float( rpcPart['HEIGHT_SCALE'])
        
        idCur=[0, 1, 2, 3, 7 , 4 , 5 , 8 , 6 , 9 , 11 , 14 , 17 , 12 , 10 , 13 , 15 , 18 , 16 , 19]
        
        #test=np.array([[1, 'L', 'P', 'H', 'LP', 'LH', 'PH', 'L2', 'P2', 'H2', 'PLH', 'L3' , 'LP2', 'LH2', 'L2P', 'P3' , 'PH2', 'L2H', 'P2H', 'H3']])
        #print(test[:,idCur])
        
        matRpcCoef=np.zeros([4,20], dtype=float)
        for i,tagCur in enumerate(['SAMP_NUM_COEFF','SAMP_DEN_COEFF','LINE_NUM_COEFF','LINE_DEN_COEFF']):
            coefStrList=rpcPart[tagCur].split()
            matRpcCoef[i,:]=[float(num) for num in coefStrList]
        
        self.matRpcCoef=matRpcCoef[:,idCur]
    
    def Read_Rpb(self):
        with open(self.path) as fileIn:
            
            dicIn={}
            endIn=True
            for lineIn in fileIn:
                lineIn=lineIn.strip()
            
                if lineIn.endswith(';'):
                    if not endIn:
                        valIn.append(float(lineIn.strip(');')))
                        dicIn[tagIn]=valIn
                        endIn=True
                        continue
                    
                    if 'GROUP' in lineIn or 'END' in lineIn: continue
                    
                    tagIn,valIn=[word.strip() for word in lineIn.strip(';').split('=')]
                    if '"' in valIn:
                        valIn=valIn.strip('"')
                    else:
                        valIn=float(valIn)
                    dicIn[tagIn]=valIn
                    endIn=True
                    
                else:
                    if 'GROUP' in lineIn or 'END' in lineIn: continue
                    endIn=False
                    if '=' in lineIn:
                        tagIn=lineIn.split('=')[0].strip()
                        valIn=[]
                        continue
                    valIn.append(float(lineIn.strip(',')))
        
        self.lineOffset=float(dicIn['lineOffset'])
        self.sampOffset=float(dicIn['sampOffset'])
        self.latOffset =float(dicIn['latOffset'])
        self.longOffset=float(dicIn['longOffset'])
        self.heiOffset =float(dicIn['heightOffset'])
        
        self.lineScale=float(dicIn['lineScale'])
        self.sampScale=float(dicIn['sampScale'])
        self.latScale =float(dicIn['latScale'])
        self.longScale=float(dicIn['longScale'])
        self.heiScale =float(dicIn['heightScale'])
        
        idCur=[0, 1, 2, 3, 7 , 4 , 5 , 8 , 6 , 9 , 11 , 14 , 17 , 12 , 10 , 13 , 15 , 18 , 16 , 19]
        matRpcCoef=np.block([dicIn['sampNumCoef'],
                          dicIn['sampDenCoef'],
                          dicIn['lineNumCoef'],
                          dicIn['lineDenCoef']])
        
        self.matRpcCoef=matRpcCoef[:,idCur]
    
    def Read_RpcTxt(self):
        
        with open(self.path) as fileIn:
            txtIn=fileIn.readlines()
            
        dicIn=dict([lineCUr.strip().split(':') for lineCUr in txtIn])
        for keyCur in dicIn:
            dicIn[keyCur]=float(dicIn[keyCur])
        
        self.lineOffset=float(dicIn['LINE_OFF'])
        self.sampOffset=float(dicIn['SAMP_OFF'])
        self.latOffset =float(dicIn['LAT_OFF'])
        self.longOffset=float(dicIn['LONG_OFF'])
        self.heiOffset =float(dicIn['HEIGHT_OFF'])
        
        self.lineScale=float(dicIn['LINE_SCALE'])
        self.sampScale=float(dicIn['SAMP_SCALE'])
        self.latScale =float(dicIn['LAT_SCALE'])
        self.longScale=float(dicIn['LONG_SCALE'])
        self.heiScale =float(dicIn['HEIGHT_SCALE'])
        
        idCur=[0, 1, 2, 3, 7 , 4 , 5 , 8 , 6 , 9 , 11 , 14 , 17 , 12 , 10 , 13 , 15 , 18 , 16 , 19]
        matRpcCoef=np.zeros([4,20], dtype=float)
        for i,keyCode in enumerate(['SAMP_NUM_COEFF','SAMP_DEN_COEFF','LINE_NUM_COEFF','LINE_DEN_COEFF']):
            for j in range(20):
                keyCur=keyCode+'_'+str(j+1)
                matRpcCoef[i,j]=dicIn[keyCur]
        
        self.matRpcCoef=matRpcCoef[:,idCur]
    
    def Offset3D(self):
        '''
        Return an array with offset values of ground coordinates used 
        by coords normalisation.
        
        out:
            offset3D (array: [oL, oP, oH]): Long (L), Lat (P), Height (H)
        '''
        return np.array([self.longOffset, self.latOffset, self.heiOffset])
    
    def Scale3D(self):
        '''
        Return an array with scale values of ground coordinates used 
        by coords normalisation.
        
        out:
            scale3D (array: [sL, sP, sH]): Long (L), Lat (P), Height (H)
        '''
        return np.array([self.longScale, self.latScale, self.heiScale])
    
    def Offset2D(self):
        '''
        Return an array with offset values of image coordinates used 
        by coords normalisation.
        
        out:
            scale3D (array: [oL, oS]): Line (L), Sample(S)
        '''
        return np.array([self.sampOffset, self.lineOffset])
    
    def Scale2D(self):
        '''
        Return an array with scale values of images coordinates used 
        by coords normalisation.
        
        out:
            scale3D (array: sL, sS]): Line (L), Sample(S) 
        '''
        return np.array([self.sampScale, self.lineScale])
    
    def Offset5D(self):
        '''
        Return an array with offset values used by coords normalisation.
        
        out:
            offset5D (array: [oL, oS, oL, oP, oH]): Line (L), Sample(S), 
                Long (L), Lat (P), Height (H) 
        '''
        return np.append(self.Offset2D(), self.Offset3D())
    
    def Scale5D(self):
        '''
        Return an array with scale values used by coords normalisation.
        
        out:
            scale5D (array: [sL, sS, sL, sP, sH]): Line (L), Sample(S), 
                Long (L), Lat (P), Height (H) 
        '''
        return np.append(self.Scale2D(), self.Scale3D())
    
    def Obj2Img(self,ptsIn,orderPoly=3,matAffine=np.identity(3)):
        '''
        Apply the RPC transformation to object coordinates (Object to Image)
        The polynomial length could be selected from its order and 
        an additional affine transformation can be set in.
        
        ptsIn (array nx3: [[Long (L), Lat (P), H], [...]] or [[X, Y, Z], [...]]): 
            point ground coordinates 
        orderPoly (int): polynomial order in use
        matAffine (array 3x3): affine transformation matrix in image plane [default: identity]
        
        out:
            ptsOut (array nx2: [[x, y], [...]]): points image coordinates
                OR ErrorCode (int): {1:'RPC coeff missing', 2:'Input points must be 3D', 3:'Wrong affine transformation', 4:'Wrong polynomial order'}
        '''
        if not 'matRpcCoef' in dir(self):
            return 1
        
        if not ptsIn.shape[1]==3:
            return 2
        
        if not matAffine.shape[0]==matAffine.shape[1]==3:
            return 3
        
        if not 0<orderPoly<4:
            return 4
        
        nbPts=ptsIn.shape[0]
        
        pts3DN=(ptsIn-self.Offset3D())/self.Scale3D()
        poly=PolynomialFeatures(orderPoly)
        matPoly=poly.fit_transform(pts3DN)
        n=len(poly.get_feature_names())
        
        matProd=(self.matRpcCoef[:,:n]@matPoly.T)
        pts2DN= (matProd[[0,2],:]/matProd[[1,3],:]).T
        
        pts2D= pts2DN*self.Scale2D()+self.Offset2D()
        pts2DH= np.append(pts2D.T, np.ones([1,nbPts]), axis=0)
        
        ptsOut= (matAffine@pts2DH)[:-1,:].T
    
        return ptsOut
    
    def Img2Obj_Z(self,ptsIn,zIn,orderPoly=3,matAffine=np.identity(3)):
        '''
        Apply the inverse RPC transformation to image coordinates and 
        known Z (Image to Object).The polynomial length could be selected 
        from its order and an additional affine transformation can be set in.
        
        ptsIn (array nx2: [[x, y], [...]]): point image coordinates
        ptsIn (array nx1: [[Z], [...]]): point ground Z coordinates 
        orderPoly (int): polynomial order in use
        matAffine (array 3x3): affine transformation matrix in image plane [default: identity]
        
        out:
            ptsOut (array: [[x, y], [...]]): points image coordinates
                OR ErrorCode (int): {1:'Inverse RPC coef missing', 2:'Input points must be 2D', 3:'Z input must be 1D', 4:'Different input point number', 5: 'Wrong affine transformation', 6: Wrong polynomial order}
        
        '''
        if not 'matInvCoef' in dir(self):
            return 1
        
        if not ptsIn.shape[1]==2:
            return 2
        
        if not zIn.shape[1]==1:
            return 3
        
        if not ptsIn.shape[0]==zIn.shape[0]: 
            return 4
        
        if not matAffine.shape[0]==matAffine.shape[1]==3:
            return 5
        
        if not 0<orderPoly<4:
            return 6
        
        nbPts=ptsIn.shape[0]
        
        pts2DH=np.append(ptsIn.T, np.ones([1,nbPts]), axis=0)
        pts2DAff=(matAffine@pts2DH).T[:,:2]
        
        pts2DN=(pts2DAff-self.Offset2D())/self.Scale2D()
        zN=(zIn-self.heiOffset)/self.heiScale
        ptsTripleN=np.append(pts2DN,zN, axis=1)
        
        poly=PolynomialFeatures(orderPoly)
        matPoly=poly.fit_transform(ptsTripleN)
        n=len(poly.get_feature_names())
        
        matProd=(self.matInvCoef[:,:n]@matPoly.T)
        latLongN= (matProd[[0,2],:]/matProd[[1,3],:]).T
        
        pts3DN=np.append(latLongN, zN, axis=1)
        pts3D= pts3DN*self.Scale3D()+self.Offset3D()
        
        return pts3D
    
    def InputNorm(self, offset, scale):
        '''
        Create the RPCin object and set in normalisation parameters from 
        external input.
        It can be used for object initialisation, e.g. objRpcPlus=RPCin.InputNorm(RPCin(), (...), (...))
        
        offset (tuple: [oL, oS, oL, oP, oH]): input offset
        scale (tuple: [sL, sS, sL, sP, sH]): input scale
        
        out:
            RPCin (obj):
        '''
        self.lineOffset=offset[0]
        self.sampOffset=offset[1]
        self.latOffset =offset[2]
        self.longOffset=offset[3]
        self.heiOffset =offset[4]
        
        self.lineScale=scale[0]
        self.sampScale=scale[1]
        self.latScale =scale[2]
        self.longScale=scale[3]
        self.heiScale =scale[4]
        
        return self
    
    def ComputRPC(self, pts3D, pts2D, orderPoly=2, solver=2):
        '''
        Compute RPC coefficient by Singular Value Decomposition (SVD).
        The polynomial order can be adjusted but it remains linked to 
        the GCP number. A maximum order stands at 3 due to object design. 
        A 1st order polynomial requires at least 7 GCPs (2: 19 and 3: 39). 
        Normalisation values have to be set in before.
        
        pts3D (array: [[Long (L), Lat (P), H], [...]] or [[X, Y, Z], [...]]): 
            point ground coordinates not normalised
        pts2D (array: [[x, y], [...]]): points image coordinates not normalised
        orderPloy (int:{1|2|3}): polynomial order [default=2]
        
        out:
            code (int): {1:'Normalisation parameters missing', 2:'Different input point number', 3:'Wrong polynomial order', 4:'GCP missing'}
        '''
        
        lstKeys=dir(self)
        for keyCur in ('lineOffset', 'sampOffset', 'latOffset', 'longOffset', 'heiOffset', 'lineScale', 'sampScale', 'latScale', 'longScale', 'heiScale'):
            if not keyCur in lstKeys:
                return 1
        
        if not pts2D.shape[0]==pts3D.shape[0]: 
            return 2
        
        if not type(orderPoly)==int and not 0<orderPoly<4:
            return 3
        
        a=np.array([[1,2,3]])
        b=PolynomialFeatures(orderPoly).fit(a)
        nbFeat=len(b.get_feature_names())*2
        if pts2D.shape[0]<nbFeat:
            if pts2D.shape[0]<nbFeat-1 or not solver==2:
                return 4
        
        pts3DN=(pts3D-self.Offset3D())/self.Scale3D()
        pts2DN=(pts2D-self.Offset2D())/self.Scale2D()
        
        self.matRpcCoef=np.zeros([4,20], dtype=float)
        
        matSolv,self.eigenVal_RpcCoef=self.Solver(pts3DN,pts2DN, orderPoly, solver)
        if type(matSolv)==int: return matSolv
        
        idVal=np.nonzero(matSolv)
        self.matRpcCoef[idVal]=matSolv[idVal]
        
        return 0
    
    def ComputInvRPC(self, pts3D, pts2D, orderPoly=2, solver=2):
        '''
        XXX Compute RPC coefficient by Singular Value Decomposition (SVD).
        The polynomial order can be adjusted but it remains linked to 
        the GCP number. A maximum order stands at 3 due to object design. 
        A 1st order polynomial requires at least 7 GCPs (2: 19 and 3: 39). 
        Normalisation values have to be set in before.
        
        pts3D (array: [[Long (L), Lat (P), H], [...]] or [[X, Y, Z], [...]]): 
            point ground coordinates not normalised
        pts2D (array: [[x, y], [...]]): points image coordinates not normalised
        orderPloy (int:{1|2|3}): polynomial order [default=2]
        
        out:
            code (int): {1:'Normalisation parameters missing', 2:'Different input point number', 3:'Wrong polynomial order', 4:'GCP missing'}

        '''
        lstKeys=dir(self)
        for keyCur in ('lineOffset', 'sampOffset', 'latOffset', 'longOffset', 'heiOffset', 'lineScale', 'sampScale', 'latScale', 'longScale', 'heiScale'):
            if not keyCur in lstKeys:
                return 1
        
        if not pts2D.shape[0]==pts3D.shape[0]: 
            return 2
        
        if not type(orderPoly)==int and not 0<orderPoly<4:
            return 3
        
        a=np.array([[1,2,3]])
        b=PolynomialFeatures(orderPoly).fit(a)
        nbFeat=len(b.get_feature_names())*2
        if pts2D.shape[0]<nbFeat:
            if pts2D.shape[0]<nbFeat-1 or not solver==2:
                return 4
        
        pts3DN=(pts3D-self.Offset3D())/self.Scale3D()
        pts2DN=(pts2D-self.Offset2D())/self.Scale2D()
        nbPts=pts2DN.shape[0]
        
        self.matInvCoef=np.zeros([4,20], dtype=float)
        
        ptsTripleN=np.append(pts2DN,pts3DN[:,[-1]], axis=1)
        
        matSolv,self.eigenVal_InvCoef=self.Solver(ptsTripleN,pts3DN[:,:2], orderPoly, solver)
        
        idVal=np.nonzero(matSolv)
        self.matInvCoef[idVal]=matSolv[idVal]
        
        return 0
    
    def Solver(self,pts3D, pts2D, orderPoly, solver):
        '''
        Pack up function of SVD solver used by RPC computation. Solves 
        Ax=y of Ax=0 depending on chosen method. No check up in !
        
        pts3D (array: [[X1, Y1, Z1], ...]): points of A 
        pts2D (array: [[x1, y1], ...]):  point of y (or A if y=0)
        orderPoly (int): polynomial order
        solver (int): solver method id
        
        out (matOut,lstEigenVal):
            matOut (array(4,n)): coefficient matrix
            lstEigenVal (list): eigenvalue list
        '''
        
        nbPts=pts2D.shape[0]
        
        poly=PolynomialFeatures(orderPoly)
        matPoly=poly.fit_transform(pts3D)
        n=matPoly.shape[1]
        
        matOut=np.zeros([4,n], dtype=float)
        lstEigenVal=[]
        
        # Solver 0 (separated SVD Ax=0)
        if not solver:
            #[[1, X, Y, Z, -x, -xX, -xY, -xZ], ...]
            for i in range(2):
                matA=np.block([[matPoly, -pts2D[:,[i]]*matPoly ]])
                
                matE,matVt=svd(matA)[1:] 
                matV=matVt.T
                
                lstEigenVal.append(matE[-1])
                matOut[2*i:2*i+2,:]= matV[:,-1].reshape([2,n])
        
        # Solver 1 (combined SVD Ax=0)
        elif solver==1:
            #[[1, X, Y, Z, -xX, -xY, -xZ, 0], ...,[0, 1, X, Y, Z, -yX, -yY, -yZ], ...]
            matA=np.block([[matPoly, -pts2D[:,[0]]*matPoly, np.zeros([nbPts,2*n])],
                           [np.zeros([nbPts,2*n]), matPoly, -pts2D[:,[1]]*matPoly]])
            
            matE,matVt=svd(matA)[1:] 
            matV=matVt.T # Caution matlab transposes outcoming V, not python
            
            matColCheck=np.array([int(matV[:,c].all()) for c in range(4*n)])
            if matColCheck.any():
                lstEigenVal.append(matE[-1])
                matOut[:,:n]=matV[:,-1].reshape([4,n])
            else:
                matOut=np.zeros([4,n], dtype=float)
                i=4*n
                while not matOut.all():
                    i-=1
                    if matV[:2*n,i].all(): 
                        matOut[:2,:]=matV[:2*n,i].reshape([2,n])
                        lstEigenVal.append(matE[i])
                    if matV[2*n:,i].all(): 
                        matOut[2:,:]=matV[2*n:,i].reshape([2,n])
                        lstEigenVal.append(matE[i])
        
        # Solver 2 (separated SVD Ax=y, b1 and d1 =1)
        elif solver==2:
            #[[1, X, Y, Z, -xX, -xY, -xZ], ...]
            for i in range(2):
                
                matA=np.block([[matPoly, (-pts2D[:,[i]]*matPoly)[:, 1:] ]])
                matZ=np.append(matA, pts2D[:,[i]], axis=1)
                
                matE,matVt=svd(matZ)[1:] 
                matV=matVt.T
                
                m=2*n-1
                matVxy=matV[:m,m:]
                matVyy=matV[m:,m:]
                
                matX=-matVxy@inv(matVyy)
                matX=np.insert(matX, n, 1)
                
                lstEigenVal.append(matE[-1])
                matOut[2*i:2*i+2,:]= matX.reshape([2,n])
        
        return (matOut,lstEigenVal)

def AffineTransfo(ptsIn, ptsTrue, solver=0):
    '''
    Compute an affine transformation (using homogeneous coordinates) from 
    point pairs. The solver in use is an hard parameter (solv): 
    0=Least square, 1=Singular Value Decomposition, 2=SVD equal to 0 (not written yet)
    
    ptsIn (array: [[x, y], ...]): wrong measurement points
    ptsTrue (array: [[x, y], ...]): true position points
    solver (int): solver selection (default=0)
    
    out:
        matOut (array 3x3): affine transformation matrix
            OR ErrorCode (int): {1:'Different input point number', 2: 'Unknown solver (0|1)'}

    '''
    
    if not ptsIn.shape[0]==ptsTrue.shape[0]: 
            return 1
    nbPts=ptsIn.shape[0]
    
    # Solver 0 (least square)
    if not solver: 
        matA=np.hstack((ptsIn,
                        np.ones([nbPts,1]) ))
        matX=lstsq(matA, ptsTrue)[0]
        matOut=np.vstack((matX.T, [0,0,1]))
    
    # Solver 1 (separated SVD Ax=y)
    elif solver==1: 
        matA=np.hstack((ptsIn,
                    np.ones([nbPts,1]) ))
        m,n=matA.shape
        matZ=np.append(matA, ptsTrue, axis=1)
        
        matE,matVt=svd(matZ)[1:] 
        matV=matVt.T # Caution matlab transposes outcoming V, not python
        
        matVxy=matV[:n,n:]
        matVyy=matV[n:,n:]
        matX=-matVxy@inv(matVyy)
        
        matOut=np.vstack((matX.T, [0]*(n-1)+[1]))
    else:
        return 2
    
    return matOut

def Geo2Cart_Elli(ptGeo,elliAF='WGS84'):
    '''
    Convert geographic coordinates to cartesian coordinates
        
    ptGeo (array: [[Long (L), Lat (P), H], [...]]): geographic coordinates
    ptsIn (tuple: (a, f)): Ellipsoid name <'Bessel 1841'|'WGS84'|'PZ-90.11'> 
        [default='WGS84']
    
    out:
        ptsOut (array: [[X, Y, Z], [...]]): cartesiane coordinates
    
    '''
    
    # Elli: a, f
    dicElli={'Bessel 1841':(6377397.2, 1/299.15),
             'WGS84':(6378137,1/298.25722),
             'PZ-90.11':(6378136,1/298.25784)
             }
    
    nbPts,ndCoords=ptGeo.shape
    if not ndCoords==3: return None
    radRatio=np.append(np.ones([nbPts,ndCoords-1])*pi/180,np.ones([nbPts,1]),axis=1)
    ptsIn=ptGeo*radRatio
    
    a,f=dicElli[elliAF]
    
    e2=2*f-f**2
    n=a/(1-e2*np.sin(ptsIn[:,1])**2)**0.5
    nh=(n+ptsIn[:,2])[np.newaxis,:]
    
    matNH=np.vstack((n+ptsIn[:,2],n+ptsIn[:,2],(1-e2)*n+ptsIn[:,2]))
    matTriP=np.vstack((np.cos(ptsIn[:,1]),np.cos(ptsIn[:,1]),np.sin(ptsIn[:,1])))
    matTriL=np.vstack((np.cos(ptsIn[:,0]),np.sin(ptsIn[:,0]),np.ones([1,nbPts])))
    
    ptsOut=matNH*matTriP*matTriL
    
    return n
    return ptsOut.T

def DisplayMat(mat):
    from PIL import Image
    print('Matrix (%ix%i, rk=%i):'% (mat.shape[0],mat.shape[1],matrix_rank(mat)))
    print(np.abs(mat).astype(bool).astype(int))
    matDisp=(mat==0).astype(int)*255
    print('Image: White=0; Black=full (±)')
    imgMat=Image.fromarray(matDisp.astype(float))
    imgMat.show()
    sys.exit()

