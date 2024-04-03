#!/usr/bin/env python3

import gmplot
import os

import argparse
from pymavlink import mavutil, mavwp
import numpy as np
import math

parser = argparse.ArgumentParser(description='Create thermal video')
parser.add_argument('binlog', default=None, help='ArduPilot bin log')
parser.add_argument('thermal_dir', default=None, help='thermal directory')
parser.add_argument('output', default=None, help='output html')
parser.add_argument('--min-temp', type=float, default=150.0, help='min temperature for display')
args = parser.parse_args()

thermal_width = 640
thermal_height = 512

C_TO_KELVIN = 273.15

def get_API_key():
    home = os.getenv('HOME')
    try:
        key = open(os.path.join(home, ".gmap_api_key.txt"),"r").read()
    except Exception as ex:
        print(ex)
    return key.strip()

def get_waypoints(binlog):
    '''get a set of waypoints for the ArduPilot bin log, return as a mavwp object'''
    mlog = mavutil.mavlink_connection(binlog)
    wp = mavwp.MAVWPLoader()
    while True:
        m = mlog.recv_match(type=['CMD'])
        if m is None:
            break
        m = mavutil.mavlink.MAVLink_mission_item_message(0,
                                                         0,
                                                         m.CNum,
                                                         m.Frame,
                                                         m.CId,
                                                         0, 1,
                                                         m.Prm1, m.Prm2, m.Prm3, m.Prm4,
                                                         m.Lat, m.Lng, m.Alt)
        try:
            while m.seq > wp.count():
                print("Adding dummy WP %u" % wp.count())
                wp.set(m, wp.count())
            wp.set(m, m.seq)
        except Exception:
            pass
    return wp

def plot_mission(gmap, wp):
    '''display mission on the map'''
    lats = []
    lons = []
    wpcount = wp.count()
    for i in range(wpcount):
        w = wp.wp(i)
        if w.command != mavutil.mavlink.MAV_CMD_NAV_WAYPOINT:
            continue
        lats.append(w.x)
        lons.append(w.y)
    gmap.plot(lats, lons, color="white")

class FlightPos(object):
    def __init__(self, timestamp, lat, lon):
        self.timestamp = timestamp
        self.lat = lat
        self.lon = lon

class FlightPositions(object):
    '''object for set of flight positions with time lookup'''
    def __init__(self):
        self.flight_pos = []
        self.last_timestamp = None
        self.last_idx = None

    def count(self):
        return len(self.flight_pos)

    def get(self, idx):
        return self.flight_pos[idx]

    def add(self, pos):
        self.flight_pos.append(pos)

    def find_by_timestamp(self, timestamp):
        if self.last_timestamp is None or timestamp < self.last_timestamp:
            idx = 0
        else:
            idx = self.last_idx
        N = self.count()
        while idx < N:
            if timestamp <= self.flight_pos[idx].timestamp:
                return self.flight_pos[idx]
            idx += 1
        return None

def get_flight_positions(binlog, time_delta=1.0):
    '''extract list of flight positions'''
    mlog = mavutil.mavlink_connection(binlog)
    last_time = None
    ret = FlightPositions()
    while True:
        m = mlog.recv_match(type=['POS'])
        if m is None:
            break
        timestamp = m._timestamp
        if last_time is None or timestamp - last_time > time_delta:
            ret.add(FlightPos(timestamp, m.Lat, m.Lng))
            last_time = timestamp
    return ret

def plot_flightpath(gmap, flight_pos):
    '''display mission on the map'''
    lats = []
    lons = []
    for i in range(flight_pos.count()):
        p = flight_pos.get(i)
        lats.append(p.lat)
        lons.append(p.lon)
    gmap.plot(lats, lons, color="red")
    print("Plotted %u positions" % len(lats))

def load_thermal_to_temperatures(fname):
    '''load a raw thermal file returning a temperature array in degrees C'''
    a = np.fromfile(fname, dtype='>u2')
    if len(a) != thermal_width * thermal_height:
        return None

    # get in C
    return (a / 64.0) - C_TO_KELVIN

def get_heatmap_value(fname):
    '''get a value from a thermal image for heatmap display'''
    t = load_thermal_to_temperatures(fname)
    count = (t > args.min_temp).sum()
    return math.log(count+1)

def sorted_files(dir):
    '''return a list of files sorted by mtime'''
    ret = sorted(os.listdir(dir), key=lambda img: os.path.getmtime(os.path.join(dir, img)))
    ret = [os.path.join(dir, x) for x in ret]
    return ret

def plot_heatmap(gmap, thermal_dir, flight_pos):
    '''plot a heatmap from density of hot pixels in the thermal images'''
    flist = sorted_files(thermal_dir)
    lats = []
    lons = []
    heat = []
    for f in flist:
        h = get_heatmap_value(f)
        if h <= 0:
            continue
        mtime = os.path.getmtime(f)
        p = flight_pos.find_by_timestamp(mtime)
        if p is None:
            continue
        lats.append(p.lat)
        lons.append(p.lon)
        heat.append(h)
    gmap.heatmap(lats, lons, weights=heat)


apikey = get_API_key()
gmap = gmplot.GoogleMapPlotter(-35.42274099, 149.00443460, 12, apikey=apikey, map_type='satellite')

kml_url = "http://uav.tridgell.net/.Angel/FB810-Bullen.kml"

gmap.display_KML(kml_url)

wp = get_waypoints(args.binlog)
print("Loaded %u waypoints" % wp.count())

flight_pos = get_flight_positions(args.binlog)

plot_mission(gmap, wp)
plot_flightpath(gmap, flight_pos)
plot_heatmap(gmap, args.thermal_dir, flight_pos)

gmap.draw(args.output)
