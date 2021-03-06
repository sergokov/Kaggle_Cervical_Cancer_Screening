#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'ar'

import os
import sys
import matplotlib.pyplot as plt
import pandas as pd
import time
import glob
import skimage.io as skio

if __name__ == '__main__':
    # fidxTrn = '/home/ar/@Kaggle/01_Intel_&_MobileODT_Cervical_Cancer_Screening/data/train-x512-processed-stage2/01-data-512x512/idx.txt-train.txt'
    fidxTrn = '/home/ar/@Kaggle/01_Intel_&_MobileODT_Cervical_Cancer_Screening/data_additional/01_train_add-x512-original-bordered_Results/idx.txt-train.txt'
    wdir = os.path.dirname(fidxTrn)
    # pathModelVal = '{0}/model_fcn_CHANNEL_vsl_v1.h5'.format(wdir)
    # pathModelValAcc = '{0}/model_fcn_CHANNEL_acc_v1.h5'.format(wdir)
    # pathModelLatest = '{0}/model_fcn_CHANNEL_latest_v1.h5'.format(wdir)
    # pathLog = '%s-log.csv' % pathModelVal
    #
    pathModelPrefix = '{0}/model_fcn_CHANNEL_EXT1'.format(wdir)
    pathModelValLoss = '{0}_valLoss_v1.h5'.format(pathModelPrefix)
    pathModelValAcc = '{0}_valAcc_v1.h5'.format(pathModelPrefix)
    pathModelLatest = '{0}_Latest_v1.h5'.format(pathModelPrefix)
    pathLog = '%s-log.csv' % pathModelValLoss
    #
    flog   = pathLog
    if os.path.isfile(flog):
        # data = pd.read_csv(flog, header=None).as_matrix()
        cnt = 0
        while True:
            data = pd.read_csv(flog)
            # dataIter = data['iter'].as_matrix()
            dataLossTrn = data['loss'].as_matrix()
            dataLossVal = data['val_loss'].as_matrix()
            dataAccTrn = data['acc'].as_matrix()
            dataAccVal = data['val_acc'].as_matrix()
            plt.clf()
            plt.subplot(1, 2, 1)
            plt.plot(dataLossTrn)
            plt.plot(dataLossVal)
            plt.grid(True)
            plt.legend(['loss-train', 'loss-validation'], loc='best')
            plt.subplot(1, 2, 2)
            plt.plot(dataAccTrn)
            plt.plot(dataAccVal)
            plt.grid(True)
            plt.legend(['acc-train', 'acc-validation'], loc='best')
            #
            plt.show(block=False)
            plt.pause(5)
            print (':: update: [{0}]'.format(cnt))
            cnt += 1
    else:
        print ('*** WARNING *** cant find log-file [{0}]'.format(flog))