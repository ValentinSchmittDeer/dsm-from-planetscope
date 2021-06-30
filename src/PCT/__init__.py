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
__all__ =['PCTlib_product',   'prodLevel', 'nameBucket']

#  Creation variables
prodLevel='L1A'
nameBucket='dsm_from_ps_{}_{}'


# Job system variables
basicScp='''plj_batch.py -c pl --make-batch #Create batch
ehco batch ID

# Add scene ID
for i in $(cat {})
    do 
        plj_run.py -c pl --quota-ram-mb=7200 --timeout=7200 --priority=1 --profile=spot product-processor ARGS="cmo -c pl --product=Multistripe_L1A_DN --output-storage-bucket=XXXXXX --disable-cache-read --disable-cache-write --input-bucket=flock1 --input-scene=$i --udm disabled --xml disabled" --batch=505021690
done
'''

cmdMakeBatch='plj_batch.py -c pl --make-batch xx' 
cmdStatusBatch='plj_query.py c pl --batch  {}xx'