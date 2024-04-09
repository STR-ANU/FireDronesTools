#!/usr/bin/env python3
'''
convert thermal images to CSV for Nicks project
'''

import sys
import os
from datetime import datetime
import numpy as np
import struct
from pymavlink import mavutil
from math import *

import argparse

parser = argparse.ArgumentParser(description='convert to CSV')
parser.add_argument('thermaldata', nargs="+", default=[], help='thermal bin files')
parser.add_argument('--SIYI', default=None, help='SIYI bin log')
parser.add_argument('--min-temp', type=float, default=-100, help='min temperature for convert')
parser.add_argument('--first-temp', type=float, default=200, help='min first temperature for convert')
parser.add_argument('--basepos', type=str, default="-35.28251139,149.00575706,594.0", help='base position')
args = parser.parse_args()

base = args.basepos.split(",")
baselat = float(base[0])
baselon = float(base[1])
basealt = float(base[2])

class SIYIData(object):
    def __init__(self, filename):
        print("Opening SIYI log %s" % filename)
        mlog = mavutil.mavlink_connection(filename)
        self.gps = []
        self.idx = 0
        self.last_timestamp = None
        while True:
            m = mlog.recv_match(type=['GPS'])
            if m is None:
                break
            self.gps.append(m)
        print("Loaded %u GPS records" % len(self.gps))

    def get_distance(self, timestamp):
        if self.last_timestamp is None or timestamp < self.last_timestamp:
            self.idx = 0
        m = None
        for i in range(self.idx, len(self.gps)):
            if self.gps[i]._timestamp >= timestamp:
                m = self.gps[i]
                break
        if m is None:
            return None
        dLat = radians(m.Lat - baselat)
        dLon = radians(m.Lng - baselon)
        dAlt = radians(m.Alt - basealt)

        a = sin(0.5*dLat)**2 + sin(0.5*dLon)**2 * cos(radians(baselat)) * cos(radians(m.Lat))
        c = 2.0 * atan2(sqrt(a), sqrt(1.0-a))
        ground_dist = 6371 * 1000 * c
        return sqrt(ground_dist**2 + dAlt**2)


summary = open("summary.csv","w")
summary.write("FileName,TimeStamp,Distance,TMin,TMax\n")

siyi = SIYIData(args.SIYI)

def convert_to_csv(filenames):
    seen_first_temp = False
    for filename in filenames:
        # Read the binary data
        with open(filename, 'rb') as file:
            data = file.read()
        
        # Unpack the binary data to 16-bit unsigned integers
        unpacked_data = struct.unpack('>327680H', data)

        # Convert the data to a NumPy array and reshape
        temperature_data_raw = np.array(unpacked_data)

        # Convert from 1/64th Kelvin to Celsius
        temperature_data_celsius = (temperature_data_raw / 64.0) - 273.15
        
        tmin = temperature_data_celsius.min()
        tmax = temperature_data_celsius.max()

        if tmax < args.min_temp:
            continue

        if not seen_first_temp and tmax < args.first_temp:
            continue
        seen_first_temp = True

        timestamp = os.path.getmtime(filename)
        mtime_human = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        distance = siyi.get_distance(timestamp)
        if distance is None:
            continue

        temperature_data_celsius = temperature_data_raw.reshape((512, 640))
        

        # Write the data to a CSV file
        csv_filename = f"{filename.split('.')[0]}.csv"
        np.savetxt(csv_filename, temperature_data_celsius, fmt='%.1f', delimiter=',')

        print(f"Converted {filename} to {csv_filename} trange=[{tmin}, {tmax}] dist={distance} {mtime_human}")
        summary.write(f'''{filename},{mtime_human},{distance},{tmin},{tmax}\n''')

convert_to_csv(args.thermaldata)
