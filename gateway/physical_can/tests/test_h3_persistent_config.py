"""真实记录验证器的掉电重载/部分写入/损坏门禁，仅用合成凭据，绝不访问设备。"""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]


def test_reload_partial_corrupt_and_legacy_record(tmp_path):
    source=tmp_path/'record.c'
    source.write_text(r'''
#include "persistent_config.h"
#include <assert.h>
#include <stdio.h>
static H3ConfigRecord good(void) {
    H3ConfigRecord r={0};r.magic=H3_CONFIG_RECORD_MAGIC;r.version=1;r.header_bytes=24;
    r.payload_bytes=312;r.generation=1;r.committed=H3_CONFIG_COMMITTED;
    r.payload=(GatewayConfig){GATEWAY_CONFIG_MAGIC,1700000000u,"synthetic-wifi","synthetic-password",
        "mqtt.example.invalid","synthetic-user","synthetic-secret","synthetic-client"};
    r.crc32=h3_config_crc(&r);return r;
}
int main(void) {
    H3ConfigRecord disk=good(),loaded;memcpy(&loaded,&disk,sizeof(loaded));
    assert(h3_config_record_valid(&loaded));
    /* 正常复位/反复重连只能读，不得擦写或改变已提交记录。 */
    for(unsigned i=0;i<100;i++){memcpy(&loaded,&disk,sizeof(loaded));assert(h3_config_record_valid(&loaded));}
    assert(!memcmp(&disk,&loaded,sizeof(disk)));
    for(size_t cut=0;cut<sizeof(disk);cut++) {
        memset(&loaded,255,sizeof(loaded));memcpy(&loaded,&disk,cut);
        assert(!h3_config_record_valid(&loaded));
    }
    /* 任何一位损坏都不能悄悄回退旧RAM或受保护扇区。 */
    for(size_t at=0;at<sizeof(disk);at++)for(unsigned bit=0;bit<8;bit++) {
        loaded=disk;((unsigned char *)&loaded)[at]^=(unsigned char)(1u<<bit);
        assert(!h3_config_record_valid(&loaded));
    }
    memset(&loaded,255,sizeof(loaded));assert(!h3_config_record_valid(&loaded));
    loaded=good();loaded.committed=0xFFFFFFFFu;assert(!h3_config_record_valid(&loaded));
    loaded=good();loaded.version=2;loaded.crc32=h3_config_crc(&loaded);assert(!h3_config_record_valid(&loaded));
    loaded=good();loaded.payload.minimum_epoch=0;loaded.crc32=h3_config_crc(&loaded);assert(!h3_config_record_valid(&loaded));
    loaded=good();memset(loaded.payload.host,'x',sizeof(loaded.payload.host));loaded.crc32=h3_config_crc(&loaded);assert(!h3_config_record_valid(&loaded));
    loaded=good();loaded.payload.ssid[0]='"';loaded.crc32=h3_config_crc(&loaded);assert(!h3_config_record_valid(&loaded));
    loaded=good();loaded.generation=0;loaded.crc32=h3_config_crc(&loaded);assert(!h3_config_record_valid(&loaded));
    /* 原312B布局不升级为新记录；恢复旧应用只能回到其原本的配置路径。 */
    memset(&loaded,0,sizeof(loaded));memcpy(&loaded,&disk.payload,312);assert(!h3_config_record_valid(&loaded));
    puts("PASS reload repeated-read partial-write bit-corruption erased uncommitted version epoch fields legacy");
}
''',encoding='utf-8')
    built=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'gateway/mqtt/src'),str(source),'-o',str(tmp_path/'record.exe')],capture_output=True,text=True)
    assert built.returncode==0,built.stderr
    executed=subprocess.run([str(tmp_path/'record.exe')],capture_output=True,text=True)
    assert executed.returncode==0,executed.stdout+executed.stderr
