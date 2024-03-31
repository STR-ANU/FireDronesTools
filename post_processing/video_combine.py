#!/usr/bin/env python3

import argparse
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip

parser = argparse.ArgumentParser(description='Combine video files')
parser.add_argument('rgb', default=None, help='RGB video')
parser.add_argument('thermal', default=None, help='thermal video')
parser.add_argument('output', default=None, help='output video')

args = parser.parse_args()

base_rgb = VideoFileClip(args.rgb)
thermal = VideoFileClip(args.thermal)

video = CompositeVideoClip([base_rgb,
                           thermal.set_position((0,0))])

video.write_videofile(args.output)
