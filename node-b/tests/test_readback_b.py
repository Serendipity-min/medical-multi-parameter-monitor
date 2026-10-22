"""真实备份状态机的合成客户端测试；不加载DLL、不连接设备。"""
from pathlib import Path
import sys
import tempfile
import threading
import time
import json
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from readback_b import acquire, check_identity, HALT, RESET, Link


class FakeLink:
    def __init__(self, halted=False, capacity=1024, mismatch=False, reset=False):
        self.state = HALT if halted else 0
        self.capacity, self.mismatch, self.reset = capacity, mismatch, reset
        self.commands, self.flashes = [], 0

    def open(self):
        self.commands.append('open')

    def gate(self):
        pass

    def call(self, name, timeout=5):
        self.commands.append(name)
        if name.endswith('Halt'):
            self.state = HALT
        if name.endswith('Go'):
            self.state = 0
        return 0

    def stable_halt(self):
        if not self.state & HALT or self.reset:
            raise RuntimeError('HALT_LOST_OR_RESET')

    def u32(self, address):
        return {0xE000EDF0:self.state, 0xE000ED00:0x410fc241, 0xE0042000:0x10016413,
                0x40023C14:0x0fffaaed, 0x40023C0C:0}[address]

    def read(self, address, size):
        if address == 0x1FFF7A10:
            return b'SYNTHETICUID'
        if address == 0x1FFF7A22:
            return self.capacity.to_bytes(2, 'little')
        if address == 0x08000000:
            self.flashes += 1
            return bytes([self.flashes if self.mismatch else 1])*size
        return b'X'*size


class Cases(unittest.TestCase):
    def test_heartbeat_append_survives_concurrent_reader(self):
        # 重现首轮Windows监督读句柄与unlink冲突；新事件流在读者持有句柄时也不删除文件。
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'heartbeat-events.jsonl'
            link = Link.__new__(Link)
            link.events = path.open('x',encoding='utf-8')
            link.gate = lambda: None
            link.dll = type('FakeDLL',(),{'noop':staticmethod(lambda: 7)})()
            done = threading.Event()
            errors = []
            def read():
                while not done.is_set():
                    try:
                        with path.open('r',encoding='utf-8') as stream:
                            stream.read()
                            time.sleep(.001)
                    except Exception as exc: errors.append(exc)
            reader = threading.Thread(target=read)
            reader.start()
            try:
                for _ in range(200):self.assertEqual(link.call('noop'),7)
            finally:
                done.set();reader.join();link.events.close()
            self.assertFalse(errors)
            events=[json.loads(line) for line in path.read_text('utf-8').splitlines()]
            self.assertEqual(len(events),400)
            self.assertFalse(events[-1]['active'])

    def attempt(self, link):
        with tempfile.TemporaryDirectory() as folder:
            receipt = {'halt_requests':0,'go_requests':0}
            acquire(link, Path(folder), receipt)
            return receipt

    def test_success_independent_double_read_and_resume(self):
        link = FakeLink()
        r = self.attempt(link)
        self.assertEqual(r['status'], 'BACKUP_DOUBLE_READ_PASS')
        self.assertEqual((link.flashes,r['halt_requests'],r['go_requests']), (2,1,1))

    def test_initial_halt_preserved(self):
        link = FakeLink(halted=True)
        r = self.attempt(link)
        self.assertEqual((r['halt_requests'],r['go_requests']), (0,0))
        self.assertEqual(r['target_end_state'], 'HALTED_AS_FOUND')

    def test_capacity_mismatch_no_halt_or_flash(self):
        link = FakeLink(capacity=512)
        with self.assertRaisesRegex(RuntimeError,'FLASH_CAPACITY_MISMATCH'):
            self.attempt(link)
        self.assertEqual(link.commands,['open'])
        self.assertEqual(link.flashes,0)

    def test_double_read_mismatch_no_go(self):
        link = FakeLink(mismatch=True)
        with self.assertRaisesRegex(RuntimeError,'BACKUP_DIFFERENCE'):
            self.attempt(link)
        self.assertNotIn('JLINKARM_Go',link.commands)

    def test_reset_no_flash_or_go(self):
        link = FakeLink(reset=True)
        with self.assertRaisesRegex(RuntimeError,'HALT_LOST_OR_RESET'):
            self.attempt(link)
        self.assertEqual(link.flashes,0)
        self.assertNotIn('JLINKARM_Go',link.commands)

    def test_wrong_protection_and_busy_rejected(self):
        good = {'device_id':0x413,'cpuid':0x410fc241,'capacity_kib':1024,
                'optcr':0xaa00,'flash_sr':0,'uid_hex':'01'*12}
        for key,value,reason in [('device_id',0,'DEVICE_ID_MISMATCH'),
                                 ('optcr',0xcc00,'RDP_NOT_LEVEL_ZERO'),
                                 ('flash_sr',0x10000,'FLASH_BUSY_OR_ERROR'),
                                 ('uid_hex','00'*12,'INVALID_UID')]:
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError,reason):
                    check_identity(dict(good,**{key:value}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
