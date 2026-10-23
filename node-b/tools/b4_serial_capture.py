"""C隔离台架唯一START及180秒串口原始记录；不支持下载、复位或任意控制命令。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
import time

import b4_capture_decode as codec
import b4_recovery as pkg
import b4_runtime as monitor

SCOPE='B4_C_UART_RAW_CAPTURE_ONE_FIXED_START_180S_NO_RESET'


def need(value,reason):
    if not value:raise ValueError(reason)


def bindings():
    return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('b4_serial_capture.py','b4_capture_decode.py','b4_runtime.py','b4_recovery.py')}


def validate(a):
    need(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,
         'CAPTURE_OWNER_AUTH_REQUIRED')
    need(a.get('tools_sha256')==bindings(),'CAPTURE_TOOL_DRIFT')
    need(a.get('port')=='COM15' and a.get('baud')==230400,'CAPTURE_PORT_SCOPE')
    need(a.get('ESP_isolated') is True and a.get('A_disconnected') is True,'CAPTURE_SITE')
    need(time.time()<a.get('expires_unix',0),'CAPTURE_AUTH_EXPIRED')
    need(len(a.get('C_candidate_sha256',''))==64,'CAPTURE_C_IDENTITY_BINDING')


def ready(path,now):
    """只接受本轮独占输出中的新鲜B运行就绪信号，旧文件不能自动武装新台架。"""
    try:
        a=json.loads(path.read_text('utf-8'))
        return a.get('B4_image_sha256')==monitor.IMAGE_SHA and 0<=now-a['host_monotonic']<=3
    except (OSError,ValueError,KeyError,TypeError):return False


def installed(a):
    # BOOT标记只证明入口身份；开始前还必须有本轮SWD整片读回成功回执绑定唯一候选。
    try:
        receipt=json.loads(Path(a['C_install_receipt']).read_text('utf-8'))
        return (receipt.get('status')=='B4_INSTALL_FULL_VERIFY_AND_FLASH_BOOT_PASS'
                and receipt.get('board')=='C' and receipt.get('exit_code')==0
                and receipt.get('full_flash_sha256')==a['C_installed_full_sha256']
                and receipt.get('options_unchanged') is True
                and receipt.get('outside_affected_sectors_unchanged') is True)
    except (OSError,ValueError,KeyError,TypeError):return False


def open_port(factory,port):
    # 先在未打开状态禁用DTR/RTS，避免沿用Serial(port=...)先置有效再拉低的旧路径。
    # 这减少控制线跳变风险，但不代替NRST/BOOT的实际电气取证。
    serial=factory(port=None,baudrate=230400,timeout=.1,write_timeout=1,
                   xonxoff=False,rtscts=False,dsrdtr=False)
    serial.dtr=False;serial.rts=False;serial.port=port;serial.open()
    return serial


def capture(serial,out,ready_path,clock=time.monotonic,install_check=lambda:False):
    parser=codec.Parser();all_rows=[];boot=None;start=None;stop=None;sent=False
    begin=clock();boot_at=None;sent_at=None;raw_bytes=0;preboot_crc=0;preboot_discarded=0
    # 整个主机事务有500秒上限，真正协议动作只能在一次START后的180秒窗口内。
    # 旧H3日志/下载期间杂字节原样保存；首次新候选BOOT后任何损坏均不能忽略。
    with (out/'serial-raw-private.bin').open('xb') as raw, \
         (out/'packets-private.jsonl').open('x',encoding='utf-8') as packets:
        while True:
            now=clock();need(now-begin<500,'CAPTURE_HOST_TIMEOUT')
            if (out/'STOP').exists():raise ValueError('CAPTURE_OWNER_STOP')
            if boot is None:need(now-begin<180,'CAPTURE_BOOT_TIMEOUT')
            elif not sent:need(now-boot_at<240,'CAPTURE_B_READY_TIMEOUT')
            elif start is None:need(now-sent_at<3,'CAPTURE_START_ACK_TIMEOUT')
            else:need(now-sent_at<185,'CAPTURE_STOP_TIMEOUT')
            data=serial.read(8192)
            if data:raw.write(data);raw.flush();raw_bytes+=len(data)
            rows=parser.feed(data)
            for row in rows:
                all_rows.append(row);packets.write(json.dumps(row)+'\n');packets.flush()
                if row['kind']==7:
                    need(boot is None,'CAPTURE_UNEXPECTED_C_REBOOT')
                    need(bytes.fromhex(row['data'])[:4]==b'B4C4' and not row['flags'],'CAPTURE_C_BOOT_ERROR')
                    # 使用该BOOT包前的计数，而非整批read末尾计数；同批后续损坏也必须失败。
                    boot=row;boot_at=clock();preboot_crc=row.get('wire_crc_before',0)
                    preboot_discarded=row.get('wire_discarded_before',0)
                    (out/'C-BOOT-OBSERVED.json').write_text(json.dumps({'host_monotonic':boot_at}))
                if row['kind']==9:
                    need(sent and start is None and not row['flags'],'CAPTURE_UNEXPECTED_START')
                    start=row
                if row['kind']==5 and boot is not None:
                    x,y=struct.unpack('<II',bytes.fromhex(row['data']))
                    if row['id']==4:need(x==0x08000000 and not y and not row['flags'],'CAPTURE_C_VECTOR_FAULT')
                    if row['id']==2:need(not x and not row['flags'],'CAPTURE_C_QUEUE_OR_INIT_ERROR')
                    if row['id']==1:need(not(x&4) and not row['flags'],'CAPTURE_C_BUS_OFF_OR_RX_OVERFLOW')
                if row['kind']==6:
                    need(start is not None and not row['flags'],'CAPTURE_EARLY_OR_ERROR_STOP')
                    stop=row
            if boot is not None and not sent and ready(ready_path,clock()) and install_check():
                # 唯一发送内容固定，短写也视为失败，不补发、不复位、不重新武装。
                sent=True;sent_at=clock()
                need(serial.write(b'B4START\n')==8,'CAPTURE_START_PARTIAL_WRITE')
                serial.flush()
                (out/'START-SENT.json').write_text(json.dumps({'host_monotonic':sent_at,'bytes':8}))
            if stop is not None:break
    report=codec.assess(all_rows,parser.crc_errors-preboot_crc,len(parser.buffer),
                        parser.discarded-preboot_discarded)
    report.update(serial_bytes=raw_bytes,host_elapsed_seconds=clock()-begin,
                  start_commands_attempted=int(sent),target_reset_or_download_commands=0)
    return report


def worker(args,a):
    args.out.mkdir(exist_ok=False);serial=None
    result={'status':'STOP','exit_code':1}
    try:
        # 延迟导入，默认关闭/纯判据测试不会枚举或打开串口。
        import serial as driver
        serial=open_port(driver.Serial,a['port'])
        result=capture(serial,args.out,Path(a['B_ready']),install_check=lambda:installed(a))
        result['exit_code']=0 if not result['failures'] else 3
    except BaseException as error:
        result.update(reason=str(error),type=type(error).__name__)
    finally:
        if serial:
            try:serial.close()
            except BaseException as error:result.update(exit_code=1,close_error=type(error).__name__)
        result['C_candidate_sha256']=a['C_candidate_sha256']
        (args.out/'receipt-private.json').write_text(json.dumps(result,indent=2))
        for file in args.out.iterdir():
            if file.is_file():pkg.protected(file,False)
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}))
    return result['exit_code']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorization',type=Path)
    p.add_argument('--out',type=Path);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    try:
        need(args.authorization is not None and args.out is not None,'CAPTURE_AUTH_OUT_REQUIRED')
        a=json.loads(pkg.protected(args.authorization,False).read_text('utf-8'));validate(a)
        pkg.protected(args.out.parent,False);need(not args.out.exists(),'CAPTURE_OUTPUT_EXISTS')
        b_ready=Path(a['B_ready']);pkg.protected(b_ready.parent.parent,False)
        need(not b_ready.parent.exists(),'CAPTURE_B_READY_REUSED')
        if args.worker:return worker(args,a)
        with args.authorization.with_suffix('.used').open('x') as f:f.write(SCOPE)
        with args.out.with_name(args.out.name+'-worker.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--worker',
                '--authorization',str(args.authorization),'--out',str(args.out)],stdout=log,stderr=subprocess.STDOUT)
            try:child.wait(timeout=510)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5);return 1
        return child.returncode
    except (ValueError,OSError,KeyError,TypeError):
        print(json.dumps({'status':'STOP_BEFORE_SERIAL','exit_code':1}));return 1


if __name__=='__main__':raise SystemExit(main())
