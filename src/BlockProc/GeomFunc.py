#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
from math import sin, cos, asin, acos, tan, atan2, pi
import json
import xml.etree.ElementTree as ET
import logging
from pprint import pprint
import numpy as np
from numpy.linalg import inv, svd, lstsq, det, norm, matrix_rank
import rasterio
from sklearn.preprocessing import PolynomialFeatures

from importlib.util import find_spec
checkPlanetCommon=find_spec('planet_opencv3') is not None
if checkPlanetCommon:
    from planet_opencv3 import cv2 as cv
else:
    import cv2 as cv



from OutLib.LoggerFunc import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['TSAIin', 'RPCin', 'AffineTransfo', 'Geo2Cart_Elli', 'Cart2Geo_Elli','MaskedImg']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class TSAIin:
    '''
    Create a object from Tsai file. It holds attributs with varribles
    from the the read file and additional attributs computed and updated
    in the class. It does not distinguish tsai versions and camera types.
    An empty object can be created by feeding a dictionary as input
    
    objInput (str|dict): tsai file path | parameters dictionary
    out:
        TSAIin (class): object with attributs
            version (str): fixed file version (4)
            camType (str): fixed camera type (PINHOLE)
            from file:
                fu (float), fv (float), cu (float), cv (float)
                u, v, w_direction (array)
                C (array), R (array), pitch (float)
                distoType (str), k1 (float), k2 (float), k3 (float), p1 (float), p2 (float)
            form class:
                vectF (array): (fu, fv)
                vectPP (array): (cu, cv)
                matR (array): R [3x3]
                vectX0 (array): C [3x1]
                matO (array): (R.T , -R.T*C) [3x4]
                matK (array): (fu/pitch, cu/pitch, fv/pitch, cv/pitch, 1) [3x3]
                matP (array): K*O [3x4]
            functions:
                __str__(): manage string output
                __write__(): writtable list
                _RfromAngles(): update rotation matrix from angles
                UpdateTsai(): update class matrices from file attributs (C, R, ...)
                ApplyDisto(): apply distortion model to list of points
                Obj2Img(): project geographic points to frame
    '''
    version='4'
    camType='PINHOLE'

    def __init__(self, objInput=None):
        '''
        Read tsai file and create file attributes. It also updates class attrbutes.
        '''
        if type(objInput)==str: 
            if not os.path.exists(objInput): SubLogger('CRITICAL', 'Path not found: %s'% objInput)
            with open(objInput) as fileIn:
                for i, lineCur in enumerate(fileIn):
                    if i<2: continue

                    words=[part.strip() for part in lineCur.strip().split('=')]
                    if len(words)>1:
                        if len(words[1].split())==1:
                            setattr(self, words[0], float(words[1]))
                        else:
                            setattr(self, words[0], np.array([float(part) for part in words[1].split()]))
                        
                        if 'direction' in words[0]:
                            setattr(self, words[0], getattr(self, words[0]).astype(int))
                    else:
                        setattr(self, 'distoType', lineCur.strip())

            if not self.fu==self.fv: SubLogger('CRITICAL', 'Rectangular pixels are not managed by the function')
            self.UpdateTsai()
        
        elif type(objInput)==dict:
            for key in objInput:
                setattr(self, key, objInput[key])
            
            # Complete object
            if not 'distoType' in self.__dir__(): setattr(self, 'distoType', 'NULL')
            if not 'u_direction' in self.__dir__(): setattr(self, 'u_direction', np.array([1, 0, 0]))
            if not 'v_direction' in self.__dir__(): setattr(self, 'v_direction', np.array([0, 1, 0]))
            if not 'w_direction' in self.__dir__(): setattr(self, 'w_direction', np.array([0, 0, 1]))

    def __str__(self):
        strOut=str(self.__repr__())+':\n\t'

        # float
        dicFloat=dict([(key, getattr(self,key)) 
                            for key in self.__dict__ 
                                if not type(getattr(self,key))==np.ndarray])
        # array
        dicArray=dict([(key, str(getattr(self, key).shape)+'=> '+str(getattr(self,key).flatten())) 
                            for key in self.__dict__ 
                                if type(getattr(self,key))==np.ndarray])
        
        dicExt=dict([(key, str(getattr(self,key))) 
                        for key in self.__dir__() 
                            if not key in dicFloat and not key in dicArray and not '_' in key])
        
        strOut+=json.dumps(dicExt, indent='\t', separators=(',', ':'))
        strOut+=json.dumps(dicFloat, indent='\t', separators=(',', ':'))
        strOut+=json.dumps(dicArray, indent='\t', separators=(',', ':'))
        return strOut

    def __write__(self):
        '''
        Create writable list of the current object.
        '''
        # Basics
        lstOut=['VERSION_%s\n'% self.version,
                self.camType+'\n',
                ]
        # Pinhole
        lstTag=('fu', 'fv', 'cu', 'cv')
        lstOut+=['%s = %s\n'% (tag, str(getattr(self,tag))) for tag in lstTag]
        lstTag=('u_direction', 'v_direction', 'w_direction', 'C', 'R')
        lstOut+=['%s = %s\n'% (tag, ' '.join(getattr(self,tag).astype(str))) for tag in lstTag]
        lstOut+=['pitch = %f\n'% getattr(self,'pitch'),
                 self.distoType+'\n']
        # Distortion
        if self.distoType=='NULL':
            return lstOut
        elif self.distoType=='TSAI':
            lstTag=('k1', 'k2', 'p1', 'p2')
        elif self.distoType=='Photometrix':
            lstTag=('xp', 'yp', 'k1', 'k2', 'k3', 'p1', 'p2', 'b1', 'b2')
        else:
            SubLogger('CRITICAL', 'Distortion model not managed yet for ouput')
        
        if not all([tag in self.__dir__() for tag in lstTag]): SubLogger('CRITICAL', 'Distortion model incomplet: %s'% self.distoType)
        lstOut+=['%s = %s\n'% (tag, str(getattr(self,tag))) for tag in lstTag]

        return lstOut
        
    def _RfromAngles(self, lstAngle):
        '''
        Update the rotation matrix from a list of angles. It uses
        a rotation matix convention: intrinsic R(k).R(p).R(o).

        lstAngle (lst or array):
        out:
            0 (int)
        '''
        if not len(lstAngle): SubLogger('CRITICAL', 'Angle list must contain 3 float values')

        omega, phi, kappa= lstAngle
        setattr(self, 'R', 
                np.array([[ cos(phi)*cos(kappa),  cos(omega)*sin(kappa)+sin(omega)*sin(phi)*cos(kappa), sin(omega)*sin(kappa)-cos(omega)*sin(phi)*cos(kappa) ],
                          [-cos(phi)*sin(kappa),  cos(omega)*cos(kappa)-sin(omega)*sin(phi)*sin(kappa), sin(omega)*cos(kappa)+cos(omega)*sin(phi)*sin(kappa) ],
                          [ sin(phi)           , -sin(omega)*cos(phi)                                 , cos(omega)*cos(phi) ] ]
                          ).T.flatten())

    def UpdateTsai(self):
        setattr(self, 'vectF', np.array([self.fu, self.fv]))
        setattr(self, 'vectPP', np.array([self.cu, self.cv]))
        setattr(self, 'matR', inv(self.R.reshape(3,3)))
        if not abs(round(det(self.matR), 2))==1.0: SubLogger('CRITICAL', '|R| = %.2f =/= 1'% round(det(self.matR), 2))
        if not np.allclose(self.matR.T, inv(self.matR)): SubLogger('CRITICAL', 'R^T=/=R^{-1}')
        if det(self.matR)<0:
            matR=self.matR*(-1)
            setattr(self, 'matR', matR)
            setattr(self, 'R', matR.T.flatten())

        setattr(self, 'vectX0', self.C.reshape(3,1))

        setattr(self, 'matO', np.append(self.matR, -self.matR@self.vectX0, axis=1))
        setattr(self, 'matK', np.array([[self.fu, 0      , self.cu   ],
                                          [0      , self.fv, self.cv   ],
                                          [0      , 0      , self.pitch]])/self.pitch)
        setattr(self, 'matP', self.matK@self.matO)

    def ApplyDisto(self, direction, ptsIn):
        '''
        Apply a distortion model to given points [pixel]. It requests 
        the direction in order to ensure match between wishes and available model.
        
        direction ('add'|'remove'): direction, add/remove the distortion
        ptsIn (array [[x, y], [...]]): point to correct
        out:
            ptsOut (array [[x, y], [...]]): corrected point
        '''
        if not direction in ('add', 'remove'): SubLogger('CRITICAL', 'Unknown direction (\'add\'|\'remove\')')
        if not ptsIn.shape[1]==2: SubLogger('CRITICAL', 'wrong input points')

        if direction=='add' and self.distoType=='TSAI':
            vectPP_pxl=np.array([self.cu, self.cv])/self.pitch
            vectF_pxl=np.array([self.fu, self.fv])/self.pitch
            
            # Normalisation
            ptsIn_off=ptsIn-vectPP_pxl
            ptsIn_n=ptsIn_off/vectF_pxl
            rad2In_n=np.square(norm(ptsIn_n, axis=1))[:,np.newaxis]
            
            # Distortion correction
            dRad=rad2In_n*(self.k1+self.k2*rad2In_n)
            sumP1yP2x=np.sum(np.array([self.p2, self.p1])*ptsIn_n*2, axis=1)
            dTang=np.array([self.p2, self.p1])*rad2In_n/ptsIn_n+sumP1yP2x[:, np.newaxis]
            
            # Correction
            ptsOut=ptsIn+ptsIn_off*(dRad+dTang)
            
            # Origin recovery
            iX=np.where(ptsIn_off[:,[0]]==0)
            if np.any(iX): ptsOut[iX]=ptsIn[iX]
            iY=np.where(ptsIn_off[:,[1]]==0)
            if np.any(iX): ptsOut[iY]=ptsIn[iY]
            
            return ptsOut
            
        elif direction=='remove' and self.distoType=='Photometrix':
            # Normalisation
            ptsIn_n=ptsIn*self.pitch-np.array([self.cu, self.cv])-np.array([self.xp, self.yp])
            rad2In_n=np.square(norm(ptsIn_n, axis=1))[:,np.newaxis]

            # Distortion correction
            dRad=ptsIn_n*rad2In_n*(self.k1+self.k2*rad2In_n+self.k3*rad2In_n*rad2In_n)
            dTang=np.array([self.p1, self.p2])*(rad2In_n+2*ptsIn_n**2)  +  np.array([self.p2, self.p1])*2*np.prod(ptsIn_n, axis=1)[:,np.newaxis]
            
            # Correction
            ptsOut=ptsIn+(dRad+dTang)/self.pitch

            return ptsOut

        elif direction=='remove' and self.distoType=='BrownConrady':
            SubLogger('WARNING', 'Not sure of Brown-Conrady implementation')
            # Normalisation
            ptsIn_n=ptsIn/self.pitch-self.vectPP-np.array([self.xp, self.yp])
            radIn_n=norm(ptsIn_n, axis=1)[:,np.newaxis]

            # Distortion correction
            dRad=ptsIn_n*(self.k1*radIn_n**2+self.k2*radIn_n**4+self.k3*radIn_n**6)
            vectDistP=np.array([self.p1, self.p2])
            dTang=self.p1*radIn_n**2+self.p2*radIn_n**4*np.array([-np.sin(self.phi), np.cos(self.phi)])
            
            # Correction
            ptsOut_n=ptsIn_n+dRad+dTang
            ptsOut=ptsOut_n+self.vectPP
            
            return ptsOut*self.pitch

        elif self.distoType=='NULL':
            return ptsIn
        else:
            SubLogger('CRITICAL', 'correction impossible, wrong distortion model: %s'% self.distoType)

    def Obj2Img_Geo(self,ptsIn):
        '''
        Project geographic points to image frame

        ptsIn (array): point ground coordinates [[Long (L), Lat (P), H], [...]]
        out:
            ptsOut (array): point image coordinates [[x, y], [...]]
        '''
        if not ptsIn.shape[1]==3: SubLogger('CRITICAL', 'Input points must be 3D')
        if not 'matP' in self.__dir__():  SubLogger('CRITICAL', 'matrix P missing, please update (UpdateTsai()) the object before')
        
        ptsCart=Geo2Cart_Elli(ptsIn)
        ptsCart_h=np.append(ptsCart, np.ones([ptsIn.shape[0], 1]), axis=1)
        ptsOut_h=(self.matP@ptsCart_h.T).T
        ptsOut=ptsOut_h[:, :2]/ptsOut_h[:, [2]]
        ptsImg=self.ApplyDisto('add', ptsOut)
        
        return ptsImg

class RPCin:
    """
    Create a RPC python object from files. Currently able to read
    : XML, tiff tag (gdalinfo), RPB file, _RPC.TXT file
    An empty object can be created before RPC computation internaly.
    The object is based on Sklearn functions like PolynomialFeatures().
    Therefore, the polynomial order of coefficients is different. All 
    importation or exportation functions take care of it (even __str__).
    
    ## Order :
    # Sklearn poly from triple (x0, x1, x2): REF
    # 0,  1,  2,  3,  4 ,   5 ,   6 ,  7 ,   8 ,  9 ,  10,   11 ,   12 ,   13 ,    14 ,   15 ,  16,   17 ,   18 , 19
    # 1, x0, x1, x2, x0², x0x1, x0x2, x1², x1x2, x2², x0³, x0²x1, x0²x2, x0x1², x0x1x2, x0x2², x1³, x1²x2, x1x2², x2³
    # RPC from geo (Long_L, Lat_P, Hei_H): equal to Planet
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, L, P, H, LP, LH, PH, L², P², H², PLH, L³ , LP², LH², L²P, P³ , PH², L²H, P²H, H³
    # RPC from Fraser (X, Y, Z):
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, Y, X, Z, YX, YZ, XZ, Y², X², Z², XYZ,  Y³, YX², YZ², Y²X,  X³, XZ², Y²Z, X²Z, Z³
    # RPC from Planet (Long_L, Lat_P, Hei_H): Seth
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, L, P, H, LP, LH, PH, L², P², H², LPH, L³ , LP², LH², L²P, P³ , PH², L²H, P²H, H³

    
    pathCur (string): file path (default: None means an empty object)
    out:
        self (RPC object): available features printable through str(RPCin) or dir(RPCin)
        object attributes:
            path (str): original file path
            src (str): file type
            lineOffset, sampOffset, latOffset, longOffset, heiOffset (float): offset values
            lineScale,sampScale latScale, longScale, heiScale (float): scale values
            error_RpcCoef (lst): computation residuals
            matRpcCoef (array): RPC coefficients with Sklearn convention [x(sample), y(line)]
            error_InvRpcCoef (lst): computation residuals
            matInvCoef (array): inverse RPC coefficients with Sklearn convention [x(sample), y(line)]
            iCoef_RPC2Sklearn, iCoef_Sklearn2RPC: coefficient indices
        object functions:
            __init__(): initialtisation
            __str__(): returns printable version
            __write__(): returns writable list
            Comput_InvRPC(): computes inverse RPC
            Comput_RPC(): computes RPC
            Obj2Img(): transformation object to image
            Img2Obj_Z(): tranforation image to object
            InputNorm(): sets offeset and scale values
            Offset(): returns offset values
            Scale(): returns scale values
            Read_Rpb(), Read_RpcTxt(), Read_Tif(), Read_Xml(),
            Solver(): solver engine

    """
    iCoef_RPC2Sklearn=[0, 1, 2, 3, 7 , 4 , 5 , 8 , 6 , 9 , 11 , 14 , 17 , 12 , 10 , 13 , 15 , 18 , 16 , 19]
    iCoef_Sklearn2RPC=[0, 1, 2, 3, 5 , 6 , 8 , 4 , 7 , 9 , 14 , 10 , 13 , 15 , 11 , 16 , 18 , 12 , 17 , 19]
    #test=np.array([['1', 'L', 'P', 'H', 'LP', 'LH', 'PH', 'L2', 'P2', 'H2', 'PLH', 'L3' , 'LP2', 'LH2', 'L2P', 'P3' , 'PH2', 'L2H', 'P2H', 'H3']])
    #print('Initial:', test)
    #print('Sklearn:', test[:, iCoef_RPC2Sklearn])
    #print('RPC    :', test[:, iCoef_RPC2Sklearn][:,iCoef_Sklearn2RPC])
  
    def __init__(self, pathCur=None):
        if pathCur and not os.path.isfile(pathCur): 
            print(self.__doc__)
            SubLogger('CRITICAL', 'RPC path does not exists')
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
        elif pathCur and pathCur.endswith('_RPC.TXT'):
            self.src=pathCur.split('.')[-1]
            self.Read_RpcTxt()
        elif pathCur is None:
            self.src='Built-in'
        else:
            SubLogger('CRITICAL', 'Unknown RPC format (available: .XML, .tif, .RPB, _RPC.TXT): %s'% os.path.basename(pathCur))
    
    def __str__(self):
        strOut=str(self.__repr__())+':\n\t'
        strOut+='(),\n\t'.join([funct for funct in dir(self) if funct[0].isupper()])
        strOut+='\n'
        objDicOut=self.__dict__.copy()
        objDicOut.pop('matRpcCoef', None)
        objDicOut.pop('matInvCoef', None)
        strOut+=json.dumps(objDicOut, indent='\t', separators=(',', ':'))
        if 'matRpcCoef' in self.__dir__(): strOut+='\n\t"matRpcCoef":\n'+str(self.matRpcCoef)
        if 'matInvCoef' in self.__dir__(): strOut+='\n\t"matInvCoef":\n'+str(self.matInvCoef)
        return strOut
    
    def __write__(self, fileType='txt'):
        '''
        Create a writable list of string to export the RPC object to RPC file

        fileType ('txt'): define the writting method and tag names
        out:
            lstOut (list): writable list of string
        '''

        if fileType=='txt':
            tagTable=(('lineOffset', 'LINE_OFF'),
                      ('sampOffset', 'SAMP_OFF'),
                      ('latOffset' , 'LAT_OFF'),
                      ('longOffset', 'LONG_OFF'),
                      ('heiOffset' , 'HEIGHT_OFF'),
                      ('lineScale' , 'LINE_SCALE'),
                      ('sampScale' , 'SAMP_SCALE'),
                      ('latScale'  , 'LAT_SCALE'),
                      ('longScale' , 'LONG_SCALE'),
                      ('heiScale'  , 'HEIGHT_SCALE'),
                      )
            lstOut=['{}: {}\n'.format(tag, self.__getattribute__(key)) for key,tag in tagTable]
            
            matRpcCoef=self.matRpcCoef[:, self.iCoef_Sklearn2RPC]
            m=len(self.iCoef_Sklearn2RPC)
            lstOut+=['LINE_NUM_COEFF_{}: {}\n'.format(j+1, matRpcCoef[2,j]) for j in range(m)]
            lstOut+=['LINE_DEN_COEFF_{}: {}\n'.format(j+1, matRpcCoef[3,j]) for j in range(m)]
            lstOut+=['SAMP_NUM_COEFF_{}: {}\n'.format(j+1, matRpcCoef[0,j]) for j in range(m)]
            lstOut+=['SAMP_DEN_COEFF_{}: {}\n'.format(j+1, matRpcCoef[1,j]) for j in range(m)]
        
            return lstOut

        else:
            SubLogger('CRITICAL', 'Unknown fileType to write') 

    def Read_Xml(self):
        '''
        Read .XML (or .xml) files with RPC standard tags
        '''
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
        
        matRpcCoef=np.zeros([4,20], dtype=float)
        for i,tagCur in enumerate(['SAMPNUMCOEF','SAMPDENCOEF','LINENUMCOEF','LINEDENCOEF']):
            tagLink=imgPartLink+tagCur+'List/'+tagCur
            coefStrList=root.find(tagLink).text.strip().split()
            matRpcCoef[i,:]=[float(num) for num in coefStrList]
        
        self.matRpcCoef=matRpcCoef[:,self.iCoef_RPC2Sklearn]
    
    def Read_Tif(self):
        '''
        Read .TIF (or .tif) metadata with RPC standard tags
        '''
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
        
        matRpcCoef=np.zeros([4,20], dtype=float)
        for i,tagCur in enumerate(['SAMP_NUM_COEFF','SAMP_DEN_COEFF','LINE_NUM_COEFF','LINE_DEN_COEFF']):
            coefStrList=rpcPart[tagCur].split()
            matRpcCoef[i,:]=[float(num) for num in coefStrList]
        
        self.matRpcCoef=matRpcCoef[:,self.iCoef_RPC2Sklearn]
    
    def Read_Rpb(self):
        '''
        Read .RPB (or .rpb) file with RPC standard tags
        '''
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
        
        matRpcCoef=np.block([dicIn['sampNumCoef'],
                          dicIn['sampDenCoef'],
                          dicIn['lineNumCoef'],
                          dicIn['lineDenCoef']])
        
        self.matRpcCoef=matRpcCoef[:,self.iCoef_RPC2Sklearn]
    
    def Read_RpcTxt(self):
        '''
        Read _RPC.TXT file with RPC standard tags
        '''
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
        
        matRpcCoef=np.zeros([4,20], dtype=float)
        for i,keyCode in enumerate(['SAMP_NUM_COEFF','SAMP_DEN_COEFF','LINE_NUM_COEFF','LINE_DEN_COEFF']):
            for j in range(20):
                keyCur=keyCode+'_'+str(j+1)
                matRpcCoef[i,j]=dicIn[keyCur]
        
        self.matRpcCoef=matRpcCoef[:,self.iCoef_RPC2Sklearn]
    
    def InputNorm(self, offset, scale):
        '''
        Create the RPCin object and set in normalisation parameters from 
        external input.
        It can be used for object initialisation, e.g. objRpcPlus=RPCin.InputNorm(RPCin(), Offset, Scale)
        
        offset (tuple: [oL, oS, oL, oP, oH]): input offset
        scale (tuple: [sL, sS, sL, sP, sH]): input scale
        
        out:
            RPCin (obj):
        '''
        roundImg=0
        roundGrd=4
        roundHei=0

        self.sampOffset=np.round(offset[0], roundImg)
        self.lineOffset=np.round(offset[1], roundImg)
        self.longOffset=np.round(offset[2], roundGrd)
        self.latOffset =np.round(offset[3], roundGrd)
        self.heiOffset =np.round(offset[4], roundHei)
        
        self.sampScale=np.round(scale[0], roundImg)
        self.lineScale=np.round(scale[1], roundImg)
        self.longScale=np.round(scale[2], roundGrd)
        self.latScale =np.round(scale[3], roundGrd)
        self.heiScale =np.round(scale[4], roundHei)
        
        return self
    
    def Offset(self, d=5):
        '''
        Return an array with offset values used by coords normalisation.
        
        d (2|3|5): number of dimensions (default: 5)
        out:
            offset (array): 
                d=2: [oL, oS]), Line (L), Sample(S)
                d=3: [oL, oP, oH], Long (L), Lat (P), Height (H)
                d=5: [oL, oS, oL, oP, oH]), Line (L), Sample(S), Long (L), Lat (P), Height (H) 
        '''
        if not d in (2,3,5): SubLogger('CRITICAL', 'unknown dimension')
        if d==3:
            return np.array([self.longOffset, self.latOffset, self.heiOffset])
        elif d==2:
            return np.array([self.sampOffset, self.lineOffset])
        else:
            return np.array([self.sampOffset, self.lineOffset, self.longOffset, self.latOffset, self.heiOffset])

    def Scale(self, d=5):
        '''
        Return an array with scale values used by coords normalisation.
        
        d (2|3|5): number of dimensions (default: 5)
        out:
            scale (array): 
                d=2: [sL, sS]), Line (L), Sample(S)
                d=3: [sL, sP, sH], Long (L), Lat (P), Height (H)
                d=5: [sL, sS, sL, sP, sH]), Line (L), Sample(S), Long (L), Lat (P), Height (H) 
        '''
        if not d in (2,3,5): SubLogger('CRITICAL', 'unknown dimension')
        if d==3:
            return np.array([self.longScale, self.latScale, self.heiScale])
        elif d==2:
            return np.array([self.sampScale, self.lineScale])
        else:
            return np.array([self.sampScale, self.lineScale, self.longScale, self.latScale, self.heiScale])

    def Comput_InvRPC(self, orderPoly=3, solver=3):
        '''
        Compute inverse RPC coefficient by least square over a grid point.
        The gird point is a fixed range [-1,1], [-1,1], [-0.2, 0.2] of 
        5x5x5 (125) nomalised coorinates. The polynomial order can be adjusted. 
        Normalisation values identical to RPC.
        
        orderPloy (int:{1|2|3}): polynomial order [default=3]
        
        out:
            0: updated object
                info_InvCoef (list): computation residuals or eigen values
                matInvCoef (array): inverse RPC coefficient
        '''
        lstRequi=('lineOffset', 'sampOffset', 'latOffset', 'longOffset', 'heiOffset', 'lineScale', 'sampScale', 'latScale', 'longScale', 'heiScale')
        lstQuery=[keyCur in self.__dir__() for keyCur in lstRequi]
        if not all(lstQuery): SubLogger('CRITICAL', 'Normalisation parameters missing: %s'% (lstRequi[lstQuery.index(False)]))
        
        if not type(orderPoly)==int and not 0<orderPoly<4: SubLogger('CRITICAL', 'Wrong polynomial order')
        
        mesh=np.meshgrid(np.linspace(-1.1, 1.1, num=9),
                         np.linspace(-1.1, 1.1, num=9),
                         np.linspace(-0.3, 0.3, num=9))

        # [[Long, Lat, Hei], ...]
        pts3DN=np.hstack((mesh[0].reshape(-1,1),
                          mesh[1].reshape(-1,1),
                          mesh[2].reshape(-1,1)))
        pts3D=pts3DN*self.Scale(d=3)+self.Offset(d=3)
        pts2D=self.Obj2Img(pts3D)
        pts2DN=(pts2D-self.Offset(d=2))/self.Scale(d=2)
        nbPts=pts2DN.shape[0]
        
        ptsTripleN=np.append(pts2DN,pts3DN[:,[-1]], axis=1)
        
        matSolv,self.error_InvRpcCoef=self.Solver(ptsTripleN,pts3DN[:,:2], orderPoly, solver)
        
        self.matInvCoef=np.zeros([4,20], dtype=float)
        idVal=np.nonzero(matSolv)
        self.matInvCoef[idVal]=matSolv[idVal]
        return 0

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
            ptsOut (array nx2: [[x, y], [...]]): point image coordinates
        '''
        if not 'matRpcCoef' in dir(self): SubLogger('CRITICAL', 'RPC coeff missing')
        
        if not ptsIn.shape[1]==3: SubLogger('CRITICAL', 'Input points must be 3D')
        
        if not matAffine.shape[0]==matAffine.shape[1]==3: SubLogger('CRITICAL', 'Wrong affine transformation')
        
        if not 0<orderPoly<4: SubLogger('CRITICAL', 'Wrong polynomial order')
        
        nbPts=ptsIn.shape[0]
        
        pts3DN=(ptsIn-self.Offset(d=3))/self.Scale(d=3)
        poly=PolynomialFeatures(orderPoly)
        matPoly=poly.fit_transform(pts3DN)
        n=poly.powers_.shape[0] #poly.get_feature_names() not compatible with planet_common env

        
        matProd=(self.matRpcCoef[:,:n]@matPoly.T)
        pts2DN= (matProd[[0,2],:]/matProd[[1,3],:]).T
        
        pts2D= pts2DN*self.Scale(d=2)+self.Offset(d=2)
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
            ptsOut (array: [[L, P, H], [...]]): point ground coordinates 
        
        '''
        if not 'matInvCoef' in dir(self): SubLogger('CRITICAL', 'Inverse RPC coef missing')
        
        if not ptsIn.ndim==2 or not ptsIn.shape[1]==2: SubLogger('CRITICAL', 'Input points must be 2D [[x, y], [...]]')
        
        if not zIn.ndim==2 or not zIn.shape[1]==1: SubLogger('CRITICAL', 'Z input must be 2D [[Z], [...]]')
        
        if not ptsIn.shape[0]==zIn.shape[0]: SubLogger('CRITICAL', 'Different input point number')
        
        if not matAffine.shape[0]==matAffine.shape[1]==3: SubLogger('CRITICAL', 'Wrong affine transformation')
        
        if not 0<orderPoly<4: SubLogger('CRITICAL', 'Wrong polynomial order')
        
        nbPts=ptsIn.shape[0]
        
        pts2DH=np.append(ptsIn.T, np.ones([1,nbPts]), axis=0)
        pts2DAff=(matAffine@pts2DH).T[:,:2]
        
        pts2DN=(pts2DAff-self.Offset(d=2))/self.Scale(d=2)
        zN=(zIn-self.heiOffset)/self.heiScale
        ptsTripleN=np.append(pts2DN,zN, axis=1)
        
        poly=PolynomialFeatures(orderPoly)
        matPoly=poly.fit_transform(ptsTripleN)
        n=poly.powers_.shape[0] #poly.get_feature_names() not compatible with planet_common env
        
        matProd=(self.matInvCoef[:,:n]@matPoly.T)
        latLongN= (matProd[[0,2],:]/matProd[[1,3],:]).T
        
        pts3DN=np.append(latLongN, zN, axis=1)
        pts3D= pts3DN*self.Scale(d=3)+self.Offset(d=3)
        
        return pts3D
    
    def Comput_RPC(self, pts3D, pts2D, orderPoly=3, solver=3):
        '''
        Compute RPC coefficients.The polynomial order can be adjusted but 
        it remains linked to the GCP number. A maximum order stands at 3 due 
        to object design. A 1st order polynomial requires at least 
        7 GCPs (2: 19 and 3: 39). Normalisation values have to be set in before.
        
        pts3D (array: [[Long (L), Lat (P), H], [...]] or [[X, Y, Z], [...]]): 
            point ground coordinates not normalised
        pts2D (array: [[x, y], [...]]): points image coordinates not normalised
        orderPloy (int:{1|2|3}): polynomial order [default=2]
        
        out:
            0 (int): updated object
                matRpcCoef (array): RPC coefficient
        '''
        
        lstKeys=dir(self)
        lstRequi=('lineOffset', 'sampOffset', 'latOffset', 'longOffset', 'heiOffset', 'lineScale', 'sampScale', 'latScale', 'longScale', 'heiScale')
        lstQuery=[keyCur in self.__dir__() for keyCur in lstRequi]
        if not all(lstQuery): SubLogger('CRITICAL', 'Normalisation parameters missing: %s'% (lstRequi[lstQuery.index(False)]))
        
        if not pts2D.shape[0]==pts3D.shape[0]: SubLogger('CRITICAL', 'Different input point number')
        
        if not type(orderPoly)==int and not 0<orderPoly<4: SubLogger('CRITICAL', 'Wrong polynomial order')
        
        nbPts=pts2D.shape[0]
        nbFeat=PolynomialFeatures(orderPoly).fit(np.array([[1,2,3]])).powers_.shape[0]*2
        if (1<solver<4 and nbPts<nbFeat-1) or (-1<solver<2 and nbPts<nbFeat):
            SubLogger('CRITICAL', 'Not enough GCP for %i order polynimal: change either polynomial order, point number or solver method'% orderPoly)
        
        pts3DN=(pts3D-self.Offset(d=3))/self.Scale(d=3)
        pts2DN=(pts2D-self.Offset(d=2))/self.Scale(d=2)
        
        self.matRpcCoef=np.zeros([4,20], dtype=float)
        
        matSolv,self.error_RpcCoef=self.Solver(pts3DN,pts2DN, orderPoly, solver)
        
        idVal=np.nonzero(matSolv)
        self.matRpcCoef[idVal]=matSolv[idVal]
        
        return 0
    
    def Solver(self,pts3D, pts2D, orderPoly, solver):
        '''
        Pack up function of solver (SVD or LS) used by RPC computation. Solves 
        Ax=y of Ax=0 depending on chosen method. No check up in !
        
        pts3D (array: [[X1, Y1, Z1], ...]): points of A (normalised)
        pts2D (array: [[x1, y1], ...]):  point of y (or A if y=0) (normalised)
        orderPoly (int): polynomial order
        solver (int): solver method id
        out :
            (matOut,lstEigenVal):
                matOut (array(4,n)): coefficient matrix
                lstInfo (list): eigenvalue list (SVD) or residual list (LS)
        '''
        nbPts=pts2D.shape[0]
        
        poly=PolynomialFeatures(orderPoly)
        matPoly=poly.fit_transform(pts3D)
        n=poly.powers_.shape[0] #poly.get_feature_names() not compatible with planet_common env

        matOut=np.zeros([4,n], dtype=float)
        lstInfo=[]
        
        # Solver 0 (separated SVD Ax=0)
        if not solver:
            #[[1, X, Y, Z, -x, -xX, -xY, -xZ], ...]
            for i in range(2):
                matA=np.block([[matPoly, -pts2D[:,[i]]*matPoly ]])
                
                matE,matVt=svd(matA)[1:] 
                matV=matVt.T
                
                lstInfo.append(matE[-1])
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
                        lstInfo.append(matE[i])
                    if matV[2*n:,i].all(): 
                        matOut[2:,:]=matV[2*n:,i].reshape([2,n])
                        lstInfo.append(matE[i])
        
        # Solver 2 (separated SVD Ax=y, b1 and d1 =1)
        elif solver==2:
            #[[1, X, Y, Z, -xX, -xY, -xZ], ...]
            for i in range(2):
                matA=np.append(matPoly, -pts2D[:,[i]]*matPoly[:,1:], axis=1)
                matZ=np.append(matA, pts2D[:,[i]], axis=1)
                
                matE,matVt=svd(matZ)[1:] 
                matV=matVt.T
                
                m=2*n-1
                matVxy=matV[:m,m:]
                matVyy=matV[m:,m:]
                
                matX=-matVxy@inv(matVyy)
                matX=np.insert(matX, n, 1)
                
                lstInfo.append(matE[-1])
                matOut[2*i:2*i+2,:]= matX.reshape([2,n])

        # Solver 3 (combined least square Ax=y, b1 and d1 =1)
        elif solver==3:
            #A=[[1, X, Y, Z, -xX, -xY, -xZ, 0, 0, 0, ...], [0, 0, 0, ..., 1, X, Y, Z, -yX, -yY, -yZ], ...]
            matA=np.hstack((matPoly, 
                            -pts2D[:,[0]]*matPoly[:,1:], 
                            np.zeros([nbPts, 2*n-1]),
                            #
                            np.zeros([nbPts, 2*n-1]),
                            matPoly,
                            -pts2D[:,[1]]*matPoly[:,1:]
                            )).reshape(2*nbPts, (2*n-1)*2)
            #Y=[[x], [y], [x], [y], ...]
            matY=pts2D.reshape(2*nbPts,1)
            
            if matrix_rank(matA)<(2*n-1)*2: SubLogger('CRITICAL', 'Insufficient rank(A), check point distribution')

            #X=[[a0], [a1], ..., [b1], ..., [c0], [c1], ..., [d1], ...]
            matX,normRes=lstsq(matA, matY, rcond=-1)[:2]
            
            if not normRes: SubLogger('CRITICAL', 'Failure')
            matOut=np.insert(matX, [n, 3*n-1], [1]).reshape(4,n)
            lstInfo.append(float(normRes))
            
        return (matOut,lstInfo)

def AffineTransfo(ptsIn, ptsTrue, solver=0):
    '''
    Compute an affine transformation (using homogeneous coordinates) from 
    point pairs. The solver in use is an hard parameter (solv): 
    0=Least square, 1=Singular Value Decomposition, 2=SVD equal to 0 (not written yet)
    
    ptsIn (array: [[x, y], ...]): wrong measurement points
    ptsTrue (array: [[x, y], ...]): true position points
    solver (int): solver selection (default=0)
    
    out:
        matOut (array 3x3): affine transformation matrix [['x0', 'x1', 1], ['x0', 'x1', '1'], [0, 0, 1]]

    '''
    
    if not ptsIn.shape[0]==ptsTrue.shape[0]: SubLogger('CRITICAL', 'Different input point number')
    nbPts=ptsIn.shape[0]
    
    # Solver 0 (least square)
    if not solver: 
        matA=np.hstack((ptsIn,
                        np.ones([nbPts,1]) ))
        matX=lstsq(matA, ptsTrue, rcond=-1)[0]
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
        SubLogger('CRITICAL', 'Unknown solver (0|1)')
    
    return matOut

def Geo2Cart_Elli(ptGeo,elliAF='WGS84'):
    '''
    Convert geographic coordinates to cartesian coordinates
        
    ptGeo (array: [[Long (L), Lat (P), H], [...]]): geographic coordinates
    ptsIn (tuple or str): Ellipsoid name <'Bessel 1841'|'WGS84'|'PZ-90.11'> or tuple (a, f)
        [default='WGS84']
    
    out:
        ptsOut (array: [[X, Y, Z], [...]]): cartesiane coordinates
    
    '''
    # Elli: a, f
    dicElli={'Bessel 1841':(6377397.2, 1/299.15),
             'WGS84':(6378137,1/298.25722),
             'PZ-90.11':(6378136,1/298.25784)
             }
    
    if not ptGeo.ndim==2: SubLogger('CRITICAL', 'ptGeo must be 2D, [[Long (L), Lat (P), H], [...]]')
    nbPts,ndCoords=ptGeo.shape
    if not ndCoords==3: SubLogger('CRITICAL', 'ptGeo must be 3 components [Long (L), Lat (P), H]')
    if not -360<np.amin(ptGeo[:,:2])<360 or not -360<np.amax(ptGeo[:,:2])<360: SubLogger('CRITICAL', 'ptGeo (Long (L), Lat (P)) must be in degree [-360, 360]')
    radRatio=np.append(np.ones([nbPts,ndCoords-1])*pi/180,np.ones([nbPts,1]),axis=1)
    ptsIn=ptGeo*radRatio
    
    if type(elliAF)==str:
        a,f=dicElli[elliAF]
    elif type(elliAF)==tuple:
        a,f=elliAF
    
    e2=2*f-f**2
    n=a/np.sqrt(1-e2*np.square(np.sin(ptsIn[:,1])))
    nh=(n+ptsIn[:,2])[np.newaxis,:]

    
    matNH=np.vstack((n+ptsIn[:,2],n+ptsIn[:,2],(1-e2)*n+ptsIn[:,2]))
    matTriP=np.vstack((np.cos(ptsIn[:,1]),np.cos(ptsIn[:,1]),np.sin(ptsIn[:,1])))
    matTriL=np.vstack((np.cos(ptsIn[:,0]),np.sin(ptsIn[:,0]),np.ones([1,nbPts])))
    
    ptsOut=matNH*matTriP*matTriL
    
    return ptsOut.T

def Cart2Geo_Elli(ptCart,elliAF='WGS84',precision=1e-10):
    '''
    Convert cartesian coordinates to geographic coordinates
        
    ptCart (array: [[X, Y, Y], [...]]): cartesian coordinates
    ptsIn (tuple or str): Ellipsoid name <'Bessel 1841'|'WGS84'|'PZ-90.11'> or tuple (a, f)
        [default='WGS84']
    pression (float): iteration limit
    
    out:
        ptsOut (array: [[Long (L), Lat (P), H], [...]]): geographic coordinates
    
    '''
    # Elli: a, f
    dicElli={'Bessel 1841':(6377397.2, 1/299.15),
             'WGS84':(6378137,1/298.25722),
             'PZ-90.11':(6378136,1/298.25784)
             }

    if not ptCart.ndim==2: SubLogger('CRITICAL', 'ptCart must be 2D, [[X, Y, Y], [...]]')
    nbPts,ndCoords=ptCart.shape
    if not ndCoords==3: SubLogger('CRITICAL', 'ptCart must be 2D, [[X, Y, Y], [...]]')
    degRatio=np.append(np.ones([nbPts,ndCoords-1])*180/pi,np.ones([nbPts,1]),axis=1)

    if type(elliAF)==str:
        a,f=dicElli[elliAF]
    elif type(elliAF)==tuple:
        a,f=elliAF
    
    e2=2*f-f**2
    rho=np.sqrt(np.sum(np.square(ptCart[:,:2]), axis=1))
    
    phi_1=np.arctan2(ptCart[:,2],(1-e2)*rho)
    phi_0=phi_1-1
    i=0
    while any(np.abs(phi_0-phi_1)>precision):
        i+=1
        phi_0=phi_1
        N=a/np.sqrt(1-e2*np.square(np.sin(phi_0)))
        h=rho/np.cos(phi_0)-N
        phi_1=np.arctan2(ptCart[:,2],(1-e2*N/(N+h))*rho)
        
    lam=np.arctan2(ptCart[:,1],ptCart[:,0])
    
    ptsOut=np.vstack((lam,
                      phi_1,
                      h)).T*degRatio
    
    return ptsOut

def MaskedImg(pathImgIn, pathModelIn, pathDemIn, geomIn, pathImgOut=None, buffer=0, debug=False): 
    '''
    Mask outside part of the geomatry in the image 

    pathImgIn (str|array): Input image
    pathModelIn (str|TSAIin|RPCin): Input location model
    pathDemIn (str): input DEM path
    geomIn (json): overlap footprint as geojson['geometry'] object
    pathImgOut (str): output image path (default: None => return image frame)
    buffer (int): buffer (in pixel) around the area (default: 0)
        negative value shrinks the area
    out:
        create file including mask with extFeatKP extention
        AND
        lstPath (tuple): list of path including mask (ImgPath, RpcPath)
    '''
    # Input
    if not os.path.exists(pathDemIn): SubLogger('CRITICAL', 'DEM not found: %s'% pathDemIn)
    try:
        matCoordsGeo=np.array(geomIn['coordinates']).reshape(-1,2)
        nbPts, dimCur=matCoordsGeo.shape
    except ValueError:
        SubLogger('CRITICAL', "Input point must json['geometry'] with 2 components coordinates")

    if type(pathImgIn)==np.ndarray:
        img = pathImgIn
    else:
        if not os.path.exists(pathImgIn): SubLogger('CRITICAL', 'Image not found: %s'% pathImgIn)
        img = cv.imread(pathImgIn, cv.IMREAD_LOAD_GDAL)
    
    if type(pathModelIn)==TSAIin or type(pathModelIn)==RPCin:
        objModel=pathModelIn
    else:
        if not os.path.exists(pathModelIn): SubLogger('CRITICAL', 'Model not found: %s'% pathModelIn)
        if pathModelIn.endswith('.tsai'):
            objModel=TSAIin(pathModelIn)
        elif pathModelIn.endswith('_RPC.TXT'):
            objModel=RPCin(pathModelIn)
        else:
            SubLogger('CRITICAL', 'Unknown model type: %s'% os.path.basename(pathModelIn))

    if pathImgOut and os.path.exists(pathImgOut): os.remove(pathImgOut)

    # Read DTM
    with rasterio.open(pathDemIn) as demIn:
        tupIndices=rasterio.transform.rowcol(demIn.transform, matCoordsGeo[:,0].tolist(), matCoordsGeo[:,1].tolist())
        demHei=demIn.read(1)
        matCoordsGeo=np.append(matCoordsGeo, demHei[tupIndices][:, np.newaxis], axis=1)
        del demHei
    
    # Convert to image coords
    if type(objModel)==TSAIin:
        if not objModel.distoType in ('TSAI', 'NULL'): SubLogger('CRITICAL', 'Distortion type cannot be used : %s'% objCam.distoType)
        matCoordsImg=objModel.Obj2Img_Geo(matCoordsGeo)
    
    else:
        matCoordsImg=objModel.Obj2Img(matCoordsGeo)
    
    matCoordsImg=np.round(matCoordsImg).astype(int)
    
    # Mask creation
    mask=np.zeros(img.shape, dtype=np.float32)
    mask+=cv.fillPoly(np.zeros(img.shape, dtype=np.float32), 
                      matCoordsImg[np.newaxis, :, :], 
                      1.0)
    mask+=cv.polylines(np.zeros(img.shape, dtype=np.float32), 
                       matCoordsImg[np.newaxis, :, :], 
                       True,
                       1.0, 
                       2*buffer)
    if not np.any(mask): 
        SubLogger('ERROR', 'Area out of frame boundaries: %s\nCoords Geo:\n%s\nCoords Img:\n%s'% (os.path.basename(pathImgIn), str(matCoordsGeo), str(matCoordsImg)) )
        return 1
    

    if pathImgOut: 
        out=cv.imwrite(pathImgOut, img*mask.astype(bool))
        if not type(out)==bool or not out: SubLogger('CRITICAL', 'Masked image creation error : %s'% os.path.basename(pathImgIn))
    else:
        out=img*mask.astype(bool)
    
    if debug:
        return (out, matCoordsImg)
    else:
        return out

def Alti2ElliH(ptGeo, pathGeoid, eh2a=False):
    '''
    Apply geoid on geographic coordinates. It adds the geoid or applies 
    the opposite opperation with 'eh2a'
    
    ptGeo (array: [[Long (L), Lat (P), H], [...]]): geographic coordinates with H=altitude (or elli. hei. with 'eh2a')
    pathGeoid (str): raster geoid path
    eh2a (bool): reverse operation marker
    out:
        ptGeo (array: [[Long (L), Lat (P), H], [...]]): geographic coordinates with H=ellipsoidal height (or reverse)
    '''
    if not os.path.exists(pathGeoid): SubLogger('CRITICAL', 'Geoid file not found')
    if not ptGeo.ndim==2: SubLogger('CRITICAL', 'ptGeo must be 2D, [[Long (L), Lat (P), H], [...]]')
    nbPts,ndCoords=ptGeo.shape
    if not ndCoords==3: SubLogger('CRITICAL', 'ptGeo must be 3 components [Long (L), Lat (P), H]')
    
    with rasterio.open(pathGeoid) as imgIn:
        if not imgIn.crs=='EPSG:4326': SubLogger('CRITICAL', 'Geoid file must be in geographic coordinates (EPSG 4326)')
        matIndex=np.array([imgIn.index(longCur,latCur) for longCur, latCur, heightCur in ptGeo], dtype=int)
        imgGeoid=imgIn.read(1)
        imgBnd=imgIn.bounds
    
    try:
        geoidVal=imgGeoid[matIndex[:,1], matIndex[:,0]]
    except IndexError:
        print()
        print('  |  '.join([' '*5, '  Long ', '   Lat  ', 'x(col)', 'y(row)']))
        print('  |  '.join(['Min'.rjust(5),]+np.round(np.min(ptGeo[:,:2],axis=0), 5).astype(str).tolist()+np.min(matIndex,axis=0).astype(str).tolist()))
        print('  |  '.join(['Max'.rjust(5),]+np.round(np.max(ptGeo[:,:2],axis=0), 5).astype(str).tolist()+np.max(matIndex,axis=0).astype(str).tolist()))
        print('Image', imgBnd)
        print('Image PixelBox', imgGeoid.shape)
        with open(pathGeoid[:-4]+'_ptsBesides.txt', 'w') as fileOut:
            fileOut.writelines(['; '.join(coords)+'\n' for coords in ptGeo.astype(str).tolist()])
        SubLogger('CRITICAL', 'Geographic coordinates go beyond geoid coverage')
    
    if eh2a: geoidVal*=-1

    ptGeo[:,-1]+=geoidVal
    
    return ptGeo


#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
