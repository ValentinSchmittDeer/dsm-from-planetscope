#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''
# Copyright PythonValentinLibrary

import os, sys, logging, time
from datetime import datetime
from termcolor import colored

#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['SetupLogger', 'SubLogger', 'ProcessStdout', 'PrintPsItem', '_ColorfulFormatter']

#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def SetupLogger(name='', output=None, *, color=True ):
    '''
    Initialize logger and set its verbosity level to "DEBUG".
    
    name (str): the root module name of this logger
    output (str): a file name or a directory to save log. If None, will not save log file.
            If ends with ".txt" or ".log", assumed to be a file name.
            Otherwise, logs will be saved to `output/log.txt`.
    
    

    Returns:
        logging.Logger: a logger
    '''
    abbrev_name=''.join([char for char in name if char.isupper()])
    
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

def SubLogger(lvl, msg, *, name=None):
    """
    Log only for the first n times.
    Args:
        lvl (int): the logging level
        msg (str):
        name (str): name of the logger to use. Will use the caller's module by default.
    """
    caller_module, caller_key = _find_caller()
    
    msg= caller_key[-1] + ': ' + msg
    
    logging.getLogger(name or caller_module).log(lvl, msg)
    if lvl==logging.CRITICAL: sys.exit()

def _find_caller():
    """
    Returns:
        str: module name of the caller
        tuple: a hashable key to be used to identify different callers
    """
    frame = sys._getframe(2)
    while frame:
        code = frame.f_code
        if os.path.join("utils", "logger.") not in code.co_filename:
            mod_name = frame.f_globals["__name__"]
            #return mod_name, (code.co_filename, frame.f_lineno, code.co_name)
            return mod_name, (code.co_filename, frame.f_lineno, code.co_name)
        frame = frame.f_back

class ProcessStdout:
    '''
    Process progress stdout. Works in 2 modes: bar [default] and list.
    The Bar mode displays an overwriting progress bar based on maximum i and 
    current i. The List mode returns the standard output string used in logger
    based on full list and index number i.
    
    name (string): process name
    mode (string: bar|list): mode selection [default=bar]
    inputCur [mandatory]: in Bar mode, inputCur is maximum i (int)
                          in List mode, inputCur is looping list with stringable items
    lengthBar: progress bar length [default 50 (bar) or 30 (list)]
    
    out:
        self (ProcessStdout object):
    '''
    
    def __init__(self, name='Process', mode='bar', inputCur=None, lengthBar=None):
        self.startTime=datetime.now()
        self.name=name
        if not inputCur: 
                self.Error()
        
        if mode=='bar':
            if type(inputCur)==int:
                self.iMax=inputCur
            else:
                self.Error()
            if lengthBar:
                self.lenBar=lengthBar
            else:
                self.lenBar=50
            strOut='|{obj.name}{0}|  %  T-spent   T-left   T-total'.format(' '*(self.lenBar-len(name)),
                                                          obj=self)
            print(strOut)
        
        elif mode=='list':
            if type(inputCur)==list:
                self.list=inputCur
            else:
                self.Error()
            self.iMax=len(inputCur)
            if lengthBar:
                self.lenBar=lengthBar
            else:
                self.lenBar=30
    
    def Error(self):
        print(colored("ProcessStdout Error:", "red", attrs=["blink"]))
        print(self.__doc__)
        sys.exit()
    
    def ViewBar(self,i):
        ratio=(i+1)/self.iMax
        
        tSpent=(datetime.now()-self.startTime).total_seconds()
        tTotal=tSpent/ratio
        tLeft=tTotal-tSpent
        
        strOut='\r|{}{}| {:3.0f} {:02.0f}:{:02.0f}:{:02.0f} {:02.0f}:{:02.0f}:{:02.0f} {:02.0f}:{:02.0f}:{:02.0f} '.format(
                                   '#'*int(self.lenBar*ratio),
                                   ' '*int(self.lenBar*(1-ratio)),
                                   ratio*100,
                                   tSpent//3600,tSpent//60,tSpent%60,
                                   tLeft//3600,tLeft//60,tLeft%60,
                                   tTotal//3600,tTotal//60,tTotal%60,
                                   )
        if ratio==1:
            endCur='\n'
        else:
            endCur=''
        print (strOut, end=endCur)
        sys.stdout.flush()
    
    def ViewList(self,i):
        feat=self.list[i]
        ratio=(i+1)/self.iMax
        
        tSpent=(datetime.now()-self.startTime).total_seconds()
        tTotal=tSpent/ratio
        tLeft=tTotal-tSpent
        
        strOut='{}: {}  {:3.0f}%|{}{}| [{:02.0f}:{:02.0f}:{:02.0f} left]'.format(
                            self.name,
                            str(feat),
                            ratio*100,
                            '#'*int(self.lenBar*ratio),
                            ' '*int(self.lenBar*(1-ratio)),
                            tLeft//3600,tLeft//60,tLeft%60,
                            )
        return strOut

def PrintPsItem(lstIn,select=False):
    '''
    Prints or returns a selection list of Planetscope items.
    
    lstIn (json): json object from search "features" part
    select (bool): activate selection mode
    out:
        lstSelect (list:bool): list of selected object
    '''
    
    print(' i   Instr    SatId   ItemType         AcquDate        Cloud(%)   GSD    GCP')
    
    lstOut=list(zip(['{:6s}'.format(feat["properties"]['instrument']) for feat in lstIn],
                    ['{:6s}'.format(feat["properties"]['satellite_id']) for feat in lstIn],
                    ['{:6s}'.format(''.join([l for l in feat["properties"]['item_type'] if l.isupper() or l.isnumeric()])) for feat in lstIn],
                    ['{:<21s}'.format(feat["properties"]['acquired'][:-6].replace('T',' ')) for feat in lstIn],
                    ['{:3.0f}-{:<3.0f}'.format(feat["properties"]['cloud_cover']*100,
                                              feat["properties"]['cloud_percent']) for feat in lstIn],
                    ['{:6.2f}'.format(feat["properties"]['gsd']) for feat in lstIn],
                    ['{:2b}'.format(feat["properties"]['ground_control']) for feat in lstIn]))
    lstSelect=[]
    iMax=len(lstOut)
    
    for i in range(iMax):
        lineCur=lstOut[i]
        lineOut=[i]
        if not i==0: 
            linePrev=lstOut[i-1]
            for j in range(len(lineCur)):
                if lineCur[j]==linePrev[j]:
                    spaceB=''.join([' ']*(len(lineCur[j])-2))
                    lineOut.append('//'+spaceB)
                else:
                    lineOut.append(lineCur[j])
        else:
            lineOut+=lineCur
        print('{0[0]:>2d} - {0[1]} - {0[2]} - {0[3]} - {0[4]} - {0[5]} - {0[6]} - {0[7]}'.format(lineOut), end='')
        
        if select:
            lstSelect.append(input(':')=='y')
        else:
            print()
    
    if select:return lstSelect

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
            prefix = colored("\nSTOP", "red", attrs=["blink", "underline"])
        else:
            return log
        return prefix + " " + log


