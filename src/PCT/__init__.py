#!/usr/bin/env python3
# -*- coding: UTF-8 -*-'''

'''
Planet_Common Tools
'''
#-----------------------------------------------------------------------
# Hard arguments
#-----------------------------------------------------------------------
__author__='Valentin Schmitt'
__version__=1.0
__all__ =['PCTlib_product', 'lstLevel','lstAction',  'dicLevel', 'nameBucket']


lstLevel=('L0','L1A','L1B')
lstAction=('create','list','match','download')

#  Creation variables
dicLevel={'L1A': ('L1A','{}_1A_Analytic_DN.tif','Multistripe_L1A_DN')}
nameFeat='{}.cmo'
nameBucket='valintern_dsmps_{}_{}'



# Job system variables
nameJobFile='{}_BucketNBatch-{}.txt'