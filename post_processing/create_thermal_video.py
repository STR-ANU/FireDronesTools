#!/usr/bin/env python3

import argparse

parser = argparse.ArgumentParser(description='Create thermal video')
parser.add_argument('dir', default=None, help='thermal directory')
parser.add_argument('output', default=None, help='output video')
parser.add_argument('--fps', type=int, default=1, help='frame rate')
parser.add_argument('--temp-min', type=float, default=20, help='min temperature')
parser.add_argument('--temp-max', type=float, default=150, help='max temperature')
args = parser.parse_args()

import os
import numpy as np
from moviepy.editor import ImageClip, concatenate_videoclips
from datetime import datetime
import matplotlib.pyplot as plt

width = 640
height = 512

C_TO_KELVIN = 273.15

# Directory containing the images
image_dir = args.dir

# Get all image files and sort them by modification time
images = sorted(os.listdir(image_dir), key=lambda img: os.path.getmtime(os.path.join(image_dir, img)))

# List to hold the individual image clips
clips = []

def load_thermal_to_temperatures(fname):
    fname = os.path.join(image_dir, fname)
    a = np.fromfile(fname, dtype='>u2')
    if len(a) != width * height:
        return None

    # get in C
    a = (a / 64.0) - C_TO_KELVIN

    return a

def find_temp_range(images):
    tmin = None
    tmax = None
    for img in images:
        a = load_thermal_to_temperatures(img)
        t1 = a.min()
        t2 = a.max()
        if tmin is None or tmin > t1:
            tmin = t1
        if tmax is None or tmax < t2:
            tmax = t2
    return (tmin, tmax)

def load_thermal(fname, tmin, tmax):
    a = load_thermal_to_temperatures(fname)

    # clip to the specified range
    a = np.clip(a, tmin, tmax)

    # convert to 0 to 255 in range tmin to tmax
    a = (a - tmin) * 255.0 / (tmax - tmin)

    # convert to uint8 greyscale as 640x512 image
    a = a.astype(np.uint8)
    a = a.reshape(height, width)
    return a

def load_thermal_colormap(fname, tmin, tmax):
    a = load_thermal_to_temperatures(fname)

    # clip to the specified range
    a = np.clip(a, tmin, tmax)

    # convert to 0 to 1 range tmin to tmax
    a = (a - tmin) / float(tmax - tmin)
    a = a.reshape(height, width)

    rgb = plt.cm.hot(a)
    rgb_image = (rgb[..., :3] * 255).astype(np.uint8)

    return rgb_image

previous_mod_time = None
done = 0

print("Finding temperature range for %u images" % len(images))
(min_temp, max_temp) = find_temp_range(images)

min_temp = max(min_temp, args.temp_min)
max_temp = min(max_temp, args.temp_max)

for image in images:
    image_path = os.path.join(image_dir, image)
    mod_time = os.path.getmtime(image_path)
    
    if previous_mod_time is not None:
        # Calculate the duration each image should be displayed to match the time between frames
        duration = mod_time - previous_mod_time
    else:
        duration = 1  # default duration for the first image

    print("Loading %s (%u/%u) for %.3fs" % (image_path, done, len(images), duration))
    done += 1
    rgb = load_thermal_colormap(image_path, min_temp, max_temp)

    clip = ImageClip(rgb, duration=duration)
    clips.append(clip)

    previous_mod_time = mod_time

print("Temp range: %.1fC to %.1fC" % (min_temp, max_temp))

# Concatenate all the image clips into one video
video = concatenate_videoclips(clips, method="compose")

# Output the video file
video.write_videofile(args.output, fps=args.fps)
