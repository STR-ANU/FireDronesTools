#!/usr/bin/env python3

import argparse
import subprocess
import tempfile
import os

def concatenate_videos(video_files, output_file):
    # Use NamedTemporaryFile to create a temporary file
    flist="flist.txt"
    f = open(flist,'w')
    for video in video_files:
        f.write(f"file '{video}'\n")
    f.close()

    # Call ffmpeg to concatenate the videos using the temporary file list
    subprocess.run([
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', flist,
        '-c', 'copy',
        output_file
    ])
    os.unlink(flist)


parser = argparse.ArgumentParser(description="Concatenate multiple MP4 videos into a single video file using ffmpeg.")
parser.add_argument('videos', nargs='+', help='List of video files to concatenate')
parser.add_argument('-o', '--output', default='output.mp4', help='Output video file name')

# Parse command line arguments
args = parser.parse_args()

# Concatenate the videos
concatenate_videos(args.videos, args.output)
