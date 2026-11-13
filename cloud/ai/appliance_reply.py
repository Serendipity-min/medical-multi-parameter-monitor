"""隔离P6V1→MR02适配；只有认证音频完成身份可建立C回复上下文。"""
from dataclasses import dataclass
import re
import struct
import time
from cloud.microphone.protocol import AudioAssembler
from .downlink import decode, encode
from .facts import answer_facts, digest, question_rule

GATEWAY = 'GW-B5-001'
HEADER = struct.Struct('<4sIIQQQIIIBBBB12s16sH')
STREAM = {'SPO2': 1, 'PR': 2, 'NIBP': 3, 'HR': 5, 'RR': 7, 'TEMP': 8}
ROLE = {'SPO2': 'NODE-A', 'PR': 'NODE-A', 'NIBP': 'NODE-E', 'HR': 'NODE-B', 'RR': 'NODE-B', 'TEMP': 'NODE-D'}
STATE = {'VALID': 0, 'INVALID': 1, 'STALE': 2, 'OFFLINE': 3}
UNAVAILABLE = '当前读数不可用'


@dataclass(frozen=True)
class Recording:
    session: int
    crc: int
    deadline: int


def adapt_reply(payload: bytes, facts: list[dict], question: str, recording: Recording, now: int) -> bytes:
    message = decode(payload, now)
    if now >= recording.deadline or message['fact_digest'] != digest(facts):
        raise ValueError('REPLY_CONTEXT_OR_DIGEST')
    kind, selected = question_rule(question)
    chosen = [f for f in facts if f['stream'] in selected]
    if kind != 'SINGLE_VALUE' or len(chosen) != 1:
        raise ValueError('ONE_FACT_REQUIRED')
    f = chosen[0]
    if f['gateway_id'] != GATEWAY or f['node_id'] != ROLE[f['stream']]:
        raise ValueError('REPLY_FACT_ROLE')
    state = 4 if f['source'] == 'REPLAY' else STATE[f['validity']]
    ttl = 90000 if f['stream'] == 'NIBP' else 5000
    if f['timestamp'] > now+1000 or now-f['timestamp'] >= ttl:
        state = 2
    if message['text'] != answer_facts(facts, question).split('\n')[0]:
        raise ValueError('VOICE_MUST_EQUAL_TRUSTED_FACT_TEMPLATE')
    text = message['text'] if state == 0 else UNAVAILABLE
    raw = text.encode('utf-8')
    if not 1 <= len(raw) <= 120:
        raise ValueError('REPLY_TEXT_SIZE')
    expires = min(message['expires_ms'], recording.deadline, f['timestamp']+ttl if state == 0 else now+15000)
    identity = re.fullmatch(r'can-([0-9]+)-([0-9]+)', f['session_id'])
    if identity is None or not 0 < f['seq'] <= 0xffffffff:
        raise ValueError('REPLY_FACT_PROVENANCE')
    epoch, boot = map(int, identity.groups())
    if not 0 < epoch <= 0xffffffff or not 0 < boot <= 0xffffffff:
        raise ValueError('REPLY_FACT_PROVENANCE')
    return HEADER.pack(b'MR02', recording.session, recording.crc, message['issued_ms'], expires,
                       f['timestamp'], f['seq'], epoch, boot, ord(f['node_id'][-1])-64,
                       STREAM[f['stream']], state, int(f['synthetic']), GATEWAY.encode(),
                       bytes.fromhex(message['fact_digest']), len(raw)) + raw


class RecordingReplyAdapter:
    """send(topic, bytes)由隔离发布者注入；缺上下文时绝不借用/伪造会话。"""
    def __init__(self, send, clock_ms=None):
        self.send = send
        self.clock_ms = clock_ms or (lambda: int(time.time()*1000))
        self.assembler = AudioAssembler(allow_short=True)
        self.recording = None

    def feed_audio(self, topic, payload, qos, retain, now_ms=None):
        if topic != 'mpm/mic/v1/in' or qos != 1 or retain:
            raise ValueError('AUDIO_AUTHORITY')
        now = self.clock_ms() if now_ms is None else now_ms
        audio = self.assembler.feed('C', payload, now/1000)
        if audio is not None:
            if not -1000 <= now-audio['session']*1000 < 300000:
                raise ValueError('AUDIO_SESSION_AGE')
            self.recording = Recording(audio['session'], audio['crc32'], min(now+300000, audio['session']*1000+300000))
        return audio

    async def publish_facts(self, gateway, turn_id, facts, question, issued_ms):
        if gateway != GATEWAY:
            raise ValueError('REPLY_GATEWAY')
        if self.recording is None:
            return 'NO_RECORDING_CONTEXT'
        context, self.recording = self.recording, None
        kind, _ = question_rule(question)
        if kind != 'SINGLE_VALUE' or not facts:
            status = 5 if kind == 'GENERAL_ADVICE' else 7 if kind == 'SINGLE_VALUE' else 6
            now = self.clock_ms()
            expires = min(issued_ms + 15000, context.deadline)
            if not issued_ms <= now + 1000 or now >= expires or expires <= issued_ms:
                raise ValueError('REPLY_CONTEXT_OR_DIGEST')
            # 非数值指令用固定标记，播报文本由固件选择。事实身份字段留空。
            packet = HEADER.pack(b'MR02', context.session, context.crc, issued_ms, expires,
                                 0, 0, 0, 0, 0, 0, status, 0, GATEWAY.encode(),
                                 bytes.fromhex(digest(facts)), 1) + b'!'
        else:
            text = answer_facts(facts, question).split('\n')[0]
            payload = encode(turn_id, digest(facts), text, issued_ms)
            packet = adapt_reply(payload, facts, question, context, self.clock_ms())
        await self.send('mpm/mic/v1/out', packet)
        return 'BROKER_PUBACK_ONLY_NOT_TTS_DONE'
