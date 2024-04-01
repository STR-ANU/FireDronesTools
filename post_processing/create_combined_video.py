#!/usr/bin/env python3
'''
create a video from raw thermal, RGB video 

'''

import argparse

parser = argparse.ArgumentParser(description='Create thermal video')
parser.add_argument('rgb', default=None, help='RGB video')
parser.add_argument('thermal_dir', default=None, help='thermal directory')
parser.add_argument('SIYI_bin', default=None, help='path to SIYI bin file')
parser.add_argument('log_bin', default=None, help='path to bin log file')
parser.add_argument('output', default=None, help='output video')
parser.add_argument('--fps', type=int, default=1, help='output frame rate')
parser.add_argument('--temp-min', type=float, default=0, help='min temperature')
parser.add_argument('--temp-max', type=float, default=188, help='max temperature')
parser.add_argument('--threshold', type=float, default=80, help='color threshold')
parser.add_argument('--duration', type=float, default=None, help='duration in seconds')

args = parser.parse_args()

import os
import numpy as np
from moviepy.editor import ImageClip, TextClip, concatenate_videoclips, VideoFileClip, CompositeVideoClip
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from progress.bar import Bar

from pymavlink import mavutil


thermal_width = 640
thermal_height = 512

C_TO_KELVIN = 273.15

def load_thermal_to_temperatures(fname):
    '''load a raw thermal file returning a temperature array in degrees C'''
    a = np.fromfile(fname, dtype='>u2')
    if len(a) != thermal_width * thermal_height:
        return None

    # get in C
    return (a / 64.0) - C_TO_KELVIN

def find_temp_range(thermal_dir):
    '''find the range of temperatures in a thermal directory'''
    tmin = None
    tmax = None
    images = sorted(os.listdir(thermal_dir), key=lambda img: os.path.getmtime(os.path.join(thermal_dir, img)))
    for img in images:
        fname = os.path.join(thermal_dir, img)
        a = load_thermal_to_temperatures(fname)
        if a is None:
            continue
        t1 = a.min()
        t2 = a.max()
        if tmin is None or tmin > t1:
            tmin = t1
        if tmax is None or tmax < t2:
            tmax = t2
    return (tmin, tmax)

def load_thermal_colormap(fname, tmin, tmax):
    a = load_thermal_to_temperatures(fname)
    if a is None:
        return None

    # clip to the specified range
    a = np.clip(a, tmin, tmax)

    # convert to 0 to 1 range tmin to tmax
    a = (a - tmin) / float(tmax - tmin)
    a = a.reshape(thermal_height, thermal_width)

    # apply colormap
    rgb = plt.cm.inferno(a)
    rgb_image = (rgb[..., :3] * 255).astype(np.uint8)

    return rgb_image

def make_thermal_video(thermal_dir, start_time, rgb_duration):
    '''make the thermal video which will be setup as PIP'''

    images = sorted(os.listdir(thermal_dir), key=lambda img: os.path.getmtime(os.path.join(thermal_dir, img)))
    done = 0


    bar = Bar('Loading raw thermal', max=len(images))

    print("Finding temperature range for %u images" % len(images))
    (min_temp, max_temp) = find_temp_range(thermal_dir)
    print("Temp range: %.1f to %.1f" % (min_temp, max_temp))

    threshold_temp = min(max_temp, args.threshold)

    min_temp = max(min_temp, args.temp_min)
    max_temp = min(max_temp, args.temp_max)
    clips = []
    t = 0.0
    first_timestamp = None

    for i in range(len(images)):
        image = images[i]
        image_path = os.path.join(thermal_dir, image)
        mod_time = os.path.getmtime(image_path)
        if mod_time < start_time:
            continue
        if mod_time > start_time+rgb_duration:
            break
        if first_timestamp is None:
            first_timestamp = mod_time
        if i < len(images)-1:
            next_mod_time = os.path.getmtime(os.path.join(thermal_dir, images[i+1]))
        else:
            next_mod_time = mod_time + 1.0
    
        duration = next_mod_time - mod_time

        rgb = load_thermal_colormap(image_path, min_temp, max_temp)
        if rgb is None:
            continue
        done += 1

        clip = ImageClip(rgb, duration=duration)
        clips.append(clip)
        t += duration
        bar.next()

    # Concatenate all the image clips into one video
    ret = concatenate_videoclips(clips, method="compose")
    ret.start_time = first_timestamp

    return ret

def make_flight_state_clips(log_bin, start_time, rgb_duration):
    '''make a video clip of flight state'''
    mlog = mavutil.mavlink_connection(log_bin)
    clips = []
    types = set(['MODE','TERR'])
    last_t = None
    first_timestamp = None
    have_types = set()
    last_txt = 'Mode: INIT'
    bar = Bar('Processing flight log', max=100)
    pct = 0
    while True:
        m = mlog.recv_match(type=types)
        if m is None:
            break
        mtype = m.get_type()
        if not mtype in have_types:
            have_types.add(mtype)
        if have_types != types:
            continue
        if m._timestamp < start_time:
            continue
        if m._timestamp > start_time+rgb_duration:
            break
        if first_timestamp is None:
            first_timestamp = m._timestamp
            last_t = first_timestamp
        if m._timestamp - last_t < 1.0:
            continue
        duration = m._timestamp - last_t
        TERR = mlog.messages.get('TERR')
        txt = f'''
Mode: {mlog.flightmode}
AltAGL: {TERR.CHeight:.2f}m
'''
        clip = TextClip(last_txt, color='red', font="Amiri-Bold", kerning = 5, fontsize=32)
        clip = clip.set_start(last_t - first_timestamp)
        clip = clip.set_duration(duration)
        clip = clip.set_position(("right", "top"))
        clip.start_time = last_t
        clips.append(clip)
        last_txt = txt
        last_t = m._timestamp
        new_pct = (mlog.offset * 100) // mlog.data_len
        if new_pct != pct:
            bar.next()
            pct = new_pct
    return clips

# get the RGB video
base_rgb = VideoFileClip(args.rgb)
base_rgb.start_time = os.path.getmtime(args.rgb) - base_rgb.duration

if args.duration is not None and base_rgb.duration > args.duration:
    base_rgb = base_rgb.set_duration(args.duration)

print("Opened RGB video of length %.2fs" % base_rgb.duration)

# make a set of text clips showing text state from bin log
flightstate_clips = make_flight_state_clips(args.log_bin, base_rgb.start_time, base_rgb.duration)
print("FlightState: %u clips" % len(flightstate_clips))

print("making PIP thermal")
thermal_video = make_thermal_video(args.thermal_dir, base_rgb.start_time, base_rgb.duration).set_position(("left","top"))
                                 
print("Created thermal video of length %.2fs" % thermal_video.duration)

thermal_offset = thermal_video.start_time - base_rgb.start_time
flight_offset = flightstate_clips[0].start_time - base_rgb.start_time
print("thermal: offset=%.2fs duration=%.2f" % (thermal_offset, thermal_video.duration))
print("flight data: offset=%.2fs len=%u" % (flight_offset, len(flightstate_clips)))

# setup start times to sync
thermal_video = thermal_video.set_start(thermal_offset)

# create combined video
video = CompositeVideoClip([base_rgb, thermal_video] + flightstate_clips)

# and write it out
if args.duration is not None:
    video = video.set_duration(args.duration)

video.write_videofile(args.output, fps=args.fps, codec='h264')
