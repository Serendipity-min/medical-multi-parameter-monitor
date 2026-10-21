"""正式台架下载仍使用原事务；验证端口/来源隔离和commit最后写，不操作设备。"""
from datetime import datetime,timedelta,timezone
import pytest
from gateway.physical_can import r2_flash_c as gate
from gateway.physical_can.tests.test_r2_persistent_download import fixture_inputs,baseline,rom


def formal_inputs():
    manifest,image,record=fixture_inputs()
    manifest.update(compiled_MQTT_port=8883,synthetic_source=True)
    manifest['commands']=[['gcc','-DMP_H3_TEST_SOURCE','-DMP_H3_PERSISTENT_CONFIG']]
    return manifest,image,record


@pytest.mark.parametrize('fault',['port','source','clock','port_override','source_flag'])
def test_formal_profile_rejects_inconsistent_build_before_erasing(rom,fault):
    m,image,record=formal_inputs();b,backup=baseline(rom)
    if fault=='port':m['compiled_MQTT_port']=8884
    if fault=='source':m['synthetic_source']=False
    if fault=='clock':m['fresh_sntp']=False
    if fault=='port_override':m['commands'][0].append('-DMP_MQTT_TLS_PORT=8884')
    if fault=='source_flag':m['commands'][0].remove('-DMP_H3_TEST_SOURCE')
    with pytest.raises(gate.GateError):gate.program(rom,m,image,record,b,backup,lambda *a:None,'formal-synthetic')
    assert not rom.erases and not rom.writes


def test_formal_program_retains_transaction_and_requires_explicit_profile(rom):
    m,image,record=formal_inputs();b,backup=baseline(rom)
    # 默认隔离入口拒绝正式镜像；显式正式入口仍先核对原件再写0..2、3及commit。
    with pytest.raises(gate.GateError):gate.offline_plan(m,image,record)
    result=gate.program(rom,m,image,record,b,backup,lambda *a:None,'formal-synthetic')
    assert result['exit_code']==0 and rom.erases==[[0,1,2],[3]]
    assert rom.writes[-1]==(gate.CONFIG+20,record[20:24])
    assert bytes(rom.memory)==image.ljust(gate.CONFIG-gate.START,b'\xff')+record.ljust(0x4000,b'\xff')


def test_formal_window_cannot_reuse_isolated_port_approval():
    m,image,record=formal_inputs();p=gate.offline_plan(m,image,record,'formal-synthetic')
    w={'role':'C','port':'COM15','source_commit':'synthetic','actions':['program'],
       'expires_utc':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(),
       'erase_sectors':[0,1,2,3],'image_sha256':p['image_sha256'],
       'record_sha256':p['record_sha256'],'identity_source_sha256':'synthetic-identity','mqtt_tls_port':8884}
    with pytest.raises(gate.GateError):gate.check_window(w,'program',p,'synthetic','synthetic-identity')
    w['mqtt_tls_port']=8883
    gate.check_window(w,'program',p,'synthetic','synthetic-identity')
