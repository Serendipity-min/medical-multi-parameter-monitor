"""验证C恢复的拒绝路径：任何原件不符都不能写RAM或执行GO。"""
from unittest.mock import Mock, patch
import pytest
from gateway.physical_can import h3_resume_c as resume
from gateway.physical_can import h3_flash_c as download


@pytest.mark.parametrize('failure', [None, 'options', 'protected', 'application', 'ram'])
def test_resume_rejects_changed_board_before_execution(failure):
    options = bytes([0, 0xAA])+bytes(14)
    baseline = {'options_sha256': resume.sha(options), 'protected': {'sector7': 'unchanged', 'sector11': 'unchanged'}}
    boot = Mock()
    # 固定合成字节只测试恢复门禁；不读取凭据或连接串口/板卡。
    image, config = b'test-image', b'test-config'
    reads = [options if failure != 'options' else bytes(16),
             image if failure != 'application' else b'changed',
             config if failure != 'ram' else b'changed']
    protected = {} if failure == 'protected' else baseline['protected']
    with patch.object(resume, 'read_exact', side_effect=reads), patch.object(resume, 'protected_hashes', return_value=protected):
        if failure:
            with pytest.raises(resume.GateError):
                resume.resume_verified(boot, image, config, baseline)
            boot.go.assert_not_called()
        else:
            assert resume.resume_verified(boot, image, config, baseline)['go_sent']
            boot.go.assert_called_once_with(0x08000000)
    # 仅允许已预留SRAM；无论成功失败都不得调用Flash擦除接口。
    if failure in ('options', 'protected', 'application'):
        boot.write_memory_data.assert_not_called()
    else:
        boot.write_memory_data.assert_called_once_with(0x2001FE00, config)
    boot.extended_erase_memory.assert_not_called()


@pytest.mark.parametrize('changed', [False, True])
def test_read_current_candidate_requires_receipt_hash(tmp_path, changed):
    image = b'known-image'
    receipt = {'image': {'bytes': len(image), 'sha256': download.sha(image)}}
    destination = tmp_path/'candidate.bin'
    boot = Mock()
    with patch.object(download, 'PRIVATE', tmp_path), patch.object(download, 'read_exact', return_value=b'unknown-img' if changed else image):
        if changed:
            with pytest.raises(download.GateError):
                download.read_current_candidate(boot, receipt, destination)
            assert not destination.exists()
        else:
            assert download.read_current_candidate(boot, receipt, destination) == image
            assert destination.read_bytes() == image
    boot.write_memory_data.assert_not_called()
    boot.extended_erase_memory.assert_not_called()
