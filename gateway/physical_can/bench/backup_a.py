"""H2-A: 固定只读J-Link流程；原始标识/日志/Flash仅进入受限本地目录。"""
import argparse,ast,hashlib,json,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--private-dir',type=Path,required=True)
parser.add_argument('--c-identity-source',type=Path,required=True)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[3]
PRIVATE=args.private_dir.resolve()
if PRIVATE.is_relative_to(ROOT):raise SystemExit('PRIVATE_BACKUP_MUST_BE_OUTSIDE_REPOSITORY')
if not PRIVATE.is_dir():raise SystemExit('PREPARE_RESTRICTED_DIRECTORY_FIRST')
OUT=ROOT/'gateway/physical_can/evidence/h2'
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
run=PRIVATE/('a-backup-'+stamp);run.mkdir()
report={'mode':'JLINK_A_READ_ONLY_BACKUP','role':'A','user_confirmed_A_only_powered_C_off_CAN_separated':True,'exit_code':1,'flash_modified':False,'C_accessed':False,'stage':'IDENTITY'}
def execute(name,commands):
 # 只允许固定只读/停止命令；绝不传入erase/load/option写入/解锁或复位命令。
 assert all(c=='connect' or c=='h' or c=='q' or c.startswith('savebin ') for c in commands)
 (run/(name+'.jlink')).write_text('\n'.join(commands)+'\n',encoding='ascii')
 r=subprocess.run(['D:/keil/ARM/Segger/JLink.exe','-device','STM32F407ZG','-if','SWD','-speed','1000'],input=('\n'.join(commands)+'\n').encode('ascii'),capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
 (run/(name+'.raw.log')).write_bytes(r.stdout+r.stderr)
 report[name+'_process_exit']=r.returncode
 if r.returncode:raise RuntimeError('JLINK_NONZERO')
def save(name,address,length):return 'savebin '+str(run/(name+'.bin')).replace('\\','/')+' '+hex(address)+' '+hex(length)
def read(name,n):
 data=(run/(name+'.bin')).read_bytes()
 if len(data)!=n:raise RuntimeError('READ_LENGTH_MISMATCH')
 return data
try:
 # 读地址必须与固定工程ST头文件一致；首次错误读址的失败证据已单独保留。
 header=(ROOT/'node-a/STM32F407_HOSPITAL/USER/stm32f4xx.h').read_text(encoding='utf-8',errors='replace')
 if not re.search(r'#define\s+DBGMCU_BASE\s+.*0xE0042000',header):raise RuntimeError('DBGMCU_ADDRESS_NOT_VERIFIED')
 execute('identity',['connect','h',save('chip',0xE0042000,4),save('flash-size',0x1fff7a22,2),save('uid',0x1fff7a10,12),save('option-register',0x40023c14,4),save('option-bytes',0x1fffc000,16),'q'])
 chip=int.from_bytes(read('chip',4),'little')&0xfff
 size=int.from_bytes(read('flash-size',2),'little')
 opt=int.from_bytes(read('option-register',4),'little')
 uid=read('uid',12)
 if chip!=0x413 or size!=1024:raise RuntimeError('CHIP_OR_FLASH_SIZE_MISMATCH')
 # 只在内存与C既有外部身份比对，避免把同一块C误当A；不输出任何UID值。
 tree=ast.parse(args.c_identity_source.read_text(encoding='utf-8'))
 expected=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXPECTED_UID' for t in n.targets))
 from stm32loader.bootloader import Stm32Bootloader
 if Stm32Bootloader.format_uid(uid)==expected:raise RuntimeError('A_MATCHES_KNOWN_C_IDENTITY')
 report.update({'chip_id_match':True,'flash_kib':size,'A_distinct_from_known_C':True,'rdp_level_zero':((opt>>8)&255)==0xaa,'option_bytes_sha256':hashlib.sha256(read('option-bytes',16)).hexdigest()})
 if not report['rdp_level_zero']:raise RuntimeError('RDP_READ_PROTECTED_STOP')
 report['stage']='FLASH_READ_TWICE'
 execute('flash-read',['connect','h',save('flash-first',0x08000000,0x100000),save('flash-second',0x08000000,0x100000),'q'])
 first=read('flash-first',0x100000);second=read('flash-second',0x100000)
 if first!=second:raise RuntimeError('BACKUP_READS_DIFFER_STOP')
 sp=int.from_bytes(first[:4],'little');reset=int.from_bytes(first[4:8],'little')
 if not (0x20000000<sp<=0x20020000 and 0x08000000<reset<0x08100000 and reset&1):raise RuntimeError('EXISTING_IMAGE_VECTOR_INVALID_STOP')
 report.update({'stage':'BACKUP_VERIFIED','backup_exists':True,'backup_bytes':len(first),'backup_sha256':hashlib.sha256(first).hexdigest(),'independent_reads_match':True,'existing_vectors_plausible':True,'exit_code':0})
except BaseException as error:
 # 错误只报告类型和自定义阶段码，不打印可能含UID或内存内容的底层异常。
 report['failure_type']=type(error).__name__
 if type(error) is RuntimeError:report['failure_code']=str(error)
finally:
 (run/'private-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 (OUT/('a-backup-'+stamp+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
raise SystemExit(report['exit_code'])
