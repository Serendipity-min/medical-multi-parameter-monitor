"""下一授权包的同范围UART低开销桥；仅离线验证，当前没有执行入口。"""
import struct
import time
import b5_esp_udp_ntp as u
from b5_esp_budget import TX_POLLS,response_polls,RX_INTERVAL,CommandBudget,HostBudgetExhausted,EXIT_CALLS,FAILURE_SNAPSHOT_CALLS
q=u.q;g=u.g


def command_calls(command,timeout=3):
    # 回绕最多两段数据加前后两次stats读；10次固定调用覆盖上下文保存/恢复。
    return 1+16*len(command)+4*response_polls(timeout)+10


class FastBudget(CommandBudget):
    def __init__(self,link,cleanup_commands):
        super().__init__(link,cleanup_commands)
        self.cleanup_reserve=sum(command_calls(c) for c in cleanup_commands)+EXIT_CALLS+FAILURE_SNAPSHOT_CALLS
    def admit(self,command,timeout,cleanup=False):
        reserve=(EXIT_CALLS+sum(command_calls(c) for c in self.cleanup_commands[self.cleanup_commands.index(command)+1:])) if cleanup else self.cleanup_reserve
        if self.link.sdk_limit-self.link.sdk_calls<command_calls(command,timeout)+reserve:raise HostBudgetExhausted('P0A_API_CLEANUP_RESERVE')
        self.current_reserve=reserve
    def byte(self,remaining_bytes,remaining_rx_polls,cleanup=False):
        if self.link.sdk_limit-self.link.sdk_calls<16*remaining_bytes+4*remaining_rx_polls+10+self.current_reserve:raise HostBudgetExhausted('P0A_BYTE_BUDGET')


class FastLink(q.QueryLink):
    def __init__(self,out,commands):
        self.READ_SCOPE={a:set(sizes) for a,sizes in u.READS.items() if a!=q.RING}
        self.BYTE_COMMANDS=tuple(commands);super().__init__(out)
    def raw_read_allowed(self,address):return address in (q.UART,q.CR,q.SR)
    def allow_delta(self,address,size):
        g.require(q.RING<=address<q.RING+q.CAPACITY and 0<size<=512 and address+size<=q.RING+q.CAPACITY,'FAST_RX_DELTA_SCOPE')
        self.READ_SCOPE.setdefault(address,set()).add(size)
    def read_delta(self,address,size):
        self.allow_delta(address,size);return self.read(address,size)


class FastBridge(u.UartBridge):
    def write_command(self,link,command,budget,timeout):
        g.require(self.proven and self.guard is not None,'FAST_BRIDGE_NOT_PROVEN')
        with self.window():
            csw=self.bus.read(0,True);self.bus.write(0,True,(csw&~0x37)|2)
            for index,value in enumerate(command):
                budget.byte(len(command)-index,response_polls(timeout))
                for poll in range(TX_POLLS):
                    self.bus.write(1,True,q.UART)
                    if self.bus.read(3,True)&(1<<7):break
                    if poll+1<TX_POLLS:time.sleep(.005)
                else:raise ValueError('FAST_UART_TX_NOT_READY')
                self.guard(q.DR,value);self.bus.write(1,True,q.DR)
                self.bus.grant_target_write(q.DR,value)
                try:self.bus.write(3,True,value)
                finally:self.bus.grant_target_write(None,None)


def ring_delta(link,baseline):
    before=struct.unpack('<5I',link.read(q.STATS,20))
    g.require(before[:4]==baseline[:4],'FAST_UART_ERROR_OR_CONSUMER')
    count=(before[4]-baseline[4])%q.CAPACITY
    g.require(0<=baseline[4]<q.CAPACITY and 0<=before[4]<q.CAPACITY and count<=512,'FAST_RING_GEOMETRY_OR_OVERFLOW')
    first=min(count,q.CAPACITY-baseline[4]);data=b''
    if first:data=link.read_delta(q.RING+baseline[4],first)
    if count>first:data+=link.read_delta(q.RING,count-first)
    after=struct.unpack('<5I',link.read(q.STATS,20))
    g.require(after[:4]==baseline[:4],'FAST_UART_ERROR_OR_CONSUMER')
    return data if before[4]==after[4] else None


def exchange(link,bridge,command,out,index,budget,mode='OK',timeout=2,allow_error=False):
    budget.admit(command,timeout,link.byte_grant.cleanup_started)
    baseline=struct.unpack('<5I',link.read(q.STATS,20));g.save(out/f'query-{index}-baseline-private.json',{'stats':baseline})
    started=time.monotonic();link.byte_grant.begin(command);bridge.write_command(link,command,budget,timeout)
    sent=time.monotonic();data=b'';kind=None
    for _ in range(response_polls(timeout)):
        if time.monotonic()-sent>=timeout:break
        raw=ring_delta(link,baseline)
        if raw is not None:
            data=raw;kind=u.terminal(data,mode)
            if kind:break
        time.sleep(RX_INTERVAL)
    g.write_private(out/f'query-{index}-response-private.bin',data)
    g.save(out/f'query-{index}-meta-private.json',{'command_bytes':len(command),'response_bytes':len(data),
        'mode':mode,'terminal':kind,'started_monotonic':started,'sent_monotonic':sent,'observed_monotonic':time.monotonic()})
    g.require(kind=={'OK':'OK','SEND':'SEND_OK','PROMPT':'PROMPT'}[mode] or allow_error and kind=='ERROR','FAST_NO_EXPECTED_TERMINAL')
    return data,baseline,sent
