#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'ar'

import cv2
import time
import shutil
import os
import sys
import gc
import math
from scipy import ndimage
import matplotlib.pyplot as plt
import skimage.io as skio
import skimage.transform as sktf
import skimage.morphology as skmorph
import skimage.exposure as skexp
import numpy as np
import keras
from keras.layers import Conv2D, UpSampling2D, \
    Flatten, Activation, Reshape, MaxPooling2D, Input, Dense, merge, Dropout, SpatialDropout2D, BatchNormalization
from keras.models import Model
import keras.losses
import keras.callbacks as kall
import pandas as pd
import multiprocessing as mp
import multiprocessing.pool
import threading

from keras.preprocessing.image import ImageDataGenerator
from keras.utils.vis_utils import plot_model as kplot
from keras.utils import np_utils
from keras.utils.vis_utils import plot_model
import keras.applications as kapp

#####################################################
def buildModelCNN_Classification_V1(inpShape=(256, 256, 3),
                                    numCls=3, kernelSize=3, numFlt = 16,
                                    numConv=2, numSubsampling=5, ppadding='valid', numHidden=None):
    fsiz = (kernelSize, kernelSize)
    psiz = (2, 2)
    dataInput = Input(shape=inpShape)
    #
    x = dataInput
    # (1) Conv-layers
    for cc in range(numSubsampling):
        if cc==0:
            tfsiz = (5,5)
        else:
            tfsiz = fsiz
        for ii in range(numConv):
            x = Conv2D(filters=numFlt * (2 **cc), kernel_size=tfsiz,
                       activation='relu',
                       padding=ppadding,
                       kernel_regularizer=keras.regularizers.l2(0.01))(x)
            # x = BatchNormalization()(x)
            # x = Activation('relu')(x)
        x = MaxPooling2D(pool_size=psiz, padding=ppadding)(x)
    # (2) flatening
    x = Flatten()(x)
    # x = Dropout(rate=0.2)(x)
    # (3) hidden dense-layers
    if numHidden is not None:
        if isinstance(numHidden, list):
            for numUnits in numHidden:
                x = Dense(units=numUnits, activation='relu', kernel_regularizer=keras.regularizers.l2(0.01))(x)

        else:
            x = Dense(units=numHidden, activation='relu',
                      # W_regularizer=keras.regularizers.l2(0.02)
                      )(x)
        # x = Dropout(rate=0.2)(x)
    # (4) multiclass-output
    x = Dense(units=numCls, activation='softmax')(x)
    retModel = Model(inputs=dataInput, outputs=x)
    return retModel

#####################################################
def preproc_image(pimg, prnd=1):
    ndim = pimg.ndim
    if prnd is None:
        trnd = np.random.randint(2)
    else:
        trnd = prnd
    timg = pimg[:, :, :3].copy()
    ret = pimg.copy()
    if trnd == 0:
        timg = skexp.equalize_hist(timg.astype(np.uint8)).astype(np.float32) * 255.
    elif trnd == 1:
        vrnd = getRandomInRange((0.3, 2.5))
        timg = (255. * skexp.adjust_gamma(timg.astype(np.float32) / 255., vrnd)).astype(np.uint8)
    elif trnd > 1:
        rndVals = 2.0 * np.random.rand(ndim,2) - 1.0
        rndVals[:, 0] *= 30
        rndVals[:, 1] = 1.0 + 0.2 * rndVals[:, 1]
        for ii in range(ndim):
            timg[:,:,ii] = rndVals[ii,0] + rndVals[ii,1] * timg[:,:,ii]
    timg[timg < 0] = 0
    timg[timg > 255] = 255
    ret[:, :,:3] = timg.copy()
    return ret

#####################################################
def calcDistArr2Point(parr2d, pp2d):
    sizArr = parr2d.shape[0]
    ret = np.linalg.norm(parr2d - np.tile(pp2d, (sizArr,1)), axis=1)
    return ret

def buildImageWithRotScaleAroundCenter(pimg, pcnt, pangDec, pscale, pcropSize, isDebug=False, pborderMode = cv2.BORDER_REPLICATE):
    # (1) precalc parameters
    angRad = (np.pi / 180.) * pangDec
    cosa = np.cos(angRad)
    sina = np.sin(angRad)
    # (2) prepare separate affine transformation matrices
    matShiftB = np.array([[1., 0., -pcnt[0]], [0., 1., -pcnt[1]], [0., 0., 1.]])
    matRot = np.array([[cosa, sina, 0.], [-sina, cosa, 0.], [0., 0., 1.]])
    matShiftF = np.array([[1., 0., +pcnt[0]], [0., 1., +pcnt[1]], [0., 0., 1.]])
    matScale = np.array([[pscale, 0., 0.], [0., pscale, 0.], [0., 0., 1.]])
    matShiftCrop = np.array([[1., 0., pcropSize[0] / 2.], [0., 1., pcropSize[1] / 2.], [0., 0., 1.]])
    # matTotal_OCV = matShiftF.dot(matRot.dot(matScale.dot(matShiftB)))
    # (3) build total-matrix
    matTotal = matShiftCrop.dot(matRot.dot(matScale.dot(matShiftB)))
    if isDebug:
        print ('(1) mat-shift-backward = \n{0}'.format(matShiftB))
        print ('(2) mat-scale = \n{0}'.format(matScale))
        print ('(3) mat-rot = \n{0}'.format(matRot))
        print ('(4) mat-shift-forward = \n{0}'.format(matShiftF))
        print ('(5) mat-shift-crop = \n{0}'.format(matShiftCrop))
        print ('---\n(*) mat-total = \n{0}'.format(matTotal))
    # (4) warp image with total affine-transform
    imgRet = cv2.warpAffine(pimg, matTotal[:2, :], pcropSize, borderMode=pborderMode)
    return imgRet

def prepareCervixInfo(pimg, pRelCervixSize = 0.4, isDebug = False):
    meanImgSize = 0.5 * np.mean(pimg.shape[:2])
    # (1) prepare masks
    tmsk_crv = (pimg[:,:,3] > 100)
    # (2) find channel cover-circle and center of this corcle
    PTS_Cervix_RC = np.array(np.where(tmsk_crv)).transpose()
    (PC_Cervix_RC, R_Cervix) = cv2.minEnclosingCircle(PTS_Cervix_RC)
    Dist_Cervix2CenterCervix = calcDistArr2Point(PTS_Cervix_RC, PC_Cervix_RC)
    #
    R_Cervix_Good = pRelCervixSize * R_Cervix
    if R_Cervix_Good > meanImgSize:
        R_Cervix_Good = meanImgSize
    PTS_Cervix_Good_RC = PTS_Cervix_RC[Dist_Cervix2CenterCervix < R_Cervix_Good, :]
    # (3) Channel info
    ret = {
        'R_Cervix': R_Cervix,
        'R_Cervix_Good': R_Cervix_Good,
        'PC_Cervix_RC': PC_Cervix_RC,
        'PTS_Cervix_Good': PTS_Cervix_Good_RC
    }
    if isDebug:
        tmsk = pimg[:, :, 3]
        timg = pimg[:, :, :3]
        retSize = 256
        newScale =  0.9
        timg_crop = buildImageWithRotScaleAroundCenter(timg, PC_Cervix_RC[::-1], 15., newScale, (retSize, retSize), isDebug=False)
        #
        plt.subplot(1, 3, 1)
        plt.imshow(tmsk)
        plt.gcf().gca().add_artist(plt.Circle(PC_Cervix_RC[::-1], R_Cervix, edgecolor='r', fill=False))
        plt.gcf().gca().add_artist(plt.Circle(PC_Cervix_RC[::-1], R_Cervix_Good, edgecolor='g', fill=False))
        plt.plot(PTS_Cervix_Good_RC[:, 1], PTS_Cervix_Good_RC[:, 0], 'y.')
        plt.subplot(1, 3, 2)
        plt.imshow(timg)
        plt.gcf().gca().add_artist(plt.Circle(PC_Cervix_RC[::-1], R_Cervix, edgecolor='r', fill=False))
        plt.gcf().gca().add_artist(plt.Circle(PC_Cervix_RC[::-1], R_Cervix_Good, edgecolor='g', fill=False))
        plt.subplot(1, 3, 3)
        plt.imshow(timg_crop)
        plt.show()
    return ret

def buildImgInfoList(dataImg):
    numImg = dataImg.shape[0]
    print (":: Prepare image info ({0})".format(dataImg.shape))
    ret = []
    for ii in range(numImg):
        timg = dataImg[ii]
        tinfo = prepareCervixInfo(timg)
        ret.append(tinfo)
        if (ii%10)==0:
            print ('[{0}/{1}]'.format(ii, numImg))
    return ret

#####################################################
def readDataImagesCls(pidx, wdir=None, maxNum=None):
    if wdir is None:
        wdir = os.path.dirname(pidx)
    tdata = pd.read_csv(pidx)
    if maxNum is not None:
        numData = len(tdata)
        if maxNum>numData:
            maxNum = numData
        tdata = tdata[:maxNum]
    #
    dataY = tdata['type'].as_matrix() - 1
    tnumCls = len(np.unique(dataY))
    dataY   = np_utils.to_categorical(dataY, tnumCls)
    lstpath = tdata['path'].as_matrix()
    lstpath = [os.path.join(wdir, xx) for xx in lstpath]
    dataPaths = lstpath
    numPath = len(lstpath)
    dataX = None
    print (':: read images into memory...')
    for ipath, path in enumerate(lstpath):
        timg = skio.imread(path)
        if dataX is None:
            dataX = np.zeros([numPath] + list(timg.shape), dtype=np.uint8)
        if (ipath%20)==0:
            print ('\t[{0}/{1}]'.format(ipath, numPath))
        dataX[ipath] = timg
    return dataX, dataY, dataPaths

#####################################################
def getRandomInRange(vrange, pnum=None):
    vmin,vmax = vrange
    if pnum is None:
        trnd = np.random.rand()
    else:
        trnd = np.random.rand(pnum)
    ret = vmin + (vmax-vmin)*trnd
    return ret

def preprocImgForInference(pimg, pinfo, angleRange=(-16.,+16.), batchSize = 16, imsize=256, isRandomize=False):
    sizeCrop = (imsize, imsize)
    dataX = np.zeros((batchSize, imsize, imsize, 3))
    timg = pimg[:, :, :3]
    CNT_chn_rc = pinfo['cnt_chn']
    PTS_chn_rc = pinfo['rc_chn']
    R_chn = pinfo['r_chn_good']
    R_crv = pinfo['r_crv']
    for ii in range(batchSize):
        # R_crop = R_crv
        if R_chn < 10:
            R_chn = 10.
        if isRandomize:
            R_crop = getRandomInRange([0.6 * R_crv, 1.2 * R_crv])
        else:
            R_crop = R_crv
        if PTS_chn_rc.shape[0]>0:
            rndChnPos = np.random.randint(PTS_chn_rc.shape[0])
            P_Center_XY = PTS_chn_rc[rndChnPos][::-1]
        else:
            P_Center_XY = CNT_chn_rc
        #
        if isRandomize:
            angleCrop = getRandomInRange(angleRange)
        else:
            angleCrop = 0.
        scaleCrop2 = (float(imsize) / (2. * R_crop + 2.))
        #
        timgCrop = buildImageWithRotScaleAroundCenter(timg, P_Center_XY, angleCrop, scaleCrop2, sizeCrop, isDebug=False)
        timgCrop = (timgCrop.astype(np.float) / 127.5 - 1.0)
        dataX[ii] = timgCrop
    return dataX

#####################################################
class BatchGenerator:
    def __init__(self, dataImg, dataCls, dataImgInfo, imsize = 256,
                               isRandomize=True,
                               angleRange=(-16.,+16.),
                               scaleRange=(0.9, 1.3), fun_random_val=None):
        self.dataImg = dataImg
        self.dataCls = dataCls
        self.dataImgInfo = dataImgInfo
        self.imsize = imsize
        self.isRandomize = isRandomize
        self.angleRange = angleRange
        self.scaleRange = scaleRange
        self.fun_random_val = fun_random_val
    def build_batch(self, batchSize=64):
        numImg = self.dataImg.shape[0]
        sizeCrop = (self.imsize, self.imsize)
        rndIdx = np.random.randint(0, numImg, batchSize)
        dataX = np.zeros((batchSize, self.imsize, self.imsize, 3))
        dataY = np.zeros((batchSize, self.dataCls.shape[-1]))
        #
        rndAngles = getRandomInRange(self.angleRange, pnum=batchSize)
        rndScales = getRandomInRange(self.scaleRange, pnum=batchSize)
        #
        for ii, idx in enumerate(rndIdx):
            timg = self.dataImg[idx][:, :, :3]
            tinf = self.dataImgInfo[idx]
            PTS_Cervix_Good = tinf['PTS_Cervix_Good']
            # PC_Cervix_RC  = tinf['PC_Cervix_RC']
            numPTS_Cervix = PTS_Cervix_Good.shape[0]
            rnd_PTS_Certvix_Idx = np.random.randint(numPTS_Cervix)
            rnd_PC_Cervix_XY = PTS_Cervix_Good[rnd_PTS_Certvix_Idx, :][::-1]
            if self.isRandomize:
                rnd_Angle = rndAngles[ii]
                rnd_Scale = rndScales[ii]
            else:
                rnd_Angle = 0.
                rnd_Scale = 1.
            timgCrop = buildImageWithRotScaleAroundCenter(timg, rnd_PC_Cervix_XY, rnd_Angle, rnd_Scale, sizeCrop,
                                                          isDebug=False)
            if self.fun_random_val is not None:
                timgCrop = self.fun_random_val(timgCrop)
            timgCrop = (timgCrop.astype(np.float) / 127.5 - 1.0)
            dataX[ii] = timgCrop
            dataY[ii] = self.dataCls[idx]
        return (dataX, dataY)

def train_generator_CLS_Cervix(dataImg, dataCls, dataImgInfo,
                               batchSize=64,
                               imsize = 256,
                               isRandomize=True,
                               angleRange=(-16.,+16.),
                               scaleRange=(0.9, 1.2),
                               fun_random_val=None,
                               numTrainRepeatsPerEpoch = 8,
                               numThreads = 3):
    batchGenerator = BatchGenerator(
                                dataImg=dataImg,
                                dataCls=dataCls,
                                dataImgInfo=dataImgInfo,
                                imsize = imsize,
                                isRandomize=isRandomize,
                                angleRange=angleRange,
                                scaleRange=scaleRange,
                                fun_random_val=fun_random_val)
    numSamples = dataImg.shape[0]
    sizeDataPool = numSamples
    itersPerEpoch = sizeDataPool/batchSize
    #
    threadedGenerator = ThreadedDataGeneratorV2(nproc=numThreads)
    threadedGenerator.setDataGenerator(batchGenerator)
    threadedGenerator.startBatchGeneration(sizeDataPool)
    while True:
        if not threadedGenerator.isIdle():
            threadedGenerator.waitAll()
        dataPoolX, dataPoolY = threadedGenerator.getGeneratedData()
        rndIdx = list(range(dataPoolX.shape[0]))
        if threadedGenerator.isIdle():
            threadedGenerator.startBatchGeneration(sizeDataPool)
        for repEpoch in range(numTrainRepeatsPerEpoch):
            # print ('\t---[{0}]---'.format(repEpoch))
            for iiter in range(itersPerEpoch):
                tidx = np.random.permutation(rndIdx)[:batchSize]
                dataX = dataPoolX[tidx]
                dataY = dataPoolY[tidx]
                yield (dataX, dataY)

#####################################################
class ThreadedDataGeneratorV2(object):
    def __init__(self, nproc=8, isThreadManager=True):
        self._nproc = nproc
        if isThreadManager:
            self._pool = mp.pool.ThreadPool(processes=self._nproc)
        else:
            self._pool = mp.Pool(processes=self._nproc)
        self._batchGenerator = None
        self._cleanData()
        self._genCounter = 0
    def _cleanData(self):
        self._poolStateMerge  = None
        self._poolResultMerge = None
        # gc.collect()
    def isIdle(self):
        if (self._poolStateMerge is not None) and self._poolStateMerge.isAlive():
            return False
        return True
    def setDataGenerator(self, batchGenerator):
        self._batchGenerator = batchGenerator
    def setDataGenerator_OLD(self, dataImg, dataCls, dataImgInfo, imsize = 256,
                               isRandomize=True,
                               angleRange=(-16.,+16.),
                               scaleRange=(0.9, 1.3), fun_random_val=None):
        self._batchGenerator = BatchGenerator(
                    dataImg=dataImg,
                    dataCls=dataCls,
                    dataImgInfo=dataImgInfo,
                    imsize=imsize,
                    isRandomize=isRandomize,
                    angleRange=angleRange,
                    scaleRange=scaleRange,
                    fun_random_val=fun_random_val)
    def _runner_batch(self, pdata):
        bidx = pdata[0]
        print (':: Batching #{0}'.format(bidx))
        bsiz = pdata[1]
        # dataXY = self._batchGenerator.build_batch(bsiz)
        return self._batchGenerator.build_batch(bsiz)
    def _runner_merge(self, pdata):
        # print ('--------- START MERGE ----------')
        t0 = time.time()
        batchSize = pdata[0]
        tpool = mp.pool.ThreadPool(processes=self._nproc)
        # list_batches = self._pool.map(self._runner_batch, [(xx, batchSize) for xx in range(self._nproc)])
        list_batches = tpool.map(self._runner_batch, [(xx, batchSize) for xx in range(self._nproc)])
        numData = len(list_batches[0])
        self._poolResultMerge = [None] * numData
        for ii in range(numData):
            # dataX = np.concatenate([xx[0] for xx in list_batches])
            self._poolResultMerge[ii] = np.concatenate([xx[ii] for xx in list_batches])
        # dataY = np.concatenate([xx[1] for xx in list_batches])
        # Freeing memory...
        tpool.close()
        dt = time.time() - t0
        # print ('--------- FINISH MERGE ----------')
        print ('\tBatched data #{0} is generated: {1:0.3f} (s)'.format(self._genCounter, dt))
        self._genCounter += 1
        # self._poolResultMerge = (dataX, dataY)
    def startBatchGeneration(self, batchSize = 1024):
        bsiz = batchSize/self._nproc
        if self.isIdle():
            self._cleanData()
            self._poolStateMerge = threading.Thread(target=self._runner_merge, args=[(bsiz,)])
            self._poolStateMerge.start()
        else:
            print ('** WARNIG Task Pool is runnig, canceling batchGeneration...')
    def getGeneratedData(self, isClean=True):
        if not self.isIdle():
            return None
        else:
            dataXY = self._poolResultMerge
            if isClean:
                self._cleanData()
            return dataXY
    def toString(self):
        return '::ThreadedDataGenerator isIdle: [{0}], generator=[{1}], #generation = {2}'\
                .format(self.isIdle(), self._batchGenerator, self._genCounter)
    def __str__(self):
        return self.toString()
    def __repr__(self):
        return self.toString()
    def waitAll(self, dt = 0):
        if not self.isIdle():
            if dt>0:
                time.sleep(dt)
            self._poolStateMerge.join()



#####################################################
if __name__ == '__main__':
    numClasses = 3
    batchSize = 128
    numEpochs = 500
    imgSize = 256
    imgShape = (imgSize, imgSize, 3)
    # (1) Setup Tran/Validation data
    fidxTrn = '/home/ar/@Kaggle/01_Intel_&_MobileODT_Cervical_Cancer_Screening/data_additional/01_train_add-x512-original-bordered_Results/idx.txt_fold1_trn.csv'
    fidxVal = '/home/ar/@Kaggle/01_Intel_&_MobileODT_Cervical_Cancer_Screening/data_additional/01_train_add-x512-original-bordered_Results/idx.txt_fold1_val.csv'
    if len(sys.argv)>2:
        fidxTrn = sys.argv[1]
        fidxVal = sys.argv[2]
    else:
        print ('*** Usage *** : {0} [/path/to/train-idx.csv] [/path/to/validation-idx.csv]'.format(os.path.basename(sys.argv[0])))
    if not os.path.isfile(fidxTrn):
        raise Exception('!! Cant find train-index: [{0}]'.format(fidxTrn))
    if not os.path.isfile(fidxVal):
        raise Exception('!! Cant find train-index: [{0}]'.format(fidxVal))
    #
    wdirTrn = os.path.dirname(fidxTrn)
    # (2) Input/Output models
    pathModelPrefix = '{0}_model_CNNCLS_EXT2'.format(fidxTrn)
    pathModelValLoss = '{0}_valLoss_v1.h5'.format(pathModelPrefix)
    pathModelValAcc = '{0}_valAcc_v1.h5'.format(pathModelPrefix)
    pathModelLatest = '{0}_Latest_v1.h5'.format(pathModelPrefix)
    pathLog = '%s-log.csv' % pathModelValLoss
    # (3) Continue training from checkpoint Model (if exists)
    pathModelRestart = pathModelValLoss
    if not os.path.isfile(pathModelRestart):
        print (':: Trained model not found: build new model...')
        # model = kapp.ResNet50(
        #             include_top=True,
        #             weights=None, #'imagenet',
        #             input_shape=imgShape,
        #             classes=numClasses)
        model = buildModelCNN_Classification_V1(inpShape=imgShape, numConv=2, ppadding='same', numHidden=128, numSubsampling=6)
        model.compile(optimizer='adam',
                      loss='categorical_crossentropy',
                      metrics=['accuracy'])
    else:
        print ('!!! WARNING !!! Found trained model, loading... [{0}]'.format(pathModelRestart))
        pref = time.strftime('%Y.%m.%d-%H.%M.%S')
        pathModelValBk = '%s-%s.bk' % (pathModelValLoss, pref)
        pathModelValAccBk = '%s-%s.bk' % (pathModelValAcc, pref)
        pathModelLatestBk = '%s-%s.bk' % (pathModelLatest, pref)
        shutil.copy(pathModelValLoss, pathModelValBk)
        shutil.copy(pathModelValAcc, pathModelValAccBk)
        # shutil.copy(pathModelLatest, pathModelLatestBk)
        model = keras.models.load_model(pathModelRestart)
    model.summary()
    # (4) Preload data
    maxNum = None
    trnX, trnY, _ = readDataImagesCls(fidxTrn, maxNum=maxNum)
    valX, valY, _ = readDataImagesCls(fidxVal, maxNum=maxNum)
    trnInfo = buildImgInfoList(trnX)
    valInfo = buildImgInfoList(valX)
    # (5) prepare image generator
    numTrn = trnX.shape[0]
    numVal = valX.shape[0]
    numIterPerEpochTrn = 1 * numTrn / batchSize
    numIterPerEpochVal = 1 * numVal / batchSize
    if numIterPerEpochTrn<1:
        numIterPerEpochTrn = 1
    if numIterPerEpochVal < 1:
        numIterPerEpochVal = 1
    generatorTrn = train_generator_CLS_Cervix(dataImg=trnX,
                                              dataCls=trnY,
                                              dataImgInfo=trnInfo,
                                              batchSize=batchSize,
                                              isRandomize=True,
                                              imsize=imgSize,
                                              fun_random_val=preproc_image,
                                              numTrainRepeatsPerEpoch = 8,
                                              numThreads=3)
    generatorVal = train_generator_CLS_Cervix(dataImg=valX,
                                              dataCls=valY,
                                              dataImgInfo=valInfo,
                                              batchSize=batchSize,
                                              isRandomize=True,
                                              imsize=imgSize,
                                              fun_random_val=None,
                                              numTrainRepeatsPerEpoch = 8,
                                              numThreads=2)
    # (6) Train model
    model.fit_generator(
        generator=generatorTrn,
        steps_per_epoch=numIterPerEpochTrn,
        epochs=numEpochs,
        validation_data=generatorVal,
        validation_steps=numIterPerEpochVal,
        callbacks=[
            kall.ModelCheckpoint(pathModelValLoss, verbose=True, save_best_only=True, monitor='val_loss'),
            kall.ModelCheckpoint(pathModelValAcc,  verbose=True, save_best_only=True, monitor='val_acc'),
            # kall.ModelCheckpoint(pathModelLatest,  verbose=True, save_best_only=False),
            kall.CSVLogger(pathLog, append=True)
        ])
