"""低开销UART仅离线验证：真实MEM-AP包装器+假DLL。"""
import ctypes as C
import io
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_esp_fast_uart as f
from b5_esp_budget import CommandBudget


def link_fake(command):
    link=object.__new__(f.FastLink);link.READ_SCOPE={a:set(n) for a,n in f.u.READS.items() if a!=f.q.RING}
    link.BYTE_COMMANDS=(command,);link.byte_grant=f.q.ByteGrant((command,));link.byte_grant.cleanup_started=False
    link.query_before_verified=True;link.native_UART_writes=0;link.sdk_calls=0;link.sdk_limit=10000;link.error=False
    link.dap_select=0;link.dap_csw=2;link.dap_tar=0x40023c10;link.raw_target_grant=None;link.gate=Mock()
    link.io=io.StringIO();link.events=io.StringIO();link.memory_counts={}
    def read(reg,ap,ptr):
        value=link.dap_csw if reg==0 else link.dap_tar if reg==1 else 1<<7
        C.cast(ptr,C.POINTER(C.c_uint32)).contents.value=value
        return 0
    link.dll=types.SimpleNamespace(JLINKARM_CORESIGHT_ReadAPDPReg=Mock(side_effect=read),JLINKARM_CORESIGHT_WriteAPDPReg=Mock(return_value=0))
    return link


class Tests(unittest.TestCase):
    def test_real_native_wrapper_four_calls_per_byte_and_context_restore(self):
        command=bytes(range(48));link=link_fake(command);budget=CommandBudget(link,())
        budget.admit(command,2);link.byte_grant.begin(command)
        bridge=f.FastBridge(f.q.site.config.NativeBus(link));bridge.proven=True;bridge.guard=link.byte_grant.check
        old=(link.dap_csw,link.dap_tar)
        bridge.write_command(link,command,budget,2)
        self.assertEqual(link.sdk_calls,10+4*len(command));self.assertEqual(link.native_UART_writes,48)
        self.assertEqual(bytes(link.byte_grant.history),command);self.assertEqual((link.dap_csw,link.dap_tar),old)
        self.assertTrue(bridge.state_restored);self.assertIsNone(link.raw_target_grant)
    def test_TX_not_ready_zero_bytes_no_unsafe_extra_poll(self):
        command=b'AT\r\n';link=link_fake(command)
        def read(reg,ap,ptr):
            C.cast(ptr,C.POINTER(C.c_uint32)).contents.value=2 if reg==0 else 0
            return 0
        link.dll.JLINKARM_CORESIGHT_ReadAPDPReg.side_effect=read
        budget=CommandBudget(link,());budget.admit(command,2);link.byte_grant.begin(command)
        bridge=f.FastBridge(f.q.site.config.NativeBus(link));bridge.proven=True;bridge.guard=link.byte_grant.check
        with patch.object(f.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'TX_NOT_READY'):bridge.write_command(link,command,budget,2)
        self.assertEqual(link.native_UART_writes,0);self.assertTrue(bridge.state_restored)
    def test_no_UID_Flash_UART_DR_or_full_ring_read_scope(self):
        link=link_fake(b'AT\r\n')
        for address,size in [(0x1fff7a10,12),(0x08000000,64),(f.q.DR,4),(f.q.RING,8192)]:
            with self.assertRaises(ValueError):link.read(address,size)
        self.assertFalse(link.raw_read_allowed(0x08000000));self.assertFalse(link.raw_read_allowed(f.q.DR))
        self.assertTrue(link.raw_read_allowed(f.q.UART))
    def test_delta_permission_stays_inside_ring_and_length_limit(self):
        link=link_fake(b'AT\r\n');link.allow_delta(f.q.RING+3,48)
        for address,size in [(f.q.RING-1,2),(f.q.RING,513),(f.q.RING+8190,3),(f.q.RING,0)]:
            with self.assertRaises(ValueError):link.allow_delta(address,size)
    def read_delta(self,before,after,baseline):
        counts=[];states=iter((struct.pack('<5I',0,0,0,0,before),struct.pack('<5I',0,0,0,0,after)))
        buffer=bytes(i%256 for i in range(f.q.CAPACITY))
        def delta(address,size):counts.append(size);return buffer[address-f.q.RING:address-f.q.RING+size]
        link=types.SimpleNamespace(read=lambda a,n:next(states),read_delta=delta)
        return f.ring_delta(link,(0,0,0,0,baseline)),counts,buffer
    def test_small_reply_reads_only_changed_bytes(self):
        data,sizes,buffer=self.read_delta(150,150,100)
        self.assertEqual(data,buffer[100:150]);self.assertEqual(sizes,[50])
    def test_wrap_reassembles_and_empty_ring_reads_no_data(self):
        data,sizes,buffer=self.read_delta(3,3,8190)
        self.assertEqual(data,buffer[8190:]+buffer[:3]);self.assertEqual(sizes,[2,3])
        data,sizes,_=self.read_delta(5,5,5);self.assertEqual(data,b'');self.assertEqual(sizes,[])
    def test_incoherent_snapshot_and_overflow_not_accepted(self):
        data,_,_=self.read_delta(150,151,100);self.assertIsNone(data)
        with self.assertRaisesRegex(ValueError,'OVERFLOW'):self.read_delta(600,600,0)
    def test_budget_includes_four_reads_on_wrap_and_cleanup_context(self):
        command=b'AT\r\n';link=types.SimpleNamespace(sdk_calls=0,sdk_limit=10000)
        budget=f.FastBudget(link,(b'AT+CIPCLOSE\r\n',));budget.admit(command,2)
        self.assertEqual(f.command_calls(command,2),1+16*len(command)+4*100+10)
        link.sdk_calls=link.sdk_limit-budget.cleanup_reserve-f.command_calls(command,2)+1
        with self.assertRaises(f.HostBudgetExhausted):budget.admit(command,2)


if __name__=='__main__':unittest.main()
