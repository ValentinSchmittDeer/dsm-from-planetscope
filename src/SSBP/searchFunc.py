#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

import os, sys
import json
import requests

from OutLib.LoggerFunc import *
from VarCur import *

#-----------------------------------------------------------------------
# Hard argument
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['PlAuth', 'MakeFiter', 'PostRequest']
SetupLogger(name=__name__)
#SubLogger('WARNING', 'jojo')
#-----------------------------------------------------------------------
# Hard command
#-----------------------------------------------------------------------
def PlAuth():
    '''
    Create python web session using the env var $PL_API_KEY.
    The env var can be added in ~/.bashrc: export PL_API_KEY='xxx'

    out:
        session (request obj): active session
    ''' 
    PLANET_API_KEY = os.getenv('PL_API_KEY')
    if not PLANET_API_KEY: SubLogger('CRITICAL', '$PL_API_KEY not found in .bashrc')

    session = requests.Session()
    session.auth = (PLANET_API_KEY, '')

    return session

def MakeFiter(argsDic,nameSearch):
    '''
    Create API filter based on past in parameters
    
    argsDic (dict): input arguments as dictionary (only required ones)
    
    out:
        jojo (json obj):
    '''
    filterOut= {"item_types": argsDic['itemType'],
                "name": nameSearch,
                "filter": {"type": "AndFilter","config": []}}
    del argsDic['itemType']

    for key in argsDic:
        if key=='geom':
            if not len(argsDic[key]['features'])==1: SubLogger('CRITICAL', 'Only 1 feature is managened in geometry file for the moment')
            filterNew={"type": "GeometryFilter",
                    "field_name": "geometry"}

            geomIn= argsDic[key]['features'][0]['geometry']

            if geomIn['type']=='MultiPolygon':
                if not len(geomIn['coordinates'])==1: return 1
                filterNew['config']= {"type": "Polygon",
                        "coordinates":geomIn['coordinates'][0]}
            else:
                filterNew['config']= geomIn

        elif key=='inst':
            if not argsDic[key]: continue
            filterNew= {"type":"StringInFilter",
                      "field_name":"instrument",
                      "config":argsDic[key]
                      }

        elif key=='dateAcq':
            if not argsDic[key]: continue
            filterNew= {"type": "DateRangeFilter",
                      "field_name": "acquired",
                      "config": {
                        "gte": argsDic[key][0].strftime('%Y-%m-%dT%H:%M:%SZ'),
                        "lte": argsDic[key][1].strftime('%Y-%m-%dT%H:%M:%SZ')
                      }
                    }

        elif key=='cloudUnder':
            if not argsDic[key]: continue
            filterNew= {"type": "RangeFilter",
                        "field_name": "cloud_percent",
                        "config": {"lte": argsDic[key]}
                        }
            filterOut['filter']['config'].append(filterNew)
            filterNew= {"type": "RangeFilter",
                        "field_name": "cloud_cover",
                        "config": {"lte": round(argsDic[key]/100,2)}
                        }

        elif key=='viewAngle':
            if not argsDic[key]: continue
            filterNew= {"type": "RangeFilter",
                        "field_name": "view_angle",
                        "config": {"lte": argsDic[key]}
                        }

        elif key=='quali':
            if not argsDic[key]: continue
            filterNew= {"type":"StringInFilter",
                      "field_name":"quality_category",
                      "config":argsDic[key]
                      }

        elif key=='assetType':
            if not argsDic[key]: continue
            filterNew= {"type":"AssetFilter",
                      "config": argsDic[key]
                      }

        elif key=='gsd':
            if not argsDic[key]: continue
            filterNew= {"type": "RangeFilter",
                        "field_name": "gsd",
                        "config": {"lte": argsDic[key]}
                        }
        
        elif key=='sunElevation':
            if not argsDic[key]: continue
            filterNew= {"type": "RangeFilter",
                      "field_name": "sun_elevation",
                      "config": { "gte": argsDic[key] }
                    }

        else:
            SubLogger('CRITICAL', 'Unknown key %s'% key)

        filterOut['filter']['config'].append(filterNew)

    return filterOut

def PostRequest(sessionCur, jsonFilter):
    '''
    Post the request using Python web tools. The Search URL is hard coded
    into the __init__ function
    
    jsonFilter (json obj): full filter object
    
    out:
        jsonResult (json obj): features part of the response
        OR
        error (int): {1: 'Abort request', 2: 'Empty response'}
    '''
    objSearchResult = sessionCur.post(urlSearch,
                                json=jsonFilter)
     
    if not objSearchResult.status_code==200: SubLogger('CRITICAL', 'Aborted request\n'+json.dumps(objSearchResult.json(), indent=2))
        
    searchResult=objSearchResult.json()
    
    # How to Paginate:
    # 1) Request a page of search results
    # 2) do something with the page of results
    # 3) if there is more data, recurse and call this method on the next page.
    searchId= searchResult["id"]
    urlPage = os.path.join(urlSearch, searchId, "results?_page_size=%i"% pageSize)
    lstFeat=[]
    i=0
    while urlPage:
        i+=1
        print('\rScene collection: %i %s'% (len(lstFeat),'.'*(i%4)+' '*(3-(i%4))), end='')
        sys.stdout.flush()
        objPageResult = sessionCur.get(urlPage)
        pageResult=objPageResult.json()
        lstFeat+= pageResult['features']
        urlPage = pageResult["_links"].get("_next")

    print()
    if not lstFeat: SubLogger('CRITICAL', 'Empty response')
    return lstFeat

#=======================================================================
#main
#-----------------------------------------------------------------------
if __name__ == "__main__":
    print('\nFunctions and classes available in %s:'% __title__)
    print([i for i in dir() if not '__' in i])
        
