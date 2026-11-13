"""ECAP 连续传输候选协议（v1）编解码与有界流式解析器。

对应《通用多样本采集工具与数据协议设计 v1.0》第 9 节与第 12 节准入测试：
- 定长头 32 B，小端序，magic = b"ECAP"，wire_version = 1，header_len = 32
- payload_len <= 1024；CRC-32 覆盖头与 payload，与 binascii.crc32(data, 0) & 0xffffffff 一致
- 测试向量 b"123456789" -> 0xCBF43926
- SAMPLES (0x02)：每条 28 B (<IIIIiiI)，1 <= record_count <= 16，payload_len == record_count * 28
- METADATA (0x01) / STATE (0x03) / COUNTERS (0x04)：record_count == 0，有界 UTF-8 JSON
- 流式解析支持半包、连包、垃圾前缀、坏 CRC、超长包、未知版本与未知消息类型，逐字节重同步并记录被跳过区间。
"""
import binascii
from dataclasses import dataclass
import json
import struct

MAGIC = b"ECAP"
HEADER_FMT = "<4sBBHIQIIHH"
HEADER_LEN = 32
MAX_PAYLOAD_LEN = 1024
SAMPLE_REC_FMT = "<IIIIiiI"
SAMPLE_REC_LEN = 28

MSG_METADATA = 0x01
MSG_SAMPLES = 0x02
MSG_STATE = 0x03
MSG_COUNTERS = 0x04

KNOWN_MSG_TYPES = {MSG_METADATA, MSG_SAMPLES, MSG_STATE, MSG_COUNTERS}


def crc32_ieee(data: bytes) -> int:
    return binascii.crc32(data, 0) & 0xFFFFFFFF


assert crc32_ieee(b"123456789") == 0xCBF43926, "CRC-32 测试向量校验失败"


@dataclass(frozen=True)
class EcapFrame:
    wire_version: int
    message_type: int
    stream_token: int
    packet_seq: int
    profile_id: int
    record_count: int
    payload: bytes
    crc32: int
    byte_offset: int
    byte_length: int
    status: str  # VALID_V1 / UNKNOWN_VERSION / UNKNOWN_MSG_TYPE
    decoded: object = None


@dataclass(frozen=True)
class EcapSkipEvent:
    byte_offset: int
    byte_length: int
    reason: str
    raw_hex_preview: str


def encode_ecap_frame(
    message_type: int,
    stream_token: int,
    packet_seq: int,
    profile_id: int,
    payload: bytes,
    record_count: int = 0,
    wire_version: int = 1,
    reserved: int = 0,
) -> bytes:
    if len(payload) > MAX_PAYLOAD_LEN:
        raise ValueError(f"payload 长度 {len(payload)} 超过上限 {MAX_PAYLOAD_LEN}")
    header = struct.pack(
        HEADER_FMT,
        MAGIC,
        wire_version & 0xFF,
        message_type & 0xFF,
        HEADER_LEN,
        len(payload),
        stream_token & 0xFFFFFFFFFFFFFFFF,
        packet_seq & 0xFFFFFFFF,
        profile_id & 0xFFFFFFFF,
        record_count & 0xFFFF,
        reserved & 0xFFFF,
    )
    body = header + payload
    crc = crc32_ieee(body)
    return body + struct.pack("<I", crc)


def encode_samples_payload(records: list[dict]) -> bytes:
    if not (1 <= len(records) <= 16):
        raise ValueError("SAMPLES record_count 必须在 1..16 之间")
    chunks = []
    for r in records:
        status = int(r["adc_status"])
        ch1 = int(r["ch1_raw"])
        ch2 = int(r["ch2_raw"])
        if status < 0 or (status >> 24) != 0:
            raise ValueError("adc_status 高 8 位必须为 0")
        if not (-8388608 <= ch1 <= 8388607 and -8388608 <= ch2 <= 8388607):
            raise ValueError("通道原始码超出 signed 24-bit 范围")
        chunks.append(
            struct.pack(
                SAMPLE_REC_FMT,
                int(r["source_seq"]) & 0xFFFFFFFF,
                int(r["sample_ms"]) & 0xFFFFFFFF,
                int(r["irq_cycles"]) & 0xFFFFFFFF,
                status,
                ch1,
                ch2,
                int(r["source_flags"]) & 0xFFFFFFFF,
            )
        )
    return b"".join(chunks)


class EcapStreamParser:
    def __init__(self):
        self.buf = bytearray()
        self.base_offset = 0
        self.frames: list[EcapFrame] = []
        self.skips: list[EcapSkipEvent] = []

    def _record_skip(self, start_offset: int, data: bytes, reason: str):
        if not data:
            return
        preview = data[:32].hex()
        self.skips.append(
            EcapSkipEvent(
                byte_offset=start_offset,
                byte_length=len(data),
                reason=reason,
                raw_hex_preview=preview,
            )
        )

    def feed(self, chunk: bytes, final: bool = False):
        self.buf.extend(chunk)
        idx = 0
        garbage_start = None
        garbage_reason = "GARBAGE_PREFIX"

        while idx <= len(self.buf):
            pos = self.buf.find(MAGIC, idx)
            if pos == -1:
                # 保留末尾最多 3 字节以防 MAGIC 半包被截断
                keep = 0 if final else min(3, len(self.buf) - idx)
                end_skip = len(self.buf) - keep
                if garbage_start is not None and end_skip > garbage_start:
                    self._record_skip(
                        self.base_offset + garbage_start,
                        bytes(self.buf[garbage_start:end_skip]),
                        garbage_reason,
                    )
                    garbage_start = None
                elif end_skip > idx:
                    self._record_skip(
                        self.base_offset + idx,
                        bytes(self.buf[idx:end_skip]),
                        "GARBAGE_PREFIX",
                    )
                idx = end_skip
                break

            if pos > idx and garbage_start is None:
                self._record_skip(
                    self.base_offset + idx,
                    bytes(self.buf[idx:pos]),
                    "GARBAGE_PREFIX",
                )
            elif garbage_start is not None and pos > garbage_start:
                self._record_skip(
                    self.base_offset + garbage_start,
                    bytes(self.buf[garbage_start:pos]),
                    garbage_reason,
                )
                garbage_start = None

            idx = pos
            # 检查头是否够 32 B
            if len(self.buf) - idx < HEADER_LEN:
                if final:
                    self._record_skip(
                        self.base_offset + idx,
                        bytes(self.buf[idx:]),
                        "TRUNCATED_HEADER_EOF",
                    )
                    idx = len(self.buf)
                break

            (
                magic,
                wire_version,
                msg_type,
                header_len,
                payload_len,
                stream_token,
                packet_seq,
                profile_id,
                record_count,
                reserved,
            ) = struct.unpack_from(HEADER_FMT, self.buf, idx)

            # 基本头合法性检验
            if header_len != HEADER_LEN or payload_len > MAX_PAYLOAD_LEN or reserved != 0:
                if garbage_start is None:
                    garbage_start = idx
                    garbage_reason = "INVALID_HEADER_FIELDS"
                idx += 1
                continue

            total_len = HEADER_LEN + payload_len + 4
            if len(self.buf) - idx < total_len:
                if final:
                    self._record_skip(
                        self.base_offset + idx,
                        bytes(self.buf[idx:]),
                        "TRUNCATED_FRAME_EOF",
                    )
                    idx = len(self.buf)
                break

            frame_bytes = bytes(self.buf[idx : idx + HEADER_LEN + payload_len])
            expected_crc = struct.unpack_from("<I", self.buf, idx + HEADER_LEN + payload_len)[0]
            actual_crc = crc32_ieee(frame_bytes)
            if actual_crc != expected_crc:
                if garbage_start is None:
                    garbage_start = idx
                    garbage_reason = "CRC_ERROR"
                idx += 1
                continue

            payload = bytes(self.buf[idx + HEADER_LEN : idx + HEADER_LEN + payload_len])

            # 未知版本不解码为 v1，保存原件并标记
            if wire_version != 1:
                if garbage_start is not None:
                    self._record_skip(
                        self.base_offset + garbage_start,
                        bytes(self.buf[garbage_start:idx]),
                        garbage_reason,
                    )
                    garbage_start = None
                self.frames.append(
                    EcapFrame(
                        wire_version=wire_version,
                        message_type=msg_type,
                        stream_token=stream_token,
                        packet_seq=packet_seq,
                        profile_id=profile_id,
                        record_count=record_count,
                        payload=payload,
                        crc32=expected_crc,
                        byte_offset=self.base_offset + idx,
                        byte_length=total_len,
                        status="UNKNOWN_VERSION",
                        decoded=None,
                    )
                )
                idx += total_len
                continue

            # 未知消息类型保留原件并标覆盖限制
            if msg_type not in KNOWN_MSG_TYPES:
                if garbage_start is not None:
                    self._record_skip(
                        self.base_offset + garbage_start,
                        bytes(self.buf[garbage_start:idx]),
                        garbage_reason,
                    )
                    garbage_start = None
                self.frames.append(
                    EcapFrame(
                        wire_version=wire_version,
                        message_type=msg_type,
                        stream_token=stream_token,
                        packet_seq=packet_seq,
                        profile_id=profile_id,
                        record_count=record_count,
                        payload=payload,
                        crc32=expected_crc,
                        byte_offset=self.base_offset + idx,
                        byte_length=total_len,
                        status="UNKNOWN_MSG_TYPE",
                        decoded=None,
                    )
                )
                idx += total_len
                continue

            # v1 已知消息类型内容校验
            valid_payload = True
            decoded_obj = None
            if msg_type == MSG_SAMPLES:
                if not (1 <= record_count <= 16) or payload_len != record_count * SAMPLE_REC_LEN:
                    valid_payload = False
                    garbage_reason = "INVALID_SAMPLES_LAYOUT"
                else:
                    recs = []
                    for r_i in range(record_count):
                        (
                            s_seq,
                            s_ms,
                            s_cyc,
                            s_stat,
                            ch1,
                            ch2,
                            s_flg,
                        ) = struct.unpack_from(SAMPLE_REC_FMT, payload, r_i * SAMPLE_REC_LEN)
                        if (s_stat >> 24) != 0 or not (
                            -8388608 <= ch1 <= 8388607 and -8388608 <= ch2 <= 8388607
                        ):
                            valid_payload = False
                            garbage_reason = "INVALID_SAMPLE_FIELD_RANGE"
                            break
                        recs.append(
                            {
                                "source_seq": s_seq,
                                "sample_ms": s_ms,
                                "irq_cycles": s_cyc,
                                "adc_status": s_stat,
                                "ch1_raw": ch1,
                                "ch2_raw": ch2,
                                "source_flags": s_flg,
                            }
                        )
                    decoded_obj = recs
            else:
                if record_count != 0:
                    valid_payload = False
                    garbage_reason = "NONZERO_RECORD_COUNT_FOR_JSON_MSG"
                else:
                    try:
                        decoded_obj = json.loads(payload.decode("utf-8"))
                    except Exception:
                        valid_payload = False
                        garbage_reason = "INVALID_JSON_PAYLOAD"

            if not valid_payload:
                if garbage_start is None:
                    garbage_start = idx
                idx += 1
                continue

            if garbage_start is not None:
                self._record_skip(
                    self.base_offset + garbage_start,
                    bytes(self.buf[garbage_start:idx]),
                    garbage_reason,
                )
                garbage_start = None

            self.frames.append(
                EcapFrame(
                    wire_version=wire_version,
                    message_type=msg_type,
                    stream_token=stream_token,
                    packet_seq=packet_seq,
                    profile_id=profile_id,
                    record_count=record_count,
                    payload=payload,
                    crc32=expected_crc,
                    byte_offset=self.base_offset + idx,
                    byte_length=total_len,
                    status="VALID_V1",
                    decoded=decoded_obj,
                )
            )
            idx += total_len

        if idx > 0:
            del self.buf[:idx]
            self.base_offset += idx
