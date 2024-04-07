#!/usr/bin/env python

'''
merge a SIYI_log.bin into a ArduPilot onboard bin log to create a new merged log
'''

import os
from argparse import ArgumentParser
from progress.bar import Bar

parser = ArgumentParser(description=__doc__)

parser.add_argument("alog", metavar="ALOG")
parser.add_argument("slog", metavar="SLOG")
parser.add_argument("logout", metavar="LOGOUT")

args = parser.parse_args()

from pymavlink import mavutil
from pymavlink import DFReader

alog = mavutil.mavlink_connection(args.alog)
slog = mavutil.mavlink_connection(args.slog)
output = open(args.logout, mode='wb')

siyi_format = {}
used_ids = set()

m1 = None
m2 = None
pct = 0
time_offset = 0

def allocate_id():
    '''
    allocate an unused id from the ardupilot bin log
    '''
    for id in range(100, 254):
        if not id in alog.id_to_name and not id in used_ids:
            used_ids.add(id)
            return id
    return None

def write_message(m):
    mtype = m.get_type()
    if mtype == "FMT":
        if m.Name in siyi_format or m.Name in alog.name_to_id:
            return
        id = allocate_id()
        if id is None:
            return
        fmt = DFReader.DFFormat(id, m.Name, m.Length, m.Format, m.Columns)
        siyi_format[m.Name] = fmt
        buf = bytearray(m.get_msgbuf())
        buf[3] = id
        output.write(buf)
        print("Added %s with id %u" % (m.Name, id))
        return
    if mtype in alog.name_to_id:
        return
    if not mtype in siyi_format:
        print("Unknown %s" % mtype)
        return
    buf = bytearray(m.get_msgbuf())
    buf[2] = siyi_format[mtype].type
    output.write(buf)

bar = Bar('Merging logs', max=100)

while True:
    if m1 is None:
        m1 = alog.recv_msg()
    if m2 is None:
        m2 = slog.recv_msg()

    new_pct = (alog.offset * 100) // alog.data_len
    if new_pct != pct:
        bar.next()
        pct = new_pct

    if m1 is None and m2 is None:
        # all done
        break

    if m2 is None and m1 is not None:
        # pass-thru m1
        output.write(m1.get_msgbuf())
        m1 = None
        continue

    if m1 is None and m2 is not None:
        # pass-thru m1
        write_message(m2)
        m2 = None
        continue

    if m2._timestamp > m1._timestamp + 10*3600:
        # we have the 18 hour issue
        time_offset = 18*3600

    if m1._timestamp < m2._timestamp - time_offset:
        # m1 is older, pass-thru m1
        output.write(m1.get_msgbuf())
        m1 = None
        continue

    # m2 is older
    write_message(m2)
    m2 = None
