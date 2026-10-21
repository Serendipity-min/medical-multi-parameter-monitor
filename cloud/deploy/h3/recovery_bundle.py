"""完整原件快照与受限恢复组件；调用者负责取得服务器写入/恢复授权。

不启动服务、不调整网络；只接受显式对象清单。普通发布回退优先保持旧服务
和源树原位，完整恢复仅在独立批准的修复窗口调用，绝不自动覆盖未知变更。
"""
import hashlib
import base64
import json
import os
from pathlib import Path
import shutil
import stat
import uuid

ROLES = {'WEB_TREE', 'BACKEND_TREE', 'AI_TREE', 'STATE', 'UNIT', 'ENV', 'NGINX',
         'BROKER', 'EXECUTABLE', 'RELEASE_LINK'}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def inventory(path):
    result = {}

    def walk(p, name):
        s = p.lstat()
        item = {'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid,
                'mtime_ns': s.st_mtime_ns}
        # POSIX ACL/扩展属性属于权限原件；仅进入私有manifest，不出现在脱敏回执。
        if hasattr(os,'listxattr'):
            item['xattrs']={key:base64.b64encode(os.getxattr(p,key,follow_symlinks=False)).decode()
                for key in os.listxattr(p,follow_symlinks=False)}
        if stat.S_ISLNK(s.st_mode):
            item.update(kind='link', target=os.readlink(p))
        elif stat.S_ISDIR(s.st_mode):
            item['kind'] = 'directory'
        elif stat.S_ISREG(s.st_mode):
            item.update(kind='file', bytes=s.st_size, sha256=digest(p))
        else:
            raise ValueError('SPECIAL_FILE_NOT_SUPPORTED')
        result[name] = item
        # 不跟随符号链接；其实际目标必须作为独立显式备份对象，避免越界遍历。
        if item['kind'] == 'directory':
            for child in sorted(p.iterdir()):
                walk(child, child.name if name == '.' else name + '/' + child.name)
    walk(Path(path), '.')
    return result


def create(specs, bundle):
    bundle = Path(bundle)
    if {s['role'] for s in specs} != ROLES:
        raise ValueError('COMPLETE_RECOVERY_ROLES_REQUIRED')
    paths = [Path(s['path']).absolute() for s in specs]
    if len(set(paths)) != len(paths) or any(p == bundle or p in bundle.parents for p in paths):
        raise ValueError('BACKUP_OVERLAP')
    if any(a in b.parents for a in paths for b in paths if a != b):
        raise ValueError('NESTED_ROOTS_MUST_BE_DEDUPLICATED')
    bundle.mkdir(mode=0o700, parents=False, exist_ok=False)
    objects = bundle / 'objects'; objects.mkdir(mode=0o700)
    manifest = {'schema': 2, 'objects': [], 'roles': sorted(ROLES), 'state': 'INCOMPLETE'}
    for spec, source in zip(specs, paths):
        entries = inventory(source)
        for name, item in entries.items():
            if item['kind'] != 'file':
                continue
            destination = objects / item['sha256']
            if not destination.exists():
                with destination.open('xb') as output, (source if name == '.' else source / name).open('rb') as f:
                    shutil.copyfileobj(f, output)
                    output.flush(); os.fsync(output.fileno())
                destination.chmod(0o600)
            if digest(destination) != item['sha256']:
                raise RuntimeError('BACKUP_OBJECT_CHANGED')
        if inventory(source) != entries:
            raise RuntimeError('LIVE_SOURCE_CHANGED_BACKUP_INCOMPLETE')
        manifest['objects'].append({'role': spec['role'], 'path': str(source), 'entries': entries})
    # 全部对象二次核对，持久状态活跃变化时直接阻断，不能声明一致快照。
    for obj in manifest['objects']:
        if inventory(obj['path']) != obj['entries']:
            raise RuntimeError('LIVE_SOURCE_CHANGED_BACKUP_INCOMPLETE')
    manifest['state'] = 'VERIFIED_COMPLETE'
    target = bundle / 'manifest.json'
    with target.open('x') as f:
        json.dump(manifest, f, sort_keys=True, indent=2)
        f.flush(); os.fsync(f.fileno())
    target.chmod(0o600)
    verify(bundle, digest(target))
    return {'path': str(bundle), 'manifest_sha256': digest(target), 'schema': 2,
            'state': 'VERIFIED_COMPLETE', 'role_count': len(ROLES)}


def verify(bundle, expected_sha, current=False):
    bundle = Path(bundle)
    if digest(bundle / 'manifest.json') != expected_sha:
        raise RuntimeError('RECOVERY_MANIFEST_CHANGED')
    data = json.loads((bundle / 'manifest.json').read_text())
    if data.get('schema') != 2 or data.get('state') != 'VERIFIED_COMPLETE' or set(data['roles']) != ROLES:
        raise RuntimeError('COMPLETE_RECOVERY_REQUIRED')
    for obj in data['objects']:
        for item in obj['entries'].values():
            if item['kind'] == 'file' and digest(bundle / 'objects' / item['sha256']) != item['sha256']:
                raise RuntimeError('RECOVERY_OBJECT_CHANGED')
        if current and inventory(obj['path']) != obj['entries']:
            raise RuntimeError('ORIGINAL_TREE_DRIFT_REQUIRES_OWNER_REPAIR_WINDOW')
    return data


def materialize(obj, target, bundle):
    for name, item in sorted(obj['entries'].items(), key=lambda pair: (pair[0].count('/'), pair[0])):
        p = target if name == '.' else target / name
        if item['kind'] == 'directory':
            p.mkdir(mode=0o700)
        elif item['kind'] == 'link':
            p.symlink_to(item['target'])
        else:
            shutil.copyfile(Path(bundle) / 'objects' / item['sha256'], p)
    # 子文件先恢复，目录时间戳最后恢复；链接本身不chmod，避免触及目标。
    for name, item in sorted(obj['entries'].items(), reverse=True):
        p = target if name == '.' else target / name
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            os.chown(p, item['uid'], item['gid'], follow_symlinks=False)
        if item['kind'] != 'link':
            p.chmod(item['mode'])
            os.utime(p, ns=(item['mtime_ns'], item['mtime_ns']))
        for key,value in item.get('xattrs',{}).items():
            os.setxattr(p,key,base64.b64decode(value),follow_symlinks=False)


def restore(bundle, expected_sha, owner_approved=False, expected_current=None):
    if not owner_approved or expected_current is None:
        raise ValueError('EXPLICIT_RESTORE_WINDOW_AND_CURRENT_INVENTORY_REQUIRED')
    data = verify(bundle, expected_sha)
    for obj in data['objects']:
        if inventory(obj['path']) != expected_current.get(obj['path']):
            raise RuntimeError('RESTORE_CURRENT_STATE_CHANGED')
    staged, moved = [], []
    try:
        # 先把所有原件重建在各自同文件系统中，全部校验后才开始交换。
        for obj in data['objects']:
            path = Path(obj['path'])
            temp = path.with_name(path.name + '.h3-restore-' + uuid.uuid4().hex)
            staged.append((path, temp))
            materialize(obj, temp, bundle)
            actual = inventory(temp)
            # 链接mtime不可移植，不影响目标/权限/内容的身份校验。
            for key in actual:
                if actual[key]['kind'] == 'link':
                    actual[key]['mtime_ns'] = obj['entries'][key]['mtime_ns']
            if actual != obj['entries']:
                raise RuntimeError('RESTORE_STAGING_MISMATCH')
        for path, temp in staged:
            if inventory(path)!=expected_current[str(path)]:
                raise RuntimeError('RESTORE_CURRENT_CHANGED_DURING_STAGING')
            displaced = path.with_name(path.name + '.h3-displaced-' + uuid.uuid4().hex)
            os.replace(path, displaced)
            moved.append((path, displaced))
            os.replace(temp, path)
    except BaseException:
        # 失败按相反顺序恢复原当前态；保留所有被替换件，不递归删除现场原件。
        for path, displaced in reversed(moved):
            if path.exists() or path.is_symlink():
                os.replace(path, path.with_name(path.name + '.h3-failed-' + uuid.uuid4().hex))
            os.replace(displaced, path)
        raise
    return {'state': 'RESTORED_FILES_SERVICE_RESTART_AND_HTTPS_PENDING',
            'displaced_originals_retained': True, 'objects': len(staged)}
