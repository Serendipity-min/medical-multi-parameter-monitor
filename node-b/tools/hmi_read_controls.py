"""独立串口屏控件只读查询；复用现有GetControlValue的EE B1 11协议，不改画面/Flash。"""
import argparse
import json
from pathlib import Path
import struct
import time

import serial
import b5_g3_contract as g


def request(screen,control):
    return b'\xee\xb1\x11'+struct.pack('>HH',screen,control)+b'\xff\xfc\xff\xff'


def responses(blob):
    rows=[]
    for part in blob.split(b'\xff\xfc\xff\xff')[:-1]:
        start=part.find(b'\xee\xb1\x11')
        if start<0:continue
        frame=part[start:]
        if len(frame)<8:continue
        screen,control=struct.unpack_from('>HH',frame,3)
        text=frame[8:].rstrip(b'\0').decode('gbk',errors='replace')
        rows.append({'screen':screen,'control':control,'type':frame[7],'text':text,'raw_hex':frame.hex()})
    return rows


def read_controls(port_name,screen,first,last,out):
    out.mkdir();g.private.protected(out,False);received=bytearray();events=[]
    port=serial.Serial(port=None,baudrate=115200,timeout=.03,write_timeout=.3)
    port.dtr=False;port.rts=False;port.port=port_name
    try:
        port.open()
        for control in range(first,last+1):
            command=request(screen,control)
            g.require(port.write(command)==len(command),'HMI_READ_QUERY_SHORT_WRITE')
            events.append({'monotonic':time.monotonic(),'query_screen':screen,'query_control':control,'TX_hex':command.hex()})
            deadline=time.monotonic()+.15
            while time.monotonic()<deadline:
                chunk=port.read(max(1,port.in_waiting))
                if chunk:received.extend(chunk)
    finally:
        port.close()
        g.write_private(out/'screen-RX-private.bin',bytes(received));g.save(out/'read-query-events-private.json',events)
    result={'exit_code':0,'screen':screen,'query_range':[first,last],'responses':responses(bytes(received)),
            'commands':'GetControlValue only','screen_changes':0,'Flash_operations':0,'MCU_connection':False}
    g.save(out/'screen-controls-private.json',result)
    print(json.dumps({'exit_code':0,'responses':len(result['responses']),'temperature_36_5_candidates':[
        {'screen':r['screen'],'control':r['control'],'type':r['type']} for r in result['responses'] if r['type']==0x11 and r['text'].strip()=='36.5']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port');p.add_argument('--screen',type=int,default=0)
    p.add_argument('--first',type=int,default=0);p.add_argument('--last',type=int,default=99)
    p.add_argument('--out',type=Path);p.add_argument('--execute-readonly',action='store_true');a=p.parse_args()
    g.require(0<=a.screen<=65535 and 0<=a.first<=a.last<=255,'HMI_QUERY_RANGE')
    if not a.execute_readonly:print(json.dumps({'enabled':False,'commands':'GetControlValue only','physical_route_required':'Screen isolated from MCU TX; independently confirmed TTL adapter and voltage'}))
    else:
        g.require(a.port is not None and a.out is not None and not a.out.exists(),'HMI_PORT_AND_NEW_OUTPUT_REQUIRED')
        g.private.protected(a.out.parent,False);read_controls(a.port,a.screen,a.first,a.last,a.out)
