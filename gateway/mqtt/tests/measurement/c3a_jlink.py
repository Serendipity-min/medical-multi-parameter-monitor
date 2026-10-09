"""已批准窗口的本地J-Link 5.12 DLL短暂停采样；导入不会访问硬件。"""

import pylink


class CaptureLink:
    def __init__(self, uid_guard, *, window_authorized=False):
        if window_authorized is not True:
            raise RuntimeError('HARDWARE_WINDOW_NOT_AUTHORIZED')
        self.library = pylink.library.Library(
            'E:/stm32/j_link/JLink_V512/bin_x64/JLink_x64.dll', use_tmpcpy=False)
        self.link = pylink.JLink(lib=self.library, log=lambda *a: None,
                                detailed_log=lambda *a: None, error=lambda *a: None,
                                warn=lambda *a: None)
        try:
            self.link.open()
            self.link.set_tif(pylink.enums.JLinkInterfaces.SWD)
            self.link.connect('STM32F407ZG', speed=4000)
            if bytes(self.link.memory_read8(0x1FFF7A10, 12)) != uid_guard:
                raise RuntimeError('HARDWARE_UID_MISMATCH')
            if self.link.halted():
                raise RuntimeError('UNEXPECTED_HALTED_CORE')
            self.registers = {self.link.register_name(i).upper(): i for i in self.link.register_list()}
        except BaseException:
            self.close()
            raise

    def read32(self, address):
        # 运行中只读白名单调试时钟/状态寄存器，不读网络凭据缓冲或任意RAM。
        if address not in (0xE0001000, 0xE0001004, 0xE000EDF0):
            raise RuntimeError('REGISTER_NOT_IN_WINDOW_ALLOWLIST')
        return int(self.link.memory_read32(address, 1)[0])

    def halt(self):
        self.link.halt()
        if not self.link.halted():
            raise RuntimeError('HALT_NOT_CONFIRMED')

    def snapshot(self, address):
        # 地址来自固定诊断ELF布局；只读取完整ProbeState，不触碰栈哨兵。
        if address not in (536956400, 536956448) or not self.link.halted():
            raise RuntimeError('SNAPSHOT_ADDRESS_OR_STATE')
        data = bytes(self.link.memory_read8(address, 1264))
        if len(data) != 1264:
            raise RuntimeError('SNAPSHOT_READ_LENGTH')
        return data

    def registers_at_halt(self):
        values = {}
        for name in ('XPSR', 'MSP', 'PSP', 'CONTROL', 'PRIMASK', 'BASEPRI', 'FAULTMASK'):
            if name not in self.registers:
                raise RuntimeError('REGISTER_LAYOUT_UNAVAILABLE')
            values[name] = self.link.register_read(self.registers[name])
        pc = next((index for name, index in self.registers.items() if name in ('PC', 'R15') or name.startswith('R15 ')), None)
        if pc is None:
            raise RuntimeError('PC_REGISTER_UNAVAILABLE')
        values['PC'] = self.link.register_read(pc)
        values['IPSR'] = values['XPSR'] & 0x1ff
        return values

    def resume(self):
        # 默认GoEx不单步、不跳过断点；恢复原执行位置，不reset或更改测量固件。
        self.link.restart()
        if self.link.halted():
            raise RuntimeError('RESUME_NOT_CONFIRMED')

    def close(self):
        if getattr(self, 'link', None) is not None:
            self.link.close()
            # 旧SDK在解释器退出阶段已卸载DLL时会被PyLink析构再次调用；成功关闭后解除该重复调用。
            self.link._initialized = False
            self.link = None
        self.library = None
