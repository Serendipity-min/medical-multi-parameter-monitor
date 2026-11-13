import io
import json
from pathlib import Path
import queue
import sys
import unittest
import asyncio
import threading
from unittest.mock import patch,AsyncMock,Mock
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'node-b/tools'),str(ROOT)]
import b5_g3_cloud as cloud

class FinalEvents(unittest.TestCase):
    def test_hanging_client_cleanup_is_bounded_and_never_complete(self):
        release=threading.Event();client=Mock();client.loop_stop.side_effect=lambda:release.wait(1)
        self.assertFalse(cloud.close_client_bounded(client,.01));release.set()
    def test_normal_client_cleanup_is_proven(self):
        client=Mock();self.assertTrue(cloud.close_client_bounded(client,.1))
        client.disconnect.assert_called_once();client.loop_stop.assert_called_once()
    def test_failure_latch_does_not_discard_pending_native_disconnect(self):
        q=queue.Queue();log=io.StringIO()
        event={'code':7,'requested_shutdown':False,'received_monotonic':123.5}
        q.put(('OBSERVER_DISCONNECT',event));cloud.drain_final_events(q,log)
        row=json.loads(log.getvalue());self.assertEqual(row['kind'],'OBSERVER_DISCONNECT')
        self.assertEqual(row['data'],event);self.assertTrue(q.empty())
    def test_shutdown_keeps_raw_tail_in_order_and_distinguishes_requested_close(self):
        q=queue.Queue();log=io.StringIO()
        q.put(('BROKER_RAW',{'payload_hex':'0001','received_monotonic':123.4}))
        q.put(('OBSERVER_DISCONNECT',{'code':0,'requested_shutdown':True}))
        cloud.drain_final_events(q,log);rows=[json.loads(s) for s in log.getvalue().splitlines()]
        self.assertEqual([x['kind'] for x in rows],['BROKER_RAW','OBSERVER_DISCONNECT'])
        self.assertEqual(rows[0]['data']['payload_hex'],'0001')
        self.assertTrue(rows[1]['data']['requested_shutdown'])

class HealthDeadline(unittest.IsolatedAsyncioTestCase):
    async def test_actual_content_length_response_and_cleanup(self):
        reader=asyncio.StreamReader();body=b'{"status":"ok","mqtt_connected":true}'
        reader.feed_data(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        writer=Mock();writer.drain=AsyncMock();writer.wait_closed=AsyncMock()
        with patch.object(cloud.asyncio,'open_connection',AsyncMock(return_value=(reader,writer))):
            self.assertTrue((await cloud.bounded_health('synthetic.invalid',1))['mqtt_connected'])
        writer.close.assert_called_once();writer.wait_closed.assert_awaited_once()
    async def test_entire_exchange_has_one_deadline_and_closes_on_timeout(self):
        reader=asyncio.StreamReader();writer=Mock();writer.drain=AsyncMock();writer.wait_closed=AsyncMock()
        with patch.object(cloud.asyncio,'open_connection',AsyncMock(return_value=(reader,writer))):
            started=asyncio.get_running_loop().time()
            with self.assertRaises(asyncio.TimeoutError):await cloud.bounded_health('synthetic.invalid',1,.03)
            self.assertLess(asyncio.get_running_loop().time()-started,.3)
        writer.close.assert_called_once()

if __name__=='__main__':unittest.main()
