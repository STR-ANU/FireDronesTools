#!/usr/bin/env python3
'''
create a video from raw thermal, RGB video 

assumes a flight_dir with the following symlinks:

  100SIYI_VID
  102SIYI_TEM
  log.bin
  SIYI_log.bin
'''

import argparse

parser = argparse.ArgumentParser(description='Create thermal video')
parser.add_argument('flight_dir', default=None, help='flight data directory')
parser.add_argument('output', default=None, help='output video')
parser.add_argument('--fps', type=int, default=1, help='output frame rate')
parser.add_argument('--temp-min', type=float, default=0, help='min temperature')
parser.add_argument('--temp-max', type=float, default=188, help='max temperature')
parser.add_argument('--threshold', type=float, default=80, help='color threshold')
parser.add_argument('--duration', type=float, default=None, help='duration in seconds')
parser.add_argument('--codec', type=str, default='h264', help='output codec')

args = parser.parse_args()

import os
import sys
import subprocess
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

RGB_DIR = "100SIYI_VID"
THERMAL_DIR = "102SIYI_TEM"
LOG_NAME = "log.bin"
SIYI_LOG_NAME = "SIYI_log.bin"

def load_thermal_to_temperatures(fname):
    '''load a raw thermal file returning a temperature array in degrees C'''
    a = np.fromfile(fname, dtype='>u2')
    if len(a) != thermal_width * thermal_height:
        return None

    # get in C
    return (a / 64.0) - C_TO_KELVIN

def sorted_files(dir):
    '''return a list of files sorted by mtime'''
    ret = sorted(os.listdir(dir), key=lambda img: os.path.getmtime(os.path.join(dir, img)))
    ret = [os.path.join(dir, x) for x in ret]
    return ret

def find_temp_range(thermal_dir):
    '''find the range of temperatures in a thermal directory'''
    tmin = None
    tmax = None
    images = sorted_files(thermal_dir)
    for img in images:
        a = load_thermal_to_temperatures(img)
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

    images = sorted_files(thermal_dir)
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
        mod_time = os.path.getmtime(image)
        if mod_time < start_time:
            continue
        if mod_time > start_time+rgb_duration:
            break
        if first_timestamp is None:
            first_timestamp = mod_time
        if i < len(images)-1:
            next_mod_time = os.path.getmtime(images[i+1])
        else:
            next_mod_time = mod_time + 1.0
    
        duration = next_mod_time - mod_time

        rgb = load_thermal_colormap(image, min_temp, max_temp)
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

def make_flight_state_video(log_bin, start_time, rgb_duration):
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

    video = CompositeVideoClip(clips, size=(thermal_width, thermal_height))
    video.start_time = clips[0].start_time
    return video

def concatenate_videos(video_files, output_file, duration=None):
    # Use NamedTemporaryFile to create a temporary file
    flist=output_file[:-4] + "_flist.txt"
    f = open(flist,'w')
    for video in video_files:
        f.write(f"file '{video}'\n")
    f.close()

    # Call ffmpeg to concatenate the videos using the temporary file list
    args = [
        'ffmpeg',
        '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', flist,
        '-c', 'copy',
        ]
    if duration is not None:
        args += ['-t', "%.2f" % duration]
    subprocess.run(args + [output_file])
    os.unlink(flist)

    # set mtime to mtime of last file, so start time can be predicted from mtime
    last_mtime = os.path.getmtime(video_files[-1])
    os.utime(output_file, (last_mtime, last_mtime))

def overlay_videos(rgb, thermal, flight_state, output, duration):
    '''Call ffmpeg to concatenate the videos using the temporary file list'''
    subprocess.run([
        'ffmpeg',
        '-y',
        '-i', rgb,
        '-i', thermal,
        '-i', flight_state,
        '-filter_complex',
        'overlay=0:0,overlay=main_w-overlay_w:0',
        '-codec', args.codec,
        '-t', "%.2f" % duration,
        output
    ])

def make_rbg_video():
    '''make the rgb video concatenating all RGB videos'''
    videos = sorted_files(os.path.join(args.flight_dir, RGB_DIR))
    if len(videos) <= 1:
        return videos[0]
    first_duration = VideoFileClip(videos[0]).duration
    start_time = os.path.getmtime(videos[0]) - first_duration
    rgb_tmp = output_base + "_rgb_tmp.mp4"
    print("Concatenating %u RGB videos" % len(videos))
    concatenate_videos(videos, rgb_tmp, duration=args.duration)

    # fixup mtime
    duration = VideoFileClip(rgb_tmp).duration
    end_time = start_time + duration
    os.utime(rgb_tmp, (end_time, end_time))
    
    return rgb_tmp

# get the base name of the output file for temporary files
output_base = args.output[:-4]

rgb_file = make_rbg_video()

# get the RGB video
base_rgb = VideoFileClip(rgb_file)
base_rgb.start_time = os.path.getmtime(rgb_file) - base_rgb.duration

if args.duration is not None and base_rgb.duration > args.duration:
    base_rgb = base_rgb.set_duration(args.duration)

print("Opened RGB video of length %.2fs" % base_rgb.duration)

# make a video of text clips showing text state from bin log
flightstate_video = make_flight_state_video(os.path.join(args.flight_dir, LOG_NAME), base_rgb.start_time, base_rgb.duration)
flightstate_tmp = output_base + "_flight_tmp.mp4"
flightstate_video.write_videofile(flightstate_tmp, fps=1, codec=args.codec)
print("Created flight state video of length %.2fs" % flightstate_video.duration)

print("making PIP thermal")
thermal_video = make_thermal_video(os.path.join(args.flight_dir,THERMAL_DIR), base_rgb.start_time, base_rgb.duration).set_position(("left","top"))
thermal_tmp = output_base + "_thermal_tmp.mp4"
thermal_video.write_videofile(thermal_tmp, fps=1, codec=args.codec)
                                 
print("Created thermal video of length %.2fs" % thermal_video.duration)

thermal_offset = thermal_video.start_time - base_rgb.start_time
flight_offset = flightstate_video.start_time - base_rgb.start_time
print("thermal: offset=%.2fs duration=%.2f" % (thermal_offset, thermal_video.duration))
print("flight data: offset=%.2fs duration=%.2f" % (flight_offset, flightstate_video.duration))

print("Overlaying videos onto %s" % args.output)
overlay_videos(rgb_file, thermal_tmp, flightstate_tmp, args.output, base_rgb.duration)
