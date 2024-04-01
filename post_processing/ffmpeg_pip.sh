#!/bin/bash

[ $# -eq 4 ] || {
    echo "Usage: RGB THERMAL FLIGHT OUTPUT"
    exit 1
}
	       

RGB="$1"
THERMAL="$2" # top left PIP
FLIGHT="$3" # top right PIP
OUTPUT="$4"

ffmpeg -i $RGB -i $THERMAL -i $FLIGHT -filter_complex 'overlay=0:0,overlay=main_w-overlay_w:0' $OUTPUT
