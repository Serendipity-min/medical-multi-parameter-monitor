"""显式启用的非人体 SWD 适配器：只读 Flash，允许计划内复位/暂停，不烧录。"""
from contextlib import contextmanager, ExitStack, nullcontext
import json
import os
from pathlib import Path
import queue
import re
import struct
import subprocess
import sys
import threading
import time

from acq_protocol import dump_strict_json, now_utc_iso, sha256_file
from acq_storage import check_configuration, exclusive, offline_precheck, require, seal_run, update_index

HALTED = 1 << 17
LOCKUP = 1 << 19
RESET_SEEN = 1 << 25
DEFAULT_JLINK = Path('E:/stm32/j_link/JLink_V512/JLink.exe')

DLL_MEM32_RE = re.compile(
    r'JLINK_ReadMemU32\(0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+)\s+Items,.*?- Data:\s*([0-9A-Fa-f ]+?)\s+returns\s+0x([0-9A-Fa-f]+)'
)


@contextmanager
def ascii_mapping(folder):
    """旧 Commander 不可靠支持中文文件名；只占用一个空闲盘符，映射归本轮所有。"""
    require(os.name == 'nt', 'SWD 硬件模式目前只支持 Windows；脱机命令跨平台')
    listing = subprocess.run(['subst'], capture_output=True, check=True).stdout.decode('gbk', errors='replace')
    available = next((letter for letter in 'RSTUVW' if not Path(letter+':/').exists()
                      and letter+':\\:' not in listing), None)
    require(available is not None, '没有空闲临时盘符；不会撤销其它任务映射')
    drive = available+':'
    subprocess.run(['subst', drive, str(folder)], check=True)
    try:
        yield drive+'/'
    finally:
        current = subprocess.run(['subst'], capture_output=True, check=True).stdout.decode('gbk', errors='replace')
        # 不依赖个人用户名；只撤销仍指向本轮目录的自有映射。
        if any(line.startswith(drive+'\\:') and str(folder).casefold() in line.casefold()
               for line in current.splitlines()):
            subprocess.run(['subst', drive, '/d'], check=True)


class JLinkClient:
    def __init__(self, executable, raw, prefix):
        self.raw, self.prefix = Path(raw), prefix
        self.lines = queue.Queue()
        self.log = (self.raw/'jlink.log').open('xb')
        self.script = (self.raw/'commands.jlink').open('x', encoding='ascii')
        self.io = (self.raw/'io.jsonl').open('x', encoding='utf-8')
        self.dll_log_path = self.raw/'dll.log'
        self.dll_log_active = False
        self.closing = False
        try:
            self.process = subprocess.Popen([str(executable), '-device', 'STM32F407ZG', '-if', 'SWD',
                '-speed', '4000', '-autoconnect', '1'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, bufsize=0)
            # 启用 J-Link DLL 实时日志文件，绕过 Windows CRT 对管道 stdout 的 4096 B 块缓冲
            init_log_cmd = f'log {self.prefix}dll.log\n'
            self.script.write(init_log_cmd)
            self.script.flush()
            self.process.stdin.write(init_log_cmd.encode('ascii'))
            self.process.stdin.flush()
        except BaseException:
            self.io.close()
            self.script.close()
            self.log.close()
            raise
        self.reader = threading.Thread(target=self._read_lines, daemon=True)
        self.reader.start()
        self.dll_reader = threading.Thread(target=self._read_dll_log, daemon=True)
        self.dll_reader.start()
        self.last_status = None
        self.command_count = 0
        self.failed = False

    def _read_lines(self):
        # 单独读线程防止 stdout 管道满导致死锁；原始日志不作字符转换。
        try:
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.log.write(line)
                self.log.flush()
                if not self.dll_log_active:
                    self.lines.put(line.decode('ascii', errors='replace'))
        finally:
            if not self.dll_log_active:
                self.lines.put(None)

    def _read_dll_log(self):
        # 实时追踪 J-Link DLL 无缓冲日志，将 JLINK_ReadMemU32 还原为标准响应行供命令边界确认。
        pos = 0
        partial = ''
        try:
            while not self.closing or self.process.poll() is None:
                if not self.dll_log_path.exists():
                    time.sleep(0.005)
                    continue
                if not self.dll_log_active:
                    self.dll_log_active = True
                try:
                    with self.dll_log_path.open('rb') as stream:
                        stream.seek(pos)
                        chunk = stream.read()
                        pos = stream.tell()
                except OSError:
                    time.sleep(0.005)
                    continue
                if not chunk:
                    time.sleep(0.002)
                    continue
                text = partial + chunk.decode('ascii', errors='replace')
                if not text.endswith('\n'):
                    parts = text.split('\n')
                    partial = parts.pop()
                    lines = parts
                else:
                    partial = ''
                    lines = text.splitlines()
                for line in lines:
                    match = DLL_MEM32_RE.search(line)
                    if match:
                        addr = int(match.group(1), 16)
                        count = int(match.group(2), 16)
                        raw_bytes = bytes.fromhex(match.group(3))
                        ret = int(match.group(4), 16)
                        if ret != count or len(raw_bytes) < count * 4:
                            self.lines.put('Error: JLINK_ReadMemU32 returned incomplete data\n')
                        else:
                            words = struct.unpack_from(f'<{count}I', raw_bytes)
                            formatted = f"{addr:08X} = {' '.join(f'{w:08X}' for w in words)}\n"
                            self.lines.put(formatted)
                    elif re.search(r'returns\s+0xFFFFFF', line, re.I):
                        self.lines.put('Error: J-Link DLL call returned negative status\n')
        finally:
            if self.dll_log_active:
                self.lines.put(None)

    def command(self, command='', timeout=8, file=None):
        require(not self.failed, '前一命令失败后不能复用确认队列，必须停止本轮')
        require(not (self.raw.parent/'STOP').exists(), '已收到 STOP，不发送后续硬件命令')
        started = time.monotonic_ns()
        # 每个操作后读 DHCSR 作为完成边界；它同时用于确认暂停/运行状态。
        text = (command+'\n' if command else '')+'mem32 0xE000EDF0 1\n'
        self.script.write(text)
        self.script.flush()
        self.process.stdin.write(text.encode('ascii'))
        self.process.stdin.flush()
        self.command_count += 1
        response = []
        status = None
        error = None
        try:
            while True:
                require(not (self.raw.parent/'STOP').exists(), '已收到 STOP，终止等待并保留原件')
                remaining = timeout-(time.monotonic_ns()-started)/1e9
                if remaining <= 0:
                    raise TimeoutError('J-Link 命令超时')
                try:
                    line = self.lines.get(timeout=min(.1, remaining))
                except queue.Empty:
                    continue  # 分段等待使 STOP 在长 IO 等待中也能被发现。
                if line is None:
                    raise RuntimeError('J-Link 在命令确认前退出')
                response.append(line)
                if re.search(r'\b(?:Error|Failed|Cannot|Could not|Unknown command)\b', line, re.I):
                    raise RuntimeError('J-Link 报告命令失败；原始日志保留')
                match = re.search(r'E000EDF0\s*=\s*([0-9A-Fa-f]{8})', line)
                if match:
                    status = int(match.group(1), 16)
                    self.last_status = status
                    break
        except BaseException as exc:
            # 避免超时/失败后迟到的 DHCSR 行被误认成下一条命令的确认。
            self.failed = True
            error = type(exc).__name__+': '+str(exc)
            raise
        finally:
            entry = {'command': command, 'request_ns': str(started),
                     'confirmation_ns': str(time.monotonic_ns()) if status is not None else None,
                     'dhcsr': status, 'file': 'raw/'+file if file else None, 'error': error}
            self.io.write(json.dumps(entry, ensure_ascii=False, allow_nan=False)+'\n')
            self.io.flush()
        require(not status & LOCKUP, '设备报告 LOCKUP，停止采集')
        return status, ''.join(response)

    def read(self, name, address, size, timeout=8):
        file = self.raw/name
        require(not file.exists(), '目标原始文件已存在，禁止覆盖: '+name)
        self.command(f'savebin {self.prefix}{name} {address:#x} {size:#x}', timeout, name)
        require(file.is_file() and file.stat().st_size == size, 'J-Link 读数缺失或长度错误: '+name)
        return file

    def close(self):
        # 失败后不追加 reset/halt/go；目标状态未知时不能擅自采取恢复动作。
        self.closing = True
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b'exit\n')
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.reader.join(timeout=5)
        self.dll_reader.join(timeout=5)
        require(not self.reader.is_alive() and not self.dll_reader.is_alive(), 'J-Link 日志线程未结束')
        self.process.stdout.close()
        self.io.close()
        self.script.close()
        self.log.close()
        return self.process.returncode


def capture_run(run, jlink=DEFAULT_JLINK, confirm_no_human=False, client_factory=JLinkClient,
                mapping_factory=ascii_mapping, clock=time.monotonic, sleeper=time.sleep):
    run = Path(run).resolve()
    session, _, profile = check_configuration(run)
    require(confirm_no_human is True, '本版 SWD 模式要求明确确认没有任何活人连接电极')
    require(session['input']['declared_kind'] in {'ACTIVE_HARDWARE_SIMULATOR', 'INTERNAL_TEST_SIGNAL', 'PASSIVE_PHANTOM'},
            '本版硬件采集仅用于明确的非人体台架输入；UNKNOWN/HUMAN_DECLARED 不准入')
    require(re.fullmatch(r'[0-9A-F]{8}-[0-9A-F]{8}-[0-9A-F]{8}', session['device'].get('expected_uid','')) is not None,
            '缺少预期板卡 UID')
    duration = session['plan']['capture_duration_s']
    require(isinstance(duration, (int,float)) and 1 <= duration <= 300, '采集时长超出 1～300 s')
    require(session['plan']['poll_interval_ms'] == 100, '首版轮询间隔固定 100 ms，不静默扩大资源范围')
    require(session['plan']['approved_hardware_action_list'] == [
                'READ_IDENTITY_AND_FLASH_TWICE','ONE_RESET_AND_RUN','LIVE_READ_ONLY_POLL',
                'ONE_FINAL_HALT_AND_RAM_READ','RESUME_AND_CONFIRM'],
            '操作清单与已实现适配器不一致，停止；不扩大或忽略清单')
    offline = offline_precheck(run)
    require(Path(jlink).is_file(), 'J-Link 程序不存在')
    require(not (run/'raw_manifest.json').exists(), '轮次已封存，请新建轮次')
    with exclusive(run/'.capture.lock'):
        # 即使中途失败也不能在同一轮重跑，从根源上避免混入旧文件。
        (run/'.capture.started').open('x').close()
        receipt = {'protocol_version': '1.0', 'run_id': session['run_id'], 'mode': 'NONHUMAN_SWD',
                   'started_utc': now_utc_iso(), 'status': 'STARTED', 'identity_status': 'UNKNOWN',
                   'target_end_state': 'UNKNOWN', 'paused_snapshot_evidence': None,
                   'no_live_person_connected_declared': True, 'offline_precheck': offline,
                   'jlink_sha256': sha256_file(Path(jlink)), 'hardware_flash_writes': 0,
                   'planned_reset_count': 1, 'planned_final_halt_count': 1}
        client, failure = None, None
        resources = ExitStack()
        try:
            # 映射必须在子进程完全退出后才释放，超时读数不能继续写向已撤销的盘符。
            with nullcontext(resources.enter_context(mapping_factory(run/'raw'))) as prefix:
                client = client_factory(jlink, run/'raw', prefix)
                status, _ = client.command()
                receipt['initial_target_state'] = 'HALTED' if status & HALTED else 'RUNNING'
                # 初始暂停不提前恢复；先核对身份，符合后才执行明确计划内的 reset/go。
                _, uid_text = client.command('mem32 0x1FFF7A10 3')
                match = re.search(r'1FFF7A10\s*=\s*([0-9A-F]{8})\s+([0-9A-F]{8})\s+([0-9A-F]{8})', uid_text, re.I)
                require(match is not None, '未取得完整板卡 UID')
                uid = '-'.join(match.groups()).upper()
                receipt['observed_uid'] = uid
                if uid != session['device']['expected_uid']:
                    receipt['identity_status'] = 'MISMATCH'
                    raise ValueError('板卡 UID 不匹配，立即停止')
                _, id_text = client.command('mem32 0xE0042000 1')
                match = re.search(r'E0042000\s*=\s*([0-9A-F]{8})', id_text, re.I)
                require(match is not None and int(match.group(1),16)&0xfff == 0x413, '器件 ID 不符合 F407 家族')
                before = client.read('identity-flash-1.bin', 0x08000000, 1048576, 45)
                second = client.read('identity-flash-2.bin', 0x08000000, 1048576, 45)
                flash_sha = sha256_file(before)
                require(flash_sha == sha256_file(second), 'Flash 双读不一致，停止')
                if flash_sha != profile['firmware_binding']['flash_1mib_sha256']:
                    receipt['identity_status'] = 'MISMATCH'
                    raise ValueError('Flash 与冻结采集镜像不一致，停止；不会烧录修正')
                receipt.update(identity_status='VERIFIED', observed_flash_sha256=flash_sha)
                # 只有身份全部符合才执行计划内的一次复位；不存在 loadbin/loadfile/写寄存器命令。
                client.command('r')
                status, _ = client.command('g')
                require(not status & HALTED, '启动后未确认运行')
                start = clock()
                progress_at = start
                polls = 0
                last = start
                gaps = []
                ring = profile['slot_ring']
                while clock()-start < duration:
                    require(not (run/'STOP').exists(), '已收到 STOP 文件，不再发送硬件命令')
                    client.read(f'slot_{polls:05d}.bin', int(ring['slots_addr'],0), 3072)
                    status = client.last_status
                    require(not status & (HALTED|RESET_SEEN), '采集中发生意外暂停/复位，停止')
                    now = clock()
                    gaps.append(now-last)
                    last = now
                    if now-progress_at >= 5:
                        print(f'采集中：{now-start:.1f}/{duration} s，原始槽块 {polls+1}；未作准确度判定', file=sys.stderr, flush=True)
                        progress_at = now
                    if polls % 10 == 0:
                        client.read(f'state_{polls:05d}.bin', 0x20000000, 2048)
                        require(not client.last_status & (HALTED|RESET_SEEN), '状态取数时发生意外暂停/复位')
                    polls += 1
                    require(polls <= 4000, '轮询数量超过上限')
                    # STOP 等待期间也可响应；不以 sleep 参数替代真实 IO 耗时。
                    sleep_left = min(.1, max(0, duration-(clock()-start)))
                    for _ in range(5):
                        require(not (run/'STOP').exists(), '已收到 STOP 文件')
                        sleeper(sleep_left/5)
                receipt.update(actual_capture_wall_s=clock()-start, polls=polls,
                               max_poll_completion_gap_s=max(gaps) if gaps else None)
                status, _ = client.command('h')
                require(status & HALTED, '未确认暂停，禁止使用暂停快照')
                client.command('regs')
                client.read('final-paused-ram.bin', 0x20000000, 131072, 20)
                require(client.last_status & HALTED, '最终 RAM 读取期间目标未保持暂停')
                receipt['paused_snapshot_evidence'] = 'DHCSR_CONFIRMED'
                status, _ = client.command('g')
                require(not status & HALTED, '恢复请求后仍为暂停')
                sleeper(.02)
                status, _ = client.command()
                require(not status & HALTED, '第二次恢复核验未通过')
                receipt.update(target_end_state='RUNNING_CONFIRMED_BEFORE_DISCONNECT', status='CAPTURE_COMPLETED')
        except BaseException as exc:
            # 用户中断、设备 STOP、IO 失败均保留实际执行到的位置，不强称已恢复。
            receipt.update(status='STOP_OR_INCOMPLETE', error=type(exc).__name__+': '+str(exc),
                           target_end_state='UNKNOWN_AFTER_STOP')
            failure = exc
        finally:
            if client is not None:
                try:
                    receipt['process_exit_code'] = client.close()
                    receipt['jlink_command_count'] = client.command_count
                    if receipt['process_exit_code'] != 0:
                        raise RuntimeError('J-Link 进程非零退出，不能宣告完整采集')
                except BaseException as exc:
                    receipt.update(status='STOP_OR_INCOMPLETE', close_error=str(exc), target_end_state='UNKNOWN_AFTER_STOP')
                    failure = failure or exc
            try:
                resources.close()
            except BaseException as exc:
                receipt.update(status='STOP_OR_INCOMPLETE', mapping_cleanup_error=str(exc))
                failure = failure or exc
            receipt['finished_utc'] = now_utc_iso()
            dump_strict_json(receipt, run/'acquisition_receipt.json')
            seal_run(run)
            update_index(run, identity=receipt['identity_status'], integrity='NOT_EVALUATED', reason=receipt['status'])
        if failure:
            raise failure
    return receipt
