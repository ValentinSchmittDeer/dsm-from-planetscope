#!/usr/bin/env python
# -*- coding: UTF-8 -*-'''

import os, sys
import json

#-------------------------------------------------------------------
# Usage
#-------------------------------------------------------------------
__title__=os.path.basename(sys.argv[0])[:-3]
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['MakeFiter', ]
#-----------------------------------------------------------------------
# Hard argument
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

def MakeFiter(argsDic):
    '''
    Create API filter based on past in parameters
    
    argsDic (dict): input arguments as dictionary (only required ones)
    
    out:
        jojo (json obj):
        OR
        error (int): {1:'Unknown key', 2:'Only 1 feature is managened in geometry file for the moment'}
    '''
    filterOut= {"type": "AndFilter","config": []}
    
    for key in argsDic:
        if key=='geom':
            if not len(argsDic[key]['features'])==1: return 2
            geomIn= argsDic[key]['features'][0]['geometry']
            print(json.dumps(geomIn, indent=2))

            if geomIn['type']=='MultiPolygon':
                if not len(geomIn['coordinates'])==1: return 1
                coordIn=geomIn['coordinates'][0]
                del geomIn
                geomIn={"type": "Polygon",
                        "coordinates":coordIn}


            filterOut['config'].append(geomIn)

        elif key=='itemType':
            filterNew={"type":"StringInFilter",
                        "field_name":"item_type",
                        "config":argsDic[key]
                        }

            filterOut['config'].append(filterNew)

        elif key=='date':
            filterNew = {"type": "DateRangeFilter",
                      "field_name": "acquired",
                      "config": {
                        "gte": "2021-02-20T00:00:00.000Z",
                        "lte": "2021-02-22T00:00:00.000Z"
                      }
                    }

        else:
            print(key)
            return 1


    
#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
