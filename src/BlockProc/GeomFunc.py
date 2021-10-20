#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
from math import pi
import json
import xml.etree.ElementTree as ET
import logging
from pprint import pprint
import numpy as np
from numpy.linalg import inv, svd, lstsq, det, norm
from sklearn.preprocessing import PolynomialFeatures





from OutLib.LoggerFunc import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['TSAIin', 'RPCin', 'AffineTransfo', 'Geo2Cart_Elli', 'Cart2Geo_Elli']
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
    
    pathIn (str): tsai file path
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
                Update(): update class attributes from file attributs
                ApplyDisto(direc, pts): apply distortion model to list of points
    '''
    version='4'
    camType='PINHOLE'

    def __init__(self, pathIn):
        '''
        Read tsai file and create file attributes. It also updates class attrbutes.
        '''
        if not os.path.exists(pathIn): SubLogger('CRITICAL', 'pathIn does not exists')
        with open(pathIn) as fileIn:
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
        self.Update()

    def __str__(self):
        # Print float values
        dicOut=dict([(key, getattr(self,key)) for key in self.__dict__ if not type(getattr(self,key))==np.ndarray])
        # Print file vectors
        dicOut.update(dict([(key, str(getattr(self,key))) for key in self.__dict__ if type(getattr(self,key))==np.ndarray and not 'mat' in key]))
        # Print matrix size
        dicOut.update(dict([(key, 'np.array '+str(getattr(self,key).shape)) for key in self.__dict__ if type(getattr(self,key))==np.ndarray and 'mat' in key]))
        dicExt=dict([(key, str(getattr(self,key))) for key in self.__dir__() if not key in dicOut and not '_' in key])
        strOut=str(self.__repr__())+':\n\t'
        strOut+=json.dumps(dicExt, indent='\t', separators=(',', ':'))
        strOut+=json.dumps(dicOut, indent='\t', separators=(',', ':'))
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
        if self.distoType=='TSAI':
            lstTag=('k1', 'k2', 'p1', 'p2')
        if self.distoType=='Photometrix':
            lstTag=('xp', 'yp', 'k1', 'k2', 'k3', 'p1', 'p2', 'b1', 'b2')
        if not all([tag in self.__dir__() for tag in lstTag]): SubLogger('CRITICAL', 'Distortion model incomplet: %s'% self.distoType)
        lstOut+=['%s = %s\n'% (tag, str(getattr(self,tag))) for tag in lstTag]

        return lstOut

    def Update(self):
        setattr(self, 'vectF', np.array([self.fu, self.fv]))
        setattr(self, 'vectPP', np.array([self.cu, self.cv]))
        setattr(self, 'matR', self.R.reshape(3,3).T)
        if not abs(round(det(self.matR), 2))==1.0: SubLogger('CRITICAL', '|R| = %.2f =/= 1, wrong dataset'% round(det(self.matR), 2))
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
        Apply a distortion model to given points. The direction is requested
        in order to ensure match between wish and available model.
        
        direction ('add'|'remove'): direction, add/remove the distortion
        ptsIn (array [[x, y], [...]]): point to correct
        out:
            ptsOut (array [[x, y], [...]]): corrected point
        '''
        if not direction in ('add', 'remove'): SubLogger('CRITICAL', 'Unknown direction (\'add\'|\'remove\')')
        if not ptsIn.shape[1]==2: SubLogger('CRITICAL', 'wrong input points')

        if direction=='add' and self.distoType=='TSAI':
            vectPP_pxl=self.vectPP/self.pitch
            vectF_pxl=self.vectF/self.pitch
            
            # Normalisation
            ptsIn_off=ptsIn-vectPP_pxl
            ptsIn_n=ptsIn_off/vectF_pxl
            radIn_n=norm(ptsIn_n, axis=1)[:,np.newaxis]
            
            # Distortion correction
            dRad=(self.k1*radIn_n**2+self.k2*radIn_n**4)
            vectDistP=np.array([self.p1, self.p2])
            dTang=(2*vectDistP*ptsIn_n[:,[1,0]] + vectDistP[[1,0]]*(radIn_n/ptsIn_n+2*ptsIn_n))  #ptsIn_off* [:,np.newaxis]
            
            # Correction
            ptsOut=ptsIn+ptsIn_off*(dRad+dTang)
            
            # Origin recovery
            iX=np.where(ptsIn_off[:,[0]]==0)
            if np.any(iX): ptsOut[iX]=ptsIn[iX]
            iY=np.where(ptsIn_off[:,[1]]==0)
            if np.any(iX): ptsOut[iY]=ptsIn[iY]
            
            return ptsOut
            
        elif direction=='remove' and self.distoType=='Photometrix':
            pass
        else:
            SubLogger('CRITICAL', 'correction impossible, wrong distortion model: %s'% self.distoType)

class RPCin:
    """
    Create a RPC python object from metadata files. Currently able to read
    : XML, tiff tag, RPB file, _RPC.TXT file
    
    ## Order :
    # Sklearn poly from triple (x0, x1, x2): REF
    # 0,  1,  2,  3,  4 ,   5 ,   6 ,  7 ,   8 ,  9 ,  10,   11 ,   12 ,   13 ,    14 ,   15 ,  16,   17 ,   18 , 19
    # 1, x0, x1, x2, x0², x0x1, x0x2, x1², x1x2, x2², x0³, x0²x1, x0²x2, x0x1², x0x1x2, x0x2², x1³, x1²x2, x1x2², x2³
    # RPC from geo (Long_L, Lat_P, Hei_H): equal to Seth
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, L, P, H, LP, LH, PH, L², P², H², PLH, L³ , LP², LH², L²P, P³ , PH², L²H, P²H, H³
    # 0, 1, 2, 3, 5 , 6 , 8 , 4 , 7 , 9 , 14 , 10 , 13 , 15 , 11 , 16 , 18 , 12 , 17 , 19
    # RPC from Fraser (X, Y, Z):
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, Y, X, Z, YX, YZ, XZ, Y², X², Z², XYZ,  Y³, YX², YZ², Y²X,  X³, XZ², Y²Z, X²Z, Z³
    # RPC from Seth (Long_L, Lat_P, Hei_H):
    # 0, 1, 2, 3, 4 , 5 , 6 , 7 , 8 , 9 , 10 , 11 , 12 , 13 , 14 , 15 , 16 , 17 , 18 , 19
    # 1, L, P, H, LP, LH, PH, L2, P2, H2, LPH, L3 , LP2, LH2, L2P, P3 , PH2, L2H, P2H, H3

    
    pathCur (string): file path
    
    out:
        self (RPC object): available features printable through str(RPCin) or dir(RPCin)
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
            SubLogger('CRITICAL', 'pathCur does not exists')
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
                      ('longOffset', 'LONG_OFF'),
                      ('latOffset' , 'LAT_OFF'),
                      ('heiOffset' , 'HEIGHT_OFF'),
                      ('lineScale' , 'LINE_SCALE'),
                      ('sampScale' , 'SAMP_SCALE'),
                      ('longScale' , 'LONG_SCALE'),
                      ('latScale'  , 'LAT_SCALE'),
                      ('heiScale'  , 'HEIGHT_SCALE'),
                      'LINE_NUM_COEFF_',
                      'LINE_DEN_COEFF_',
                      'SAMP_NUM_COEFF_',
                      'SAMP_DEN_COEFF_')
        else:
            SubLogger('CRITICAL', 'Unknown fileType to write')

        lstOut=['{}: {}\n'.format(tag, self.__getattribute__(key)) for key,tag in tagTable[:-4]]
        
        matRpcCoef=self.matRpcCoef[:, self.iCoef_Sklearn2RPC]
        m=matRpcCoef.shape[1]
        for i, tag in enumerate(tagTable[-4:]):
            lstOut+=['{}{}: {}\n'.format(tag, j+1, matRpcCoef[i,j]) for j in range(m)]
        
        return lstOut

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
        roundGrd=5
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
        if not all([keyCur in self.__dir__() for keyCur in lstRequi]): SubLogger('CRITICAL', 'Normalisation parameters missing')
        
        if not type(orderPoly)==int and not 0<orderPoly<4: SubLogger('CRITICAL', 'Wrong polynomial order')
        
        mesh=np.meshgrid(np.linspace(-1.1, 1.1, num=9),
                         np.linspace(-1.1, 1.1, num=9),
                         np.linspace(-0.3, 0.3, num=7))

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
            ptsOut (array nx2: [[x, y], [...]]): points image coordinates
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
            0 (int): updated object
                matRpcCoef (array): RPC coefficient
        '''
        
        lstKeys=dir(self)
        lstReq=('lineOffset', 'sampOffset', 'latOffset', 'longOffset', 'heiOffset', 'lineScale', 'sampScale', 'latScale', 'longScale', 'heiScale')
        if not all([req in self.__dir__() for req in lstReq]): SubLogger('CRITICAL', 'Normalisation parameters missing')
        
        if not pts2D.shape[0]==pts3D.shape[0]: SubLogger('CRITICAL', 'Different input point number')
        
        if not type(orderPoly)==int and not 0<orderPoly<4: SubLogger('CRITICAL', 'Wrong polynomial order')
        
        nbFeat=PolynomialFeatures(orderPoly).fit(np.array([[1,2,3]])).powers_.shape[0]*2
        if pts2D.shape[0]<nbFeat:
            if pts2D.shape[0]<nbFeat-1 or not solver==2:
                SubLogger('CRITICAL', 'Not enough GCP for %i order polynimal'% orderPoly)
        
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
                            )).reshape(-1, (2*n-1)*2)
            #Y=[[x], [y], [x], [y], ...]
            matY=pts2D.reshape(-1,1)
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
#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
