"""主机配额和有界UART调用模型；不加载DLL、不访问设备。"""
import math


class HostBudgetExhausted(ValueError):
    pass


class NativeReadFailed(ValueError):
    pass


class NativeCallUncertain(RuntimeError):
    pass


TX_POLLS = 4
DAP_BYTE_CALLS = 12
RX_INTERVAL = .02
EXIT_CALLS = 40  # 清理后的复核、最终状态检查、退出策略和Close；失败前检查另留12。
FAILURE_SNAPSHOT_CALLS = 12


def response_polls(timeout):
    return math.ceil(timeout / RX_INTERVAL)


def command_calls(command, timeout=3):
    return 1 + len(command) * (TX_POLLS + DAP_BYTE_CALLS) + 3 * response_polls(timeout)


class CommandBudget:
    def __init__(self, link, cleanup_commands):
        self.link = link
        self.cleanup_commands = tuple(cleanup_commands)
        self.cleanup_reserve = sum(command_calls(c) for c in cleanup_commands) + EXIT_CALLS + FAILURE_SNAPSHOT_CALLS

    def admit(self, command, timeout, cleanup=False):
        reserve = (EXIT_CALLS + sum(command_calls(c) for c in
            self.cleanup_commands[self.cleanup_commands.index(command)+1:])) if cleanup else self.cleanup_reserve
        needed = command_calls(command, timeout) + reserve
        if self.link.sdk_limit - self.link.sdk_calls < needed:
            raise HostBudgetExhausted('P0A_API_CLEANUP_RESERVE')
        self.current_reserve = reserve

    def byte(self, remaining_bytes, remaining_rx_polls, cleanup=False):
        needed = remaining_bytes * (TX_POLLS + DAP_BYTE_CALLS) + 3 * remaining_rx_polls + self.current_reserve
        if self.link.sdk_limit - self.link.sdk_calls < needed:
            raise HostBudgetExhausted('P0A_BYTE_BUDGET')
