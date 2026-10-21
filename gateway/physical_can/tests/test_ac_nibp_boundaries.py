"""实际CANopen RPDO/Adapter的毫秒边界、回绕、丢帧和新启动隔离用例。"""
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def probe(tmp_path_factory):
    tmp=tmp_path_factory.mktemp('ac_nibp');source=tmp/'probe.c'
    source.write_text(r'''
#include "physical.h"
#include "mp_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void input(unsigned id,unsigned dlc,uint32_t x,uint32_t y){
 MpCanFrame f={0};f.ident=id;f.dlc=dlc;memcpy(f.data,&x,4);memcpy(f.data+4,&y,4);physical_receive(&f);
}
int main(int argc,char **argv){
 assert(argc==4);uint32_t age=(uint32_t)strtoul(argv[1],0,10),anchor=(uint32_t)strtoul(argv[2],0,10);
 unsigned mode=(unsigned)atoi(argv[3]);MpStack s;MpAdapter a;MpRouter r;
 assert(!mp_stack_init(&s,1800000000u));physical_link_ready=true;mp_adapter_init(&a);mp_router_init(&r);mp_router_online(&r,true);
 input(0x701,1,0,0);input(0x681,8,512u|8u,1);input(0x281,8,anchor-age,1170u|(770u<<16));
 /* 前1999ms只推进真实CANopen；在固定2000ms发布槽注入完成身份，确保90.001s不是秒级近似。 */
 for(unsigned i=0;i<1999;i++){if(i%500==0)input(0x701,1,5,0);mp_stack_tick(&s);}
 if(mode==4)input(0x701,1,0,0);
 input(0x701,1,5,0);input(0x681,8,(mode==3?0u:512u)|8u,1);
 input(0x481,8,mode==6?0u:1800000002u,anchor);
 if(mode!=1 && mode!=4 && mode!=5)input(0x281,8,mode==7?anchor+2000u:anchor-age,(mode==2?1180u:1170u)|(770u<<16));
 input(0x381,8,0,1170u|(770u<<16));mp_stack_tick(&s);mp_adapter_poll(&a,&s,&r);
 MpFrame f;unsigned seen=0,valid=0;
 while(mp_router_take(&r,&f,s.milliseconds)){
  if(f.node==2)assert(f.stream==MP_NODE_STATUS && !f.valid);
  if(f.stream==MP_NIBP){seen++;if(f.valid){valid++;assert(f.timestamp==1800000002000ULL-age);assert(f.values[0]==1170 && f.values[1]==770 && f.synthetic);}}
  mp_router_ack(&r,&f,true);
 }
 assert(valid==((mode==0 && age<=90000u)?1u:0u));if(mode==0)assert(seen==1);
 mp_stack_close(&s);puts("PASS exact NIBP age, wrapped A tick, metadata identity/freshness/boot and B OFFLINE");
}
''',encoding='utf-8')
    here=ROOT/'gateway/physical_can';co=ROOT/'gateway/canopen';vendor=ROOT/'gateway/third_party/CANopenNode'
    sources=[here/'src/stack.c',here/'src/adapter.c',co/'src/mp_can_driver.c',co/'src/mp_od.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',vendor/'CANopen.c',*sorted((vendor/'301').glob('*.c')),source]
    command=['gcc','-std=c11','-O1','-DCO_MULTIPLE_OD','-DMP_H3_TEST_SOURCE','-I'+str(here/'src'),'-I'+str(co/'src'),'-I'+str(vendor),*map(str,sources),'-o',str(tmp/'probe.exe')]
    built=subprocess.run(command,capture_output=True,text=True);assert built.returncode==0,built.stderr
    return tmp/'probe.exe'


@pytest.mark.parametrize('age',[89000,90000,90001])
@pytest.mark.parametrize('anchor',[1234,0xFFFFFFF0])
def test_actual_adapter_exact_expiry_and_A_tick_wrap(probe,age,anchor):
    result=subprocess.run([str(probe),str(age),str(anchor),'0'],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('mode',[1,2,3,4,5,6,7])
def test_actual_adapter_rejects_missing_mismatch_legacy_boot_stale_clock_future(probe,mode):
    result=subprocess.run([str(probe),'89000','1234',str(mode)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
