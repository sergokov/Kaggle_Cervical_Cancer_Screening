#!/bin/bash

finp="idx.txt"
finpShuf="${finp}-shuf.txt"

foutTrain="${finp}-train.txt"
foutVal="${finp}-val.txt"

strHeader=`head -n1 ${finp}`

#############################
##cat $finp | grep -v 'path' | shuf | head -n 2000 > $finpShuf
cat $finp | grep -v 'path' | shuf > $finpShuf
numFn=`cat $finpShuf | wc -l`
pVal=20

((numVal=numFn*pVal/100))
((numTrain=numFn-numVal))

echo "train/val/tot = ${numTrain}/${numVal}/${numFn}"

#############################
echo "${strHeader}" > $foutTrain
##:> $foutTrain
cat $finpShuf | head -n $numTrain >> $foutTrain

echo "${strHeader}" > $foutVal
##:> $foutVal
cat $finpShuf | tail -n $numVal   >> $foutVal
