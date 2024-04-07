#!/usr/bin/env python3

import gmplot
import os

import argparse
from pymavlink import mavutil, mavwp
import numpy as np
import math
from pymavlink.rotmat import Matrix3, Vector3
from MAVProxy.modules.lib import mp_util
from moviepy.editor import VideoFileClip

parser = argparse.ArgumentParser(description='Create thermal video')
parser.add_argument('binlog', default=None, help='ArduPilot bin log')
parser.add_argument('thermal_dir', default=None, help='thermal directory')
parser.add_argument('output', default=None, help='output html')
parser.add_argument('--min-temp', type=float, default=150.0, help='min temperature for display')
parser.add_argument('--time-delta', type=float, default=1.0, help='time resolution')
parser.add_argument('--video', type=str, action='append', default=[], help='video files')
args = parser.parse_args()

thermal_width = 640
thermal_height = 512
thermal_FOV = 22.8

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
    def __init__(self, timestamp, lat, lon, theight, yaw, SIGA, SITR, SIRF):
        self.timestamp = timestamp
        self.lat = lat
        self.lon = lon
        self.theight = theight
        self.yaw = yaw
        self.GRoll = SIGA.R
        self.GPitch = SIGA.P
        self.GYaw = SIGA.Y
        self.SR = SIRF.SR
        self.TMin = SITR.TMin
        self.TMax = SITR.TMax

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


def get_flight_positions(binlog):
    '''extract list of flight positions'''
    mlog = mavutil.mavlink_connection(binlog)
    last_time = None
    ret = FlightPositions()
    while True:
        m = mlog.recv_match(type=['POS','TERR','ATT','SIGA','SIRF','SITR'])
        if m is None:
            break
        mtype = m.get_type()
        if mtype != 'POS':
            continue
        TERR = mlog.messages.get('TERR',None)
        ATT = mlog.messages.get('ATT',None)
        if TERR is None or ATT is None:
            continue
        SIRF = mlog.messages.get('SIRF', None)
        SITR = mlog.messages.get('SITR', None)
        SIGA = mlog.messages.get('SIGA', None)
        if SIRF is None or SITR is None or SIGA is None:
            continue
        timestamp = m._timestamp
        if last_time is None or timestamp - last_time > args.time_delta:
            ret.add(FlightPos(timestamp, m.Lat, m.Lng, TERR.CHeight, ATT.Yaw, SIGA, SITR, SIRF))
            last_time = timestamp
    return ret

def get_view_vector(fpos, x, y, FOV, aspect_ratio):
    '''
    get ground lat/lon given vehicle orientation, camera orientation and slant range
    x and y are from -1 to 1, relative to center of camera view
    positive x is to the right
    positive y is down
    '''
    v = Vector3(1, 0, 0)
    m = Matrix3()
    (roll,pitch,yaw) = (math.radians(fpos.GRoll),math.radians(fpos.GPitch),math.radians(fpos.GYaw))
    yaw += fpos.yaw
    FOV_half = math.radians(0.5*FOV)
    yaw += FOV_half*x
    pitch -= y*FOV_half/aspect_ratio
    m.from_euler(roll, pitch, yaw)
    v = m * v
    return v

def get_latlon(fpos, x, y, FOV, aspect_ratio):
    '''
    get ground lat/lon given vehicle orientation, camera orientation and slant range
    x and y are from -1 to 1, relative to center of camera view
    '''
    v = get_view_vector(fpos, x,y,FOV,aspect_ratio)
    if v is None:
        return None
    v *= fpos.SR
    (lat,lon) = (fpos.lat,fpos.lon)
    (lat,lon) = mp_util.gps_offset(lat,lon,v.y,v.x)
    return (lat, lon)

def xy_to_latlon(fpos, x, y):
    '''convert x,y pixel coordinates to a latlon tuple'''
    (yres, xres, depth) = (thermal_height, thermal_width, 1)
    x = (2 * x / float(xres)) - 1.0
    y = (2 * y / float(yres)) - 1.0
    aspect_ratio = float(xres) / yres
    FOV = thermal_FOV
    slant_range = fpos.SR
    return get_latlon(fpos, x, y, FOV, aspect_ratio)

def find_projection_by_timestamp(timestamp, x, y):
    '''find lat/lon of a pixel in the thermal image by timestamp'''
    fpos = flight_pos.find_by_timestamp(timestamp)
    if fpos is None:
        return None
    latlon = xy_to_latlon(fpos, x, y)
    return latlon

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
        latlon = find_projection_by_timestamp(mtime, thermal_width//2, thermal_height//2)
        if latlon is None:
            continue
        lats.append(latlon[0])
        lons.append(latlon[1])
        heat.append(h)
    gmap.heatmap(lats, lons, weights=heat)


def create_flight_json(flight_pos):
    '''create a flight.json file containing meta data for the flight'''
    j = open('flight.json', 'w')
    j.write('''
[
''')
    count = flight_pos.count()
    for idx in range(count):
        p = flight_pos.get(idx)
        j.write(f'''{{
 "timestamp" : {p.timestamp},
 "lat" : {p.lat},
 "lon" : {p.lon},
 "theight" : {p.theight},
 "yaw" : {p.yaw},
 "GRoll" : {p.GRoll},
 "GPitch" : {p.GPitch},
 "GYaw" : {p.GYaw},
 "SR" : {p.SR},
 "TMin" : {p.TMin},
 "TMax" : {p.TMax}
}}''')
        if idx < count-1:
            j.write(',\n')
        else:
            j.write('\n')
    j.write('''
]
''')
    j.close()

def get_video_start_time(video):
    '''get start time of a video file'''
    duration = VideoFileClip(video).duration
    mtime = os.path.getmtime(video)
    start_time = mtime - duration
    return start_time


def add_videos(gmap):
    '''add in videos to the page'''
    print('Videos: ', args.video)

    videos_json = '''video_list = [
'''
    for i in range(len(args.video)):
        video = args.video[i]
        start_time = get_video_start_time(video)
        videos_json += f'''{{
 "video_id" : "Video_{i}",
 "name" : "{video}",
 "start_time" : new Date({start_time}*1000),
}}'''
        if i < len(args.video)-1:
            videos_json += ','
        videos_json += '\n'
    videos_json += '''
]
'''
    gmap.add_custom('js', videos_json)

    gmap.add_custom('html_top','''
<div id="videoContainer">
<table>
<tr>
''')
    for i in range(len(args.video)):
        video = args.video[i]
        gmap.add_custom('html_top',f'''
<td>
    <video id="Video_{i}" width="320" height="240" controls>
        <source src="{video}" type="video/mp4">
    </video>
</td>
''')
    gmap.add_custom('html_top','''
<td>
<div id="status_text">Initialising</div>
</td>
</tr>
</table>
</div>
<script>
    function playVideo() {
        var video = document.getElementById("RGBvideoPlayer");
        video.play();
    }

    function seekVideo(time) {
        var video = document.getElementById("ThermalvideoPlayer");
        video.currentTime = time;
    }
</script>
''')

apikey = get_API_key()
gmap = gmplot.GoogleMapPlotter(-35.42274099, 149.00443460, 12, apikey=apikey, map_type='satellite', title='FireMap')

kml_url = "http://uav.tridgell.net/.Angel/FB810-Bullen.kml"

gmap.display_KML(kml_url)

wp = get_waypoints(args.binlog)
print("Loaded %u waypoints" % wp.count())

flight_pos = get_flight_positions(args.binlog)

plot_mission(gmap, wp)
plot_flightpath(gmap, flight_pos)
plot_heatmap(gmap, args.thermal_dir, flight_pos)

gmap.add_custom('html_head', '''
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
<link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet" type="text/css" />
<style>
#videoContainer {
  bottom: 1000px; /* Adjust based on your layout */
  left: 0;
  width: 100%;
  background-color: #f3f3f3;
  text-align: left;
  vertical-align: text-top;
  z-index: 1000; /* Ensure controls are on top of the page */
}
</style>
''')
gmap.add_custom('html_top', '''
  <div id="timeline"></div>
  <script src="rotmat.js"></script>
  <script src="projection.js"></script>
  <script src="timeline.js"></script>
''')
gmap.add_custom('js','''
  global_map = map;

  map.addListener("click", (mapsMouseEvent) => {
    handle_map_click(mapsMouseEvent);
  });
''')


gmap.set_option('map_height', '800px')

create_flight_json(flight_pos)

add_videos(gmap)

gmap.draw(args.output)
