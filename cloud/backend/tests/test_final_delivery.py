"""F1/F3关键失败边界：只有合成内存和tmp目录，没有真实开发板或服务器。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import pytest

from cloud.deploy.h3 import recovery_bundle as bundle
from cloud.deploy.h3 import runtime_package
from gateway.physical_can.bench import final_a


def test_wrong_a_candidate_never_opens_debugger(tmp_path):
    image=tmp_path/'image.bin';image.write_bytes(b'wrong image')
    with pytest.raises(ValueError,match='NEW_A_IMAGE_MISMATCH'):final_a.plan(image)


def test_a_contract_signature_does_not_authorize_flash(a_window):
    image,_,_=a_window
    with pytest.raises(ValueError,match='OWNER_WINDOW_REQUIRED'):
        final_a.authorize({'auth_id':'CONTRACT_SIGNED'},'program',image)


class FakeBridge:
    def __init__(self, memory, uid, double_mismatch=False, outside_corrupt=False):
        self.memory=memory;self.uid=uid;self.flash_reads=0;self.loads=0
        self.double_mismatch=double_mismatch;self.outside_corrupt=outside_corrupt
    def execute(self, lines):
        # 仿真只实现测试所需的J-Link读写效果，绝不调用Bridge实际进程。
        for line in lines:
            if line.startswith('loadbin '):
                self.loads+=1
                path=line[len('loadbin '):].split(',')[0]
                value=Path(path).read_bytes();self.memory=value+b'\xff'*(final_a.BOUND-len(value))+self.memory[final_a.BOUND:]
                if self.outside_corrupt:self.memory=self.memory[:-1]+b'!'
            if not line.startswith('savebin '):continue
            path,address,length=line[len('savebin '):].split(', ')
            address,length=int(address,16),int(length,16)
            values={0xE0042000:(0x413).to_bytes(4,'little'),0x1FFF7A22:(1024).to_bytes(2,'little'),
                0x1FFF7A10:self.uid,0x1FFFC000:b'\xff'*16,0x40023C14:(0xAA00).to_bytes(4,'little'),
                0xE0042008:b'\0'*4}
            if address==final_a.FLASH:
                self.flash_reads+=1;value=self.memory
                if self.double_mismatch and self.flash_reads==2:value=b'!'+value[1:]
            else:value=values[address]
            Path(path).write_bytes(value[:length])


@pytest.fixture
def a_window(tmp_path,monkeypatch):
    # 使用合成镜像，并把摘要门映射到合成值；真实候选门另由离线计划检查冻结SHA。
    image=tmp_path/'new.bin'
    image.write_bytes((0x20002000).to_bytes(4,'little')+(0x080001A1).to_bytes(4,'little')+b'N'*(50084-8))
    old=b'O'*49888;memory=old+b'\xff'*(final_a.SIZE-len(old))
    monkeypatch.setattr(final_a,'IMAGE_SHA',final_a.sha(image.read_bytes()))
    monkeypatch.setattr(final_a,'OLD_SHA',final_a.sha(old))
    directory=tmp_path/'window';directory.mkdir()
    return image,directory,memory


def test_fresh_a_double_backup_and_outside_sector_protection(a_window):
    image,directory,memory=a_window;uid=b'A'*12
    bridge=FakeBridge(memory,uid)
    report=final_a.Window(directory,bridge,uid).program(image)
    assert report['exit_code']==0 and bridge.loads==1
    assert (directory/'first-flash.bin').read_bytes()==memory
    assert report['outside_sectors_unchanged'] and report['normal_cold_boot']=='NOT_OBSERVED'


@pytest.mark.parametrize('reason',['uid','backup','old_application'])
def test_a_prewrite_failure_never_loads(a_window,reason):
    image,directory,memory=a_window;uid=b'A'*12
    if reason=='old_application':memory=b'?'+memory[1:]
    bridge=FakeBridge(memory,b'C'*12 if reason=='uid' else uid,double_mismatch=reason=='backup')
    with pytest.raises(RuntimeError):final_a.Window(directory,bridge,uid).program(image)
    assert bridge.loads==0


def test_a_outside_range_corruption_stops_without_auto_restore(a_window):
    image,directory,memory=a_window;uid=b'A'*12
    bridge=FakeBridge(memory,uid,outside_corrupt=True)
    with pytest.raises(RuntimeError,match='OUTSIDE_SECTORS'):final_a.Window(directory,bridge,uid).program(image)
    assert bridge.loads==1 and (directory/'fresh-backup.json').exists()


def test_a_restore_uses_only_new_window_64k_original(a_window,tmp_path):
    image,directory,memory=a_window;uid=b'A'*12
    bridge=FakeBridge(memory,uid)
    final_a.Window(directory,bridge,uid).program(image)
    restoring=tmp_path/'restore';restoring.mkdir()
    report=final_a.Window(restoring,bridge,uid).restore(directory,final_a.sha(memory))
    assert report['exit_code']==0 and bridge.memory==memory
    assert (restoring/'restore-sector0-3.bin').stat().st_size==65536


def test_a_restore_refuses_changed_protected_area(a_window,tmp_path):
    image,directory,memory=a_window;uid=b'A'*12
    bridge=FakeBridge(memory,uid)
    final_a.Window(directory,bridge,uid).program(image)
    bridge.memory=bridge.memory[:-1]+b'!'
    restoring=tmp_path/'restore';restoring.mkdir()
    with pytest.raises(RuntimeError,match='OUTSIDE_SCOPE_CHANGED'):
        final_a.Window(restoring,bridge,uid).restore(directory,final_a.sha(memory))
    assert bridge.loads==1


def make_bundle(tmp_path):
    live=tmp_path/'live';live.mkdir();spec=[]
    for role in sorted(bundle.ROLES):
        path=live/role
        if role.endswith('TREE') or role=='STATE':
            path.mkdir();(path/'data').write_bytes(role.encode());(path/'data').chmod(0o600)
        else:path.write_bytes(role.encode())
        spec.append({'role':role,'path':str(path)})
    target=tmp_path/'backup';receipt=bundle.create(spec,target)
    return spec,target,receipt


def test_full_backup_covers_all_roles_and_restores_extra_files(tmp_path):
    spec,target,receipt=make_bundle(tmp_path)
    web=Path(next(s['path'] for s in spec if s['role']=='WEB_TREE'))
    (web/'data').write_text('new revision');(web/'extra').write_text('new extra')
    current={s['path']:bundle.inventory(s['path']) for s in spec}
    result=bundle.restore(target,receipt['manifest_sha256'],True,current)
    assert result['objects']==len(spec) and (web/'data').read_text()=='WEB_TREE'
    assert not (web/'extra').exists()


def test_damaged_backup_and_unknown_current_block_before_replace(tmp_path):
    spec,target,receipt=make_bundle(tmp_path)
    with pytest.raises(RuntimeError,match='CURRENT_STATE_CHANGED'):
        bundle.restore(target,receipt['manifest_sha256'],True,{})
    obj=next((target/'objects').iterdir());obj.write_text('corrupt')
    with pytest.raises(RuntimeError,match='OBJECT_CHANGED'):bundle.verify(target,receipt['manifest_sha256'])


def test_incomplete_four_file_backup_rejected(tmp_path):
    with pytest.raises(ValueError,match='COMPLETE_RECOVERY_ROLES'):
        bundle.create([{'role':'ENV','path':str(tmp_path/'env')}],tmp_path/'backup')


def test_restore_midway_failure_puts_every_current_original_back(tmp_path,monkeypatch):
    spec,target,receipt=make_bundle(tmp_path)
    current={s['path']:bundle.inventory(s['path']) for s in spec}
    replace=os.replace;count=0
    def fail_once(src,dst):
        nonlocal count
        count+=1
        if count==4:raise OSError('synthetic rename failure')
        return replace(src,dst)
    monkeypatch.setattr(bundle.os,'replace',fail_once)
    with pytest.raises(OSError,match='synthetic rename'):
        bundle.restore(target,receipt['manifest_sha256'],True,current)
    assert all(bundle.inventory(s['path'])==current[s['path']] for s in spec)


@pytest.mark.skipif(os.name=='nt',reason='POSIX symlink/ownership metadata verified in Linux offline run')
def test_symlink_metadata_without_following_target(tmp_path):
    spec,target,receipt=make_bundle(tmp_path)
    link=Path(next(s['path'] for s in spec if s['role']=='RELEASE_LINK'))
    link.unlink();link.symlink_to('relative-old-release')
    other=tmp_path/'linkbackup';proof=bundle.create(spec,other)
    saved=bundle.verify(other,proof['manifest_sha256'])
    assert next(o for o in saved['objects'] if o['role']=='RELEASE_LINK')['entries']['.']['target']=='relative-old-release'


def test_runtime_rejects_missing_complete_manifest(tmp_path):
    (tmp_path/'H3_RUNTIME_SOURCE.json').write_text(json.dumps({'schema':1,'critical_source_sha256':{}}))
    with pytest.raises(ValueError,match='COMPLETE_NEW_RUNTIME'):runtime_package.verify(tmp_path)


def test_runtime_hashes_entire_dist_and_rejects_added_files(tmp_path):
    hashes={}
    for name in runtime_package.REQUIRED:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic')
        hashes[name]=runtime_package.digest(p.read_bytes())
    data={'schema':2,'critical_source_sha256':hashes,'backend_session_fix_present':True,
          'persistent_usage_ledger':True,'payload_sha256':runtime_package.digest(json.dumps(hashes,sort_keys=True).encode())}
    (tmp_path/'H3_RUNTIME_SOURCE.json').write_text(json.dumps(data))
    runtime_package.verify(tmp_path)
    (tmp_path/'unlisted.js').write_text('injected asset')
    with pytest.raises(ValueError,match='UNMANIFESTED'):runtime_package.verify(tmp_path)
    (tmp_path/'unlisted.js').unlink()
    (tmp_path/'cloud/web/dist/index.html').write_text('changed approved asset')
    with pytest.raises(ValueError,match='FILE_CHANGED'):runtime_package.verify(tmp_path)
