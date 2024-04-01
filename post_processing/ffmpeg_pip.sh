#!/bin/bash

[ $# -eq 4 ] || {
    echo "Usage: RGB THERMAL FLIGHT OUTPUT"
    exit 1
}


RGB="$1"
THERMAL="$2" # top left PIP
FLIGHT="$3" # top right PIP
OUTPUT="$4"

ffmpeg -i $RGB -i $THERMAL -i $FLIGHT -filter_complex "[2:v]format=argb,geq=r='r(X,Y)':a='0.8*alpha(X,Y)'[al];
[0:v][1:v]overlay=0:0[o1];
[o1][al]overlay=main_w-overlay_w:0" $OUTPUT
