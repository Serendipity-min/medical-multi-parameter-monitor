"""真实Gateway协议/Adapter回归：连续上报不能刷新同一次NIBP的完成时间。"""
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    tmp_path=tmp_path_factory.mktemp('nibp_capture')
    source=tmp_path/'nibp.c'
    source.write_text(r'''
#include "physical.h"
#include "mp_adapter.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static MpStack s;static MpAdapter a;static MpRouter r;static unsigned valid,expired;
static void input(unsigned id,unsigned dlc,uint32_t x,uint32_t y) {
    MpCanFrame f={0};f.ident=id;f.dlc=dlc;memcpy(f.data,&x,4);memcpy(f.data+4,&y,4);physical_receive(&f);
}
int main(int argc,char **argv) {
    unsigned mode=argc>1?(unsigned)atoi(argv[1]):0;
    assert(!mp_stack_init(&s,1800000000u));physical_link_ready=true;
    mp_adapter_init(&a);mp_router_init(&r);mp_router_online(&r,true);
    input(0x701,1,0,0);
    for(unsigned at=0;at<98000;at++) {
        unsigned now=s.milliseconds+1;
        if(now%500==0)input(0x701,1,5,0);
        if(now%1000==0) {
            unsigned complete=now>=94000?94000:1000;
            unsigned ok=mode==4 || now<=91000 || now>=94000;
            input(0x681,8,(mode==5?0u:512u)|(ok?8u:0u),1);
            input(0x481,8,s.epoch+now/1000,now-now%1000);
            if(mode!=1)input(0x281,8,mode==3?now+2000:complete,(mode==2?1220u:1210u)|(790u<<16));
            input(0x381,8,0,1210u|(790u<<16));
        }
        mp_stack_tick(&s);mp_adapter_poll(&a,&s,&r);MpFrame f;
        while(mp_router_take(&r,&f,s.milliseconds)) {
            if(f.node==2)assert(f.stream==MP_NODE_STATUS && !f.valid);
            if(f.stream==MP_NIBP) {
                if(f.valid) {
                    uint64_t expected=1800000000000ULL+(now>=94000?94000u:1000u);
                    if(f.timestamp!=expected)return 7;
                    assert(f.synthetic && f.values[0]==1210 && f.values[1]==790);valid++;
                } else if(now>91000 && now<94000)expired++;
            }
            mp_router_ack(&r,&f,true);
        }
    }
    if(mode==0 || mode==4)assert(valid>30 && expired);else assert(!valid);
    mp_stack_close(&s);
    puts("PASS fixed-completion-UTC 90-second-expiry identical-result-new-completion B-OFFLINE");
}
''',encoding='utf-8')
    here=ROOT/'gateway/physical_can';co=ROOT/'gateway/canopen';vendor=ROOT/'gateway/third_party/CANopenNode'
    sources=[here/'src/stack.c',here/'src/adapter.c',co/'src/mp_can_driver.c',co/'src/mp_od.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',vendor/'CANopen.c',*sorted((vendor/'301').glob('*.c')),source]
    command=['gcc','-std=c11','-O1','-DCO_MULTIPLE_OD','-DMP_H3_TEST_SOURCE','-I'+str(here/'src'),'-I'+str(co/'src'),'-I'+str(vendor),*map(str,sources),'-o',str(tmp_path/'nibp.exe')]
    built=subprocess.run(command,capture_output=True,text=True)
    assert built.returncode==0,built.stderr
    return tmp_path/'nibp.exe'


@pytest.mark.parametrize('mode',[0,1,2,3,4,5])
def test_completion_timestamp_stays_fixed_until_next_result(binary,mode):
    # 缺元数据、跨PDO值不匹配、未来时间、伪有效旧值、旧协议都不能伪装有效新测量。
    run=subprocess.run([str(binary),str(mode)],capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr+' exit='+str(run.returncode)
