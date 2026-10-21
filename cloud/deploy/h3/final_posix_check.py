"""Linux本机文件恢复验证；仅用stdlib临时目录，不接触云服务或开发板。"""
import json
import os
from pathlib import Path
import tempfile
from . import recovery_bundle as bundle


def main():
    if os.name != 'posix':
        raise RuntimeError('POSIX_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='mpm-ac-final-') as temporary:
        root=Path(temporary);live=root/'live';live.mkdir();spec=[]
        for role in sorted(bundle.ROLES):
            p=live/role
            if role.endswith('TREE') or role=='STATE':
                p.mkdir();(p/'data').write_bytes(role.encode());(p/'data').chmod(0o600)
            elif role=='RELEASE_LINK':p.symlink_to('WEB_TREE')
            else:p.write_text(role);p.chmod(0o640)
            spec.append({'role':role,'path':str(p)})
        os.setxattr(live/'WEB_TREE/data','user.h3',b'synthetic-attribute')
        result=bundle.create(spec,root/'bundle')
        web=live/'WEB_TREE';(web/'data').write_text('new version');(web/'newfile').write_text('new asset')
        (live/'RELEASE_LINK').unlink();(live/'RELEASE_LINK').symlink_to('AI_TREE')
        current={s['path']:bundle.inventory(s['path']) for s in spec}
        bundle.restore(root/'bundle',result['manifest_sha256'],True,current)
        assert (web/'data').read_text()=='WEB_TREE' and not (web/'newfile').exists()
        assert (web/'data').stat().st_mode&0o777==0o600
        assert os.readlink(live/'RELEASE_LINK')=='WEB_TREE'
        assert (web/'data').stat().st_uid==os.getuid()
        assert os.getxattr(web/'data','user.h3')==b'synthetic-attribute'
        print(json.dumps({'exit_code':0,'platform':'POSIX_LOCAL_TMP_ONLY',
            'checks':['COMPLETE_ROLE_OBJECTS','CONTENTS','EXTRA_FILE_REMOVAL','MODE_UID_GID','XATTR','SYMLINK_NO_DEREFERENCE'],
            'actual_server_rollback':'NOT_RUN'}))
    return 0


if __name__=='__main__':raise SystemExit(main())
