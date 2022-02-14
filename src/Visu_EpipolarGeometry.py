#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys, logging, argparse
from termcolor import colored
from pprint import pprint

import numpy as np
from numpy.linalg import inv

from importlib.util import find_spec
checkPlanetCommon=find_spec('planet_opencv3') is not None
if checkPlanetCommon:
    from planet_opencv3 import cv2 as cv
else:
    import cv2 as cv

from BlockProc import GeomFunc

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0])[:-3]
__author__='Valentin Schmitt'
__version__=1.0
parser = argparse.ArgumentParser(description='''
%s (v%.1f by %s):
    Main Task
Build up a epipolar tool image geometry controle. It read phyiscal models.

**************************************************************************
> Read ORI files
> Compute relative orientation matrix (F)
> Run interactive tool for point selection and residual extraction
**************************************************************************
'''% (__title__,__version__,__author__),
formatter_class=argparse.RawDescriptionHelpFormatter)
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
class ORIin():
    '''
    Very basic version of ORI file reading
    
    oriPath (str): file path
    oriFormPath (str): ori template path (not used yet)
    
    out:
        (Obj): object holding ori information
    '''
    
    def __init__(self, oriPath, oriFormPath):
        with open(oriPath) as oriFile:
            for i,lineCur in enumerate(oriFile.readlines()):
                if lineCur.startswith('$'): continue
                strCur=lineCur.strip().split()
                
                if i==1:
                    self.imgId=int(strCur[0])
                elif i==3:
                    self.fu=float(strCur[0])
                    self.fv=float(strCur[0])
                    self.vectF=np.array([self.fu, self.fv])
                elif i==5:
                    self.pitch=float(strCur[0])
                elif i==7:
                    self.pixNum=(int(strCur[0]),int(strCur[1]))
                elif i==9:
                    self.cu=float(strCur[0])
                    self.cv=float(strCur[1])
                    self.vectPP=np.array([self.cu, self.cv])
                elif i==11:
                    self.matK=np.zeros((3,3))
                    self.matK[0,:]=[float(word) for word in strCur]
                elif i==12:
                    self.matK[1,:]=[float(word) for word in strCur]
                elif i==13:
                    self.matK[2,:]=[float(word) for word in strCur]
                elif i==15:
                    self.matR=np.zeros((3,3))
                    self.matR[0,:]=[float(word) for word in strCur]
                elif i==16:
                    self.matR[1,:]=[float(word) for word in strCur]
                elif i==17:
                    self.matR[2,:]=[float(word) for word in strCur]
                elif i==19:
                    self.vectX0=np.array([float(word) for word in strCur]).reshape(3,-1)
        try:
            self.matR,self.vectX0,self.matK
            self.MatProj()
        except NameError:
            logger.error('ORI file incomplet')
        
    
    def __str__(self):
        return self.__dict__
    
    def MatProj(self):
        '''Compute the projection matrix'''
        self.matO=np.block([self.matR, -self.matR@self.vectX0])
        self.matP=self.matK@self.matO

class SelectTool:
    '''
    Selection tool including window management, mousse call back 
    functions (...Mousse) and process function.
    
    img1Path (str): base image path
    img2Path (str): match image path
    pinSize (int): cross size in pixel
    matF (np.array): F matrix, relative projection (3x3)
    
    '''
    
    def __init__(self, img1Path, img2Path, matF, wS, pinSize=1000):
        self.img1 = cv.imread(img1Path, -1)
        self.clone1=self.StretchImg(self.img1)
        self.out1=self.StretchImg(self.img1)
        self.nameBase='Base: '+os.path.basename(img1Path).split('.')[0]
        
        self.img2 = cv.imread(img2Path, -1)
        self.clone2=self.StretchImg(self.img2)
        self.out2= self.StretchImg(self.img2)
        self.nameMatch='Match: '+os.path.basename(img2Path).split('.')[0]
        
        cv.namedWindow(self.nameBase, cv.WINDOW_NORMAL)
        cv.setMouseCallback(self.nameBase, self.BaseImgMousse)
        cv.namedWindow(self.nameMatch, cv.WINDOW_NORMAL)
        cv.setMouseCallback(self.nameMatch, self.MatchImgMousse)
        
        self.transfImg1=np.identity(3)
        self.transfImg2=np.identity(3)
        
        self.linePts=np.zeros(1)
        self.checkGcp=False
        self.delta=pinSize//2
        self.matF=matF
        self.wS=wS
        
    def show_image(self):
        return self.out1
    
    def BaseImgMousse(self, event, x, y, flags, parameters):
        if event == cv.EVENT_MBUTTONDOWN:
            self.wheelPts=(x,y)
        
        elif event == cv.EVENT_MBUTTONUP:
            if not self.wheelPts==(x,y):
                self.clone1,self.transfImg1=self.ZoomOpt(self.img1,self.clone1,self.transfImg1,x,y)
                self.out1=self.clone1.copy()
                cv.imshow(self.nameBase, self.out1)
        
        elif event == cv.EVENT_RBUTTONDOWN:
            self.ClearDisplay()
        
        #Epipolar tool (left click)
        elif event == cv.EVENT_LBUTTONDOWN:
            # New pin on left mouse button click
            self.out1=self.clone1.copy()
            self.DrawCross(self.out1,x,y)
            cv.imshow(self.nameBase, self.out1)

            # And epipolar line on match image
            self.linePts= self.EpipolCoords([x,y])
            self.out2= self.clone2.copy()
            cv.line(self.out2, tuple(self.linePts[0,:]), tuple(self.linePts[1,:]), (0,0,255), 10)
            cv.imshow(self.nameMatch, self.out2)
            #cv.resizeWindow(self.nameMatch, int(self.wS*2000), int(self.wS*2000))
            
            self.checkGcp=False
    
    def MatchImgMousse(self, event, x, y, flags, parameters):
        if event == cv.EVENT_MBUTTONDOWN:
            self.wheelPts=(x,y)
        
        elif event == cv.EVENT_MBUTTONUP:
            if not self.wheelPts==(x,y):
                self.clone2,self.transfImg2=self.ZoomOpt(self.img2,self.clone2,self.transfImg2,x,y)
                self.out2=self.clone2.copy()
                cv.imshow(self.nameMatch, self.out2)
        
        elif event == cv.EVENT_RBUTTONDOWN:
            self.ClearDisplay()
        
        #GCP tool (left click)
        elif event == cv.EVENT_LBUTTONDOWN and self.linePts.any() and not self.checkGcp:
            self.checkGcp=True
            #self.out2=self.clone2.copy()
            self.DrawCross(self.out2,x,y,'g')
            
            residPts=self.ResidCoords([x,y])
            cv.line(self.out2,tuple(residPts[0,:]),tuple(residPts[1,:]),(0,0,255), 10)
            cv.imshow(self.nameMatch, self.out2)
    
    # Clear tool (right click)
    def ClearDisplay(self):
        self.clone1 = self.StretchImg(self.img1)
        self.out1=self.clone1.copy()
        cv.imshow(self.nameBase, self.out1)
        
        self.clone2=self.StretchImg(self.img2)
        self.out2= self.clone2.copy()
        cv.imshow(self.nameMatch, self.out2)
        
        self.transfImg1=np.identity(3)
        self.transfImg2=np.identity(3)
        
        self.linePts=np.zeros(1)
        self.checkGcp=False
    
    # Cross Drawing tool (left click)
    def DrawCross(self, img, x, y,colour='r'):
        if colour=='r':
            c=(0,0,255)
        elif colour=='g':
            c=(0,255,0)
        
        cv.line(img, (x-self.delta,y), (x+self.delta,y), c, 10)
        cv.line(img, (x,y-self.delta), (x,y+self.delta), c, 10)
    
    # ZoomIn tool (wheel drawing)
    def ZoomOpt(self, img, clone, transfo, x, y):
        nbRow,nbCol= img.shape[:2]

        r=(nbCol)/(nbRow)
        
        xStart,yStart=self.wheelPts
        self.wheelPts=None
        xCen,yCen=(xStart+x)/2, (yStart+y)/2
        widZoom=abs((x-xStart+(y-yStart)*r)/2)
        heiZoom=widZoom/r
        
        ptsZoomRect= np.float32([[xCen-widZoom/2,yCen-heiZoom/2],
                                 [xCen+widZoom/2,yCen-heiZoom/2], 
                                 [xCen-widZoom/2,yCen+heiZoom/2], 
                                 [xCen+widZoom/2,yCen+heiZoom/2]])
        
        fullRectPts= np.float32([[0,0],
                               [nbCol,0],
                               [0,nbRow],
                               [nbCol,nbRow]])
        
        addTransfo=cv.getPerspectiveTransform(ptsZoomRect, fullRectPts)
        
        if np.array_equal(transfo,np.identity(3)):
            transfo=addTransfo
        else:
            ptsRect=np.vstack((ptsZoomRect.T,np.ones([1,4])))
            ptsRectInit=(inv(transfo)@ptsRect).T[:,:-1]
            ptsRectInit=np.float32(ptsRectInit)
            transfo= cv.getPerspectiveTransform(ptsRectInit, fullRectPts)
        
        return (cv.warpPerspective(clone, addTransfo, (nbCol, nbRow)),transfo)
    
    # Epipolar line computation
    def EpipolCoords(self,coordIn):
        ptIn=np.array(coordIn+[1]).reshape(3,-1)
        ptInInit=inv(self.transfImg1)@ptIn
        if args.debug: logger.info('Point in base image (pixel)= '+str(ptInInit.flatten()))
        
        lineParam_h=(self.matF@ptInInit).flatten()
        lineParam=-lineParam_h[1:]/lineParam_h[0]
        if args.debug: logger.info('Epipolar line parameters (pixel)= '+str(lineParam))
        
        maxRow=np.size(self.img2,0)
        # [[x1,x2],[y1,y2],[1,1]]
        ptsOutInit=np.array([[lineParam[0]*0+lineParam[1], lineParam[0]*maxRow+lineParam[1]],
                             [0, maxRow,],
                             [1, 1]])
        ptsOut=self.transfImg2@ptsOutInit
        
        return ptsOut[:-1,:].T.astype(int)
    
    #Residual line computation
    def ResidCoords(self,coordIn):
        ptIn=np.array(coordIn+[1]).reshape(3,-1)
        ptInInit=inv(self.transfImg2)@ptIn
        if args.debug: logger.info('Point in match image (pixel)= '+str(ptInInit.flatten()))
        
        ptsLine=np.append(self.linePts.T,np.ones([1,2]),axis=0)
        ptsLineInit=inv(self.transfImg2)@ptsLine
        p0=ptsLineInit[0:2,0].flatten()
        
        lineParam=np.subtract.reduce(ptsLineInit,axis=1)[:-1]
        a=np.array([-np.sum(ptInInit.flatten()[:-1]*lineParam),
                    np.sum(np.array([-p0[1], p0[0]])*lineParam)])
        b=np.array([[lineParam[0], lineParam[1]],
                    [-lineParam[1], lineParam[0]]])
        
        ptOutInit=np.append(-(inv(b)@a),1).reshape(3,-1)
        ptOut=(self.transfImg2@ptOutInit)
        ptResid=np.append(ptIn,ptOut,axis=1)[:-1,:]
        
        residLen=np.power(np.subtract(ptInInit,ptOutInit),2).sum()**0.5
        logger.info('Match residuals (pixel)= '+str(round(residLen,1)))
        
        return ptResid.T.astype(int)

    # 16 bits images
    def StretchImg(self, imgIn):
        if not imgIn.dtype=='uint16': return imgIn.copy()

        a=1/(np.amax(imgIn)-np.amin(imgIn))
        b=-a*np.amin(imgIn)

        return a*imgIn+b

def SelectManag(img1Path, img2Path, matF, wScale):
    '''
    Top layer of interactive window with OpenCV
    
    img1Path (str): base image path
    img2Path (str): match image path
    matF (np.array): F matrix, relative projection (3x3)
    
    '''
    logger.warning('Selection tool ON')
    baseImgDrawing=SelectTool(img1Path,img2Path,matF, wScale)
    winName=baseImgDrawing.nameBase
    logger.warning('\t-ESC to quit')
    logger.warning('\t-Select a point on base image (left click)')
    logger.warning('\t  and its matching point in the match image (left click)')
    logger.warning('\t-Zoom in by wheel click (window drawing)')
    logger.warning('\t-Reset window view by right click')
    
    while(1):
        cv.imshow(winName,baseImgDrawing.show_image())
        #cv.resizeWindow(winName, int(wScale*2000), int(wScale*2000))
        
        if cv.waitKey(20) & 0xFF == 27:
            break
    cv.destroyAllWindows()

class _ColorfulFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        self._root_name = kwargs.pop("root_name") + "."
        self._abbrev_name = kwargs.pop("abbrev_name", "")
        if len(self._abbrev_name):
            self._abbrev_name = self._abbrev_name + "."
        super(_ColorfulFormatter, self).__init__(*args, **kwargs)

    def formatMessage(self, record):
        record.name = record.name.replace(self._root_name, self._abbrev_name)
        log = super(_ColorfulFormatter, self).formatMessage(record)
        if record.levelno == logging.WARNING:
            prefix = colored("WARNING", "red")
        elif record.levelno == logging.ERROR:
            prefix = colored("ERROR", "red", attrs=["underline"])
        elif record.levelno == logging.ERROR or record.levelno == logging.CRITICAL:
            prefix = colored("STOP", "red", attrs=["blink", "underline"])
        else:
            return log
        return prefix + " " + log

def SetupLogger(output=None, *, color=True, name=__title__, abbrev_name=''.join([char for char in __title__ if char.isupper()])):
    '''
    Initialize logger and set its verbosity level to "DEBUG".
    
    output (str): a file name or a directory to save log. If None, will not save log file.
            If ends with ".txt" or ".log", assumed to be a file name.
            Otherwise, logs will be saved to `output/log.txt`.
    name (str): the root module name of this logger
    abbrev_name (str): an abbreviation of the module, to avoid long names in logs.
            Set to "" to not log the root module in logs.
            By default, will abbreviate "detectron2" to "d2" and leave other
            modules unchanged.

    Returns:
        logging.Logger: a logger
    '''
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    
    plain_formatter = logging.Formatter(
        "[%(asctime)s] %(name)s %(levelname)s: %(message)s", datefmt="%m/%d %H:%M:%S"
    )
    
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    if color:
        formatter = _ColorfulFormatter(
            colored("[%(asctime)s %(name)s]: ", "green") + "%(message)s",
            datefmt="%m/%d %H:%M:%S",
            root_name=name,
            abbrev_name=str(abbrev_name),
        )
    else:
        formatter = plain_formatter
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # file logging: all workers
    if output is not None:
        if output.endswith(".txt") or output.endswith(".log"):
            filename = output
        else:
            filename = os.path.join(output, "log.txt")
        if distributed_rank > 0:
            filename = filename + ".rank{}".format(distributed_rank)
        PathManager.mkdirs(os.path.dirname(filename))

        fh = logging.StreamHandler(_cached_log_stream(filename))
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(plain_formatter)
        logger.addHandler(fh)

    return logger
    
#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        print()
        logger = SetupLogger()
        #---------------------------------------------------------------
        # Retrieval of arguments
        #---------------------------------------------------------------
        #Optional arguments
        parser.add_argument('-img1', required=True,help='Image1 path')
        parser.add_argument('-img2', required=True,help='Image2 path')
        parser.add_argument('-camName', required=True,help='Camera name fromat (e.g. {}.tsai)')
        # ORI file not in-use
        parser.add_argument('-oriForm', default='/Volumes/LocalData/valentin/Data/Geoengine/S3_CompVis/CompVis_Labs/Format.ori',help='Ori form file path')
        
        parser.add_argument('-s',type=float,default=1,help='Window size, [0, 1] per dim')
        parser.add_argument('-debug',action='store_true',help='Debug mode')
        
        args = parser.parse_args()
        
        logger.info("Arguments: " + str(vars(args)))
        
        #---------------------------------------------------------------
        # Check input
        #---------------------------------------------------------------
        img1Path=args.img1
        if not os.path.exists(img1Path): raise RuntimeError("No image 1")
        img2Path=args.img2
        if not os.path.exists(img2Path): raise RuntimeError("No image 2")
        
        dirCur=os.path.dirname(args.img1)
        cam1Path=os.path.join(dirCur, args.camName.format(os.path.basename(args.img1).split('.')[0]))
        if not os.path.exists(cam1Path): raise RuntimeError("No image 1 camera")
        cam2Path=os.path.join(dirCur, args.camName.format(os.path.basename(args.img2).split('.')[0]))
        if not os.path.exists(cam2Path): raise RuntimeError("No image 2 camera")
        
        #---------------------------------------------------------------
        # Geometry setting
        #---------------------------------------------------------------
        if args.camName.endswith('.ori'):
            cam1=ORIin(cam1Path, args.oriForm)
            cam2=ORIin(cam2Path, args.oriForm)
        elif args.camName.endswith('.tsai'):
            cam1=GeomFunc.TSAIin(cam1Path)
            cam2=GeomFunc.TSAIin(cam2Path)
        else:
            raise RuntimeError("Unknown camera type")
        
        
        vectOrtho=cam2.matP@np.append(cam1.vectX0,[[1]], axis=0)
        matOrthoSkew=np.array([[0, -vectOrtho[2,0], vectOrtho[1,0]],
                               [vectOrtho[2,0] , 0, -vectOrtho[0,0]],
                               [-vectOrtho[1,0], vectOrtho[0,0], 0]])
        cam1MatPplus=cam1.matP.T@inv(cam1.matP@cam1.matP.T)
        matF=matOrthoSkew@cam2.matP@cam1MatPplus
        if args.debug: logger.info('F=\n'+str(matF))
        
        #---------------------------------------------------------------
        # Tool
        #---------------------------------------------------------------
        SelectManag(img1Path, img2Path, matF, args.s)
        
    #---------------------------------------------------------------
    # Exception management
    #---------------------------------------------------------------
    except RuntimeError as msg:
        logger.critical(msg)
