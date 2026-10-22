"""只对新语音topic改变权限，既有遥测行逐字保留。"""
import pytest
from cloud.deploy.voice_window import scoped_acl,TOPIC


def test_scoped_acl_only_adds_exact_topic_and_preserves_old_telemetry():
    text='user oldpub\ntopic write mpm/v1/GW-C-001/#\n\nuser oldreader\ntopic read mpm/v1/GW-C-001/#\n\nuser current\ntopic write mpm/v1/GW-C-001/NODE-A/telemetry/+\n'
    new,count=scoped_acl(text,'current','trialpub')
    assert count==2 and new.count('topic deny '+TOPIC)==2
    assert 'topic read '+TOPIC in new and 'user trialpub\ntopic write '+TOPIC in new
    assert all(line in new for line in text.splitlines() if line)
    assert new.count('#')==2


@pytest.mark.parametrize('text', ['user other\ntopic write x\n','user current\ntopic read '+TOPIC+'\n','user current\nuser trialpub\n'])
def test_ambiguous_or_existing_voice_changes_stop(text):
    with pytest.raises(ValueError):scoped_acl(text,'current','trialpub')
