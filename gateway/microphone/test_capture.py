"""只检验实际导出校验器；合成PCM不作为麦克风实测。"""
import copy
import math
import struct
import unittest
import zlib
from capture import analyze


class ExportChecks(unittest.TestCase):
    def setUp(self):
        self.pcm=struct.pack('<32000h',*[int(2000*math.sin(i*2*math.pi/16)) for i in range(32000)])
        self.meta={'state':2,'frames':32000,'rate':16000,'bytes':64000,'crc32':zlib.crc32(self.pcm),
                   'dma_errors':0,'overruns':0,'fault_flags':0,'blocks':250,'cpu_hz':8000000,
                   'irq_cycles':[i*80000 for i in range(250)],'left_abs':40000000,'right_abs':0,
                   'zero24':0,'clip24':0,'PLLCFGR':(1<<22)|8,
                   'PLLI2SCFGR':(256<<6)|(5<<28),'I2SPR':25,'I2SCFGR':0xb03}
    def test_valid_packet_and_cycle_wrap(self):
        self.assertAlmostEqual(analyze(self.meta,self.pcm)['IRQ_rate_from_declared_HSE_Hz'],16000)
        self.meta['irq_cycles']=[(t+0xffff0000)&0xffffffff for t in self.meta['irq_cycles']]
        self.assertAlmostEqual(analyze(self.meta,self.pcm)['duration_s'],2)
    def test_bad_data_or_count(self):
        for pcm in (self.pcm[:-2],b'\x01'+self.pcm[1:]):
            with self.assertRaises(ValueError):analyze(self.meta,pcm)
        for key,value in (('state',3),('frames',31999),('overruns',1),('dma_errors',1),('fault_flags',4),('blocks',249)):
            m=copy.deepcopy(self.meta);m[key]=value
            with self.assertRaises(ValueError):analyze(m,self.pcm)
    def test_wrong_slot_or_stalled_DMA(self):
        for changes in ({'left_abs':0},{'right_abs':50000000},{'zero24':32000},
                        {'I2SPR':24},{'I2SCFGR':0xa03},
                        {'irq_cycles':[i*160000 for i in range(250)]}):
            m=copy.deepcopy(self.meta);m.update(changes)
            with self.assertRaises(ValueError):analyze(m,self.pcm)


if __name__=='__main__':unittest.main()
