"""M0仅验证新增入口、当前源会话选择和主机观察期限，无设备连接。"""
import copy
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tools'))
import m0_field
import m0_review
import importlib.util
voice_spec=importlib.util.spec_from_file_location('m0_voice_field',ROOT/'gateway/microphone/field.py')
voice_field=importlib.util.module_from_spec(voice_spec);voice_spec.loader.exec_module(voice_field)
import b5_g3_devices as devices


class Entry(unittest.TestCase):
    def test_nibp_replacement_expiry_and_resurrection(self):
        first={'node_id':'NODE-A','stream':'NIBP','session_id':'fixture','seq':1,'timestamp':1000,'validity':'VALID','value':[127,64]}
        second=dict(first,seq=2,timestamp=2000,value=[101,64])
        snapshots=[{'server_time':1100,'streams':[first]},{'server_time':2100,'streams':[second]},
            {'server_time':92001,'streams':[dict(second,validity='STALE',value=None)]}]
        old=m0_review.nibp_lifecycle(first,[first,second],snapshots)
        last=m0_review.nibp_lifecycle(second,[first,second],snapshots)
        self.assertTrue(old['superseded_before_expiry']);self.assertFalse(old['expiry_observed']);self.assertFalse(old['resurrected'])
        self.assertTrue(last['expiry_observed']);self.assertFalse(last['resurrected'])
        revival=snapshots+[{'server_time':2200,'streams':[first]}]
        self.assertTrue(m0_review.nibp_lifecycle(first,[first,second],revival)['resurrected'])
        late=[{'server_time':92001,'streams':[second]}]
        self.assertFalse(m0_review.nibp_lifecycle(second,[second],late)['expiry_observed'])
        self.assertTrue(m0_review.nibp_lifecycle(second,[second],late)['resurrected'])
        duplicate=[{'server_time':1100,'streams':[first]},{'server_time':90000,'streams':[first]}]
        self.assertFalse(m0_review.nibp_lifecycle(first,[first,first],duplicate)['superseded_before_expiry'])
        self.assertFalse(m0_review.nibp_lifecycle(first,[first],duplicate)['expiry_observed'])
        fresh_same_value=dict(second,value=first['value'])
        self.assertTrue(m0_review.nibp_lifecycle(first,[first,fresh_same_value],
            [{'server_time':2100,'streams':[fresh_same_value]}])['superseded_before_expiry'])

    def test_failed_tts_still_gets_global_stop_without_claiming_idle(self):
        class Port:
            def __init__(self):self.is_open=False;self.pending=bytearray();self.writes=[];self.network=False
            def open(self):self.is_open=True
            def close(self):self.is_open=False
            def write(self,body):
                self.writes.append(body)
                if self.network:
                    self.pending.extend(b'UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM\r\n' if body==b'I' else
                        b'UNI CONFIG_OK\r\n' if body.startswith(b'F') else
                        (b'B5 STOPPED NO_AUTOREARM\r\n' if self.network==2 else
                         b'GW FAIL AT\r\nGW CLOSE_UNSYNCED_MANUAL_POWER_REQUIRED\r\n') if body.startswith(b'UNISTART ') else b'')
                    return
                fault=b'UNI AUDIO phase=8 session=0 chunk=0 stop_ack=0 stop_query=0 stop_idle=0 stop_failed=1 tts_uart=0 tts_overflow=0\r\n'
                self.pending.extend(fault+b'UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM\r\n' if body==b'I' else
                    b'B5 STOPPED NO_AUTOREARM\r\n' if body==b'X' else fault)
            def read(self,n):
                value=bytes(self.pending[:n]);del self.pending[:n];return value
        real_stat=Path.stat
        class EfsStat:
            def __init__(self,actual):self.actual=actual;self.st_file_attributes=0x4000
            def __getattr__(self,name):return getattr(self.actual,name)
        port=Port()
        with tempfile.TemporaryDirectory() as folder:
            args=['field.py','--job',folder,'--port','NO_DEVICE','--action','finish','--unified']
            with patch.object(sys,'argv',args),patch.object(voice_field.serial,'Serial',return_value=port),\
                    patch.object(Path,'stat',autospec=True,side_effect=lambda p,*a,**k:EfsStat(real_stat(p,*a,**k))),\
                    contextlib.redirect_stdout(io.StringIO()):
                result=voice_field.main()
            receipt=json.loads(next(Path(folder).glob('field-finish-*/receipt.json')).read_text())
            self.assertEqual(port.writes,[b'I',b'X',b'Q'])
            self.assertEqual(result,1)
            self.assertEqual(receipt['reason'],'FIELD_TTS_STOP_UNCONFIRMED')
            self.assertFalse(port.is_open)
        for mode,reason in ((1,'FIELD_NETWORK_UNSYNCED_REQUIRES_COLD_BOOT'),(2,'FIELD_CONNECT_TARGET_STOPPED')):
            port=Port();port.network=mode
            with tempfile.TemporaryDirectory() as folder:
                (Path(folder)/'voice-runtime-credentials-private.json').write_text(json.dumps({'roles':{'b5-gateway':'synthetic-mqtt-password'}}))
                (Path(folder)/'host-hotspot-runtime-private.json').write_text(json.dumps({'ssid':'synthetic-wifi','wifi_password':'synthetic-wifi-password'}))
                args=['field.py','--job',folder,'--port','NO_DEVICE','--action','connect','--unified']
                with patch.object(sys,'argv',args),patch.object(voice_field.serial,'Serial',return_value=port),\
                        patch.object(Path,'stat',autospec=True,side_effect=lambda p,*a,**k:EfsStat(real_stat(p,*a,**k))),\
                        contextlib.redirect_stdout(io.StringIO()):
                    result=voice_field.main()
                receipt=json.loads(next(Path(folder).glob('field-connect-*/receipt.json')).read_text())
                self.assertEqual(result,1)
                self.assertEqual(receipt['reason'],reason)
                self.assertEqual(port.writes[-2:],[b'UNISTART C\n',b'Q'])
                self.assertNotIn(b'R',port.writes)
                self.assertFalse(port.is_open)

    def test_actual_record_ack_interleaved_in_can_diagnostic(self):
        raw=b'UNI CAN water_a=0 water_b=8 mask=2 limit_ms=0 network_fault=0 replay_a=0 replUNI RECORDING\r\n'
        self.assertEqual(voice_field.serial_ack(raw,b'UNI RECORDING'),b'UNI RECORDING\r\n')
        rows=[{'monotonic':100,'data':raw.decode().strip()},{'monotonic':100.001,'data':'ay_b=0 can_poll_cycles_max=43537'}]
        original=copy.deepcopy(rows);logical,repairs=m0_review.console_rows(rows)
        self.assertEqual(rows,original)
        self.assertEqual(logical[0]['monotonic'],100)
        self.assertIn('replay_a=0 replay_b=0 can_poll_cycles_max=43537',logical[0]['data'])
        self.assertEqual(len(repairs),1)
        self.assertIsNone(voice_field.serial_ack(b'UNI RECORD_REJECTED_GATEWAY_STOPPED\r\n',b'UNI RECORDING'))

    def test_server_clock_lag_cannot_include_post_stop_offline(self):
        events=[
            {'kind':'WSS_RAW','monotonic':99.99,'data':{'server_time':100400,'gateway_state':'ONLINE'}},
            {'kind':'WSS_RAW','monotonic':100.1,'data':{'server_time':99800,'gateway_state':'ONLINE'}},
            {'kind':'WSS_RAW','monotonic':399.999,'data':{'server_time':399600,'gateway_state':'ONLINE'}},
            {'kind':'WSS_RAW','monotonic':400.203,'data':{'server_time':399815,'gateway_state':'OFFLINE'}},
        ]
        legacy=[x['data'] for x in events if 100000<=x['data']['server_time']<400000]
        self.assertTrue(any(x['gateway_state']=='OFFLINE' for x in legacy))
        selected=m0_review.state_snapshots(events,100,(100000,400000))
        self.assertEqual([x['server_time'] for x in selected],[399600])
        self.assertTrue(all(x['gateway_state']=='ONLINE' for x in selected))

    def test_host_cancel_before_capture_opens_no_serial(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'STOP_BEFORE_CAPTURE').write_text('host-preparation-cancel')
            r=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'gateway/microphone/field.py'),
                '--job',folder,'--port','NO_DEVICE','--action','capture','--unified',
                '--topology','BC','--window-seconds','300'],capture_output=True)
            self.assertEqual(r.returncode,2)
            self.assertIn(b'M0_HOST_CANCELLED_BEFORE_SERIAL_AND_RECORDING',r.stdout)
            self.assertEqual([p.name for p in Path(folder).iterdir()],['STOP_BEFORE_CAPTURE'])

    def test_topology_needs_unified_before_serial(self):
        with tempfile.TemporaryDirectory() as folder:
            r=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'gateway/microphone/field.py'),
                '--job',folder,'--port','NO_DEVICE','--action','connect','--topology','BC'],capture_output=True)
            self.assertEqual(r.returncode,2)
            self.assertFalse(list(Path(folder).iterdir()))

    def test_300_seconds_rejects_connect_before_serial(self):
        with tempfile.TemporaryDirectory() as folder:
            r=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'gateway/microphone/field.py'),
                '--job',folder,'--port','NO_DEVICE','--action','connect','--unified','--window-seconds','300'],capture_output=True)
            self.assertEqual(r.returncode,2)
            self.assertFalse(list(Path(folder).iterdir()))

    def test_ready_requires_current_valid_real_b_streams(self):
        snap={'gateway_state':'ONLINE','nodes':{'NODE-A':'OFFLINE','NODE-B':'ONLINE'},'streams':[
            {'stream':name,'node_id':'NODE-B','session_id':'m0-99-22','validity':'VALID','value':value}
            for name,value in (('HR',60),('ECG',None),('TEMP',25.6))]}
        self.assertEqual(m0_field.b_session(snap,'m0-99-0','ECG60'),'m0-99-22')
        old=copy.deepcopy(snap);old['streams'][1]['session_id']='m0-98-22'
        self.assertIsNone(m0_field.b_session(old,'m0-99-0','ECG60'))
        stale=copy.deepcopy(snap);stale['streams'][2]['validity']='STALE'
        self.assertIsNone(m0_field.b_session(stale,'m0-99-0','ECG60'))
        self.assertIsNone(m0_field.b_session(snap,'m0-99-0','RR18'))

    def test_m0_host_duration_does_not_change_legacy_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'ARM_ATTEMPT.json').write_text(json.dumps({'monotonic':0}))
            link=devices.BLink.__new__(devices.BLink)
            link.root=root;link.started=0;link.host_cancel_close=False;link.host_cancel_cleanup_s=0
            link.operator_wait_extra_s=0;link.error=False;link.integration_window_s=1200
            with patch.object(devices.time,'monotonic',return_value=500):
                link.gate()
                link.integration_window_s=0
                with self.assertRaises(ValueError):link.gate()
            link.integration_window_s=1200
            with patch.object(devices.time,'monotonic',return_value=1201):
                with self.assertRaises(ValueError):link.gate()


if __name__=='__main__':unittest.main()
