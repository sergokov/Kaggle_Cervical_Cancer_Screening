#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'ar'

import os
import sys
import pandas as pd
import numpy as np

###########################
def usage(pargv):
    print ('Usage: {0} {{/path/to/data-ground-truth-idx}} {{/path/to/data-evaluated-idx}}'.format(os.path.basename(pargv[0])))

###########################
if __name__ == '__main__':
    print ('FUCK')
    if len(sys.argv)<3:
        usage(sys.argv)
        sys.exit(0)
    pathIdxGT = sys.argv[1]
    pathIdxEV = sys.argv[2]
    if not os.path.isfile(pathIdxGT):
        raise Exception('!!! Cant find Ground-Truth index-file: [{0}]'.format(pathIdxGT))
    if not os.path.isfile(pathIdxEV):
        raise Exception('!!! Cant find Evaluated index-file: [{0}]'.format(pathIdxEV))
    #
    dataGT = pd.read_csv(pathIdxGT)[['Type_1', 'Type_2', 'Type_3']].as_matrix()
    dataEV = pd.read_csv(pathIdxEV)[['Type_1', 'Type_2', 'Type_3']].as_matrix()
    numGT = len(dataGT)
    numEV = len(dataEV)
    print ("""
Input parameters:
---------------------------
    ground-truth:   {0}
    evaluated:      {1}
    ---
    #Samples: GT/EV =  {2}/{3}
---------------------------    
    """.format(pathIdxGT, pathIdxEV, numGT, numEV))
    if numGT != numEV:
        raise Exception('!!! Invalid number of Samples in GroundTruth or in Evaluated data: {0} != {1}'.format(numGT, numEV))
    #
    print ('-')
    idxGT = np.argmax(dataGT, axis=1)
    idxEV = np.argmax(dataEV, axis=1)
    retACC = np.mean(idxGT==idxEV)
    retLOSS = np.mean(-np.log(dataEV[dataGT>0.9] + 0.00001))
    print (':: Results: ACC = {0:0.5f}, LOSS = {1:0.5f} for eval [{2}]/[{3}]'
           .format(retACC, retLOSS, os.path.basename(pathIdxGT), os.path.basename(pathIdxEV)))
