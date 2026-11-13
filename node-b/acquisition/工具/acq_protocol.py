"""通用多样本采集工具与数据协议 v1.0 核心规范、严格序列化、分段解卷绕与状态解码模块。

遵循《通用多样本采集工具与数据协议设计 v1.0》与《采集协议_v1.0_模板/README.md》：
- JSON RFC 8259：UTF-8，禁止 NaN/Infinity，禁止重复键，未知值为 null，超出 2^53-1 的整数用十进制字符串。
- CSV RFC 4180：UTF-8，逗号分隔，带表头，CRLF 行尾，空字段代表未知（null），不默填 0。
- 清单自引用防护：raw_manifest.json 与 manifest.json 均不收录自身。
- 严格区分 4 个状态模块：adc_driver、ecg_algorithm、resp_algorithm、ui。
"""
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

from stable_slot_export import unpack_slot_fields

PROTOCOL_VERSION = "1.0"
TOOL_VERSION = "acq/1.0.0"
MAX_SAFE_JSON_INT = (1 << 53) - 1  # 9007199254740991

DATASET_INDEX_HEADERS = [
    "dataset_id",
    "sample_id",
    "condition_id",
    "repeat_index",
    "run_id",
    "run_path",
    "session_sha256",
    "raw_manifest_sha256",
    "analysis_id",
    "identity_status",
    "integrity_status",
    "reference_status",
    "comparison_disposition",
    "reason",
]

SAMPLES_HEADERS = [
    "run_id",
    "boot_id",
    "segment_id",
    "source_seq",
    "device_tick_raw",
    "device_time_us",
    "irq_cycles_raw",
    "channel_id",
    "raw_code",
    "adc_status_raw",
    "source_flags_raw",
    "integrity",
    "provenance",
    "observation_count",
    "source_ref",
]

FIRMWARE_STATE_HEADERS = [
    "run_id",
    "boot_id",
    "segment_id",
    "observation_id",
    "module",
    "field",
    "value",
    "value_type",
    "unit",
    "valid",
    "sample_seq",
    "sample_tick_raw",
    "read_start_host_ns",
    "read_end_host_ns",
    "coherence",
    "source_ref",
]

REFERENCE_HEADERS = [
    "run_id",
    "reference_id",
    "reference_time_us",
    "device_time_us",
    "sync_uncertainty_us",
    "channel_id",
    "metric",
    "value",
    "unit",
    "reference_kind",
    "source_ref",
]

OBSERVATIONS_HEADERS = [
    "run_id",
    "boot_id",
    "segment_id",
    "source_seq",
    "observation_id",
    "source_path",
    "byte_offset",
    "byte_length",
    "record_sha256",
    "validation_status",
    "selection_status",
    "reason",
]

EVENT_REQUIRED_KEYS = [
    "event_id",
    "run_id",
    "boot_id",
    "segment_id",
    "type",
    "device_seq_start",
    "device_seq_end",
    "host_request_ns",
    "host_confirmation_ns",
    "details",
    "source_ref",
]

IDENTITY_STATUSES = {"VERIFIED", "UNKNOWN", "MISMATCH"}
INTEGRITY_STATUSES = {"PASS", "LIMITED", "INCOMPLETE", "FAIL", "NOT_EVALUATED"}
REFERENCE_STATUSES = {"SETPOINT", "INDEPENDENT", "NONE", "UNKNOWN"}
COMPARISON_DISPOSITIONS = {
    "INCLUDE_FOR_STATED_PURPOSE",
    "OBSERVATIONAL_ONLY",
    "EXCLUDE_FOR_STATED_PURPOSE",
}

DECLARED_INPUT_KINDS = {
    "ACTIVE_HARDWARE_SIMULATOR",
    "INTERNAL_TEST_SIGNAL",
    "SOFTWARE_FIXTURE",
    "PASSIVE_PHANTOM",
    "HUMAN_DECLARED",
    "UNKNOWN",
}

SAMPLE_INTEGRITY_KINDS = {
    "CONSISTENT_RECONSTRUCTION",
    "PUBLISHED_SNAPSHOT",
    "CRC_VERIFIED_FRAME",
    "UNVERIFIED",
}

STATE_MODULES = {"ecg_algorithm", "resp_algorithm", "ui", "adc_driver"}
COHERENCE_KINDS = {"LIVE_UNCOORDINATED", "HALTED_MEMORY_POINT", "FRAME_ASSOCIATED"}

EVENT_TYPES = {
    "SOURCE_GAP",
    "TX_GAP",
    "HOST_IO_ERROR",
    "CRC_ERROR",
    "CONFLICT",
    "PENDING",
    "BOOT_DETECTED",
    "TIME_AMBIGUOUS",
    "CONFIG_CHANGED",
    "INPUT_CHANGED",
    "HALT_REQUEST",
    "HALT_CONFIRMED",
    "RUN_REQUEST",
    "RUN_CONFIRMED",
}


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"JSON 存在重复键: {k!r}")
        result[k] = v
    return result


def _reject_nan_inf(constant: str):
    raise ValueError(f"JSON 禁止使用非有限常数: {constant}")


def _sanitize_for_strict_json(obj: Any) -> Any:
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int):
        if obj > MAX_SAFE_JSON_INT or obj < -MAX_SAFE_JSON_INT:
            return str(obj)
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"JSON 禁止写入 NaN 或 Infinity: {obj}")
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                k = str(k)
            out[k] = _sanitize_for_strict_json(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_strict_json(x) for x in obj]
    raise TypeError(f"不支持写入严格 JSON 的类型: {type(obj)!r}")


def load_strict_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nan_inf,
    )


def loads_strict_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nan_inf,
    )


def dumps_strict_json(obj: Any, indent: int | None = 2) -> str:
    sanitized = _sanitize_for_strict_json(obj)
    return json.dumps(sanitized, ensure_ascii=False, allow_nan=False, indent=indent)


def dump_strict_json(obj: Any, path: Path, indent: int | None = 2) -> str:
    text = dumps_strict_json(obj, indent=indent) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return sha256_bytes(text.encode("utf-8"))


def write_events_jsonl(events: list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for ev in events:
        ordered = {k: ev.get(k) for k in EVENT_REQUIRED_KEYS}
        for extra_k, extra_v in ev.items():
            if extra_k not in ordered:
                ordered[extra_k] = extra_v
        lines.append(dumps_strict_json(ordered, indent=None))
    content = ("\n".join(lines) + "\n") if lines else ""
    path.write_text(content, encoding="utf-8", newline="\n")
    return sha256_bytes(content.encode("utf-8"))


def read_events_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        obj = loads_strict_json(line)
        for k in EVENT_REQUIRED_KEYS:
            if k not in obj:
                raise ValueError(f"{path.name} 第 {idx} 行缺少必填字段 {k!r}")
        if obj["type"] not in EVENT_TYPES:
            raise ValueError(f"{path.name} 第 {idx} 行包含未知事件类型 {obj['type']!r}")
        events.append(obj)
    return events


def write_strict_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=headers,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\r\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            clean_row = {}
            for h in headers:
                val = row.get(h)
                if val is None:
                    clean_row[h] = ""
                elif isinstance(val, float) and not math.isfinite(val):
                    raise ValueError(f"CSV 禁止写入 NaN/Infinity: 字段 {h}")
                else:
                    clean_row[h] = val
            writer.writerow(clean_row)
    return sha256_file(path)


def read_strict_csv(path: Path, expected_headers: list[str] | None = None) -> tuple[list[str], list[dict[str, str]]]:
    raw_bytes = path.read_bytes()
    if b"\r\n" not in raw_bytes and len(raw_bytes) > 0:
        raise ValueError(f"CSV 文件 {path.name} 未采用 RFC 4180 CRLF 行尾")
    text = raw_bytes.decode("utf-8")
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        if expected_headers is not None and headers != expected_headers:
            raise ValueError(
                f"CSV 表头不匹配 ({path.name}): 实际={headers} != 预期={expected_headers}"
            )
        rows = list(reader)
    return headers, rows


def build_manifest(
    base_dir: Path,
    manifest_filename: str,
    target_subdir: str | None = None,
    external_evidence: list[dict] | None = None,
) -> dict:
    """构建 raw_manifest.json 或 manifest.json，严格排除自身。"""
    scan_root = (base_dir / target_subdir) if target_subdir else base_dir
    files_list = []
    if scan_root.exists():
        for p in sorted(scan_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base_dir).as_posix()
            if rel == manifest_filename or p.name == manifest_filename:
                continue
            files_list.append(
                {
                    "path": rel,
                    "size_bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
            )
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "manifest_type": manifest_filename,
        "created_utc": now_utc_iso(),
        "self_excluded": True,
        "files": files_list,
    }
    if external_evidence:
        manifest["external_local_evidence"] = external_evidence
    return manifest


def verify_manifest(base_dir: Path, manifest_filename: str) -> dict:
    manifest_path = base_dir / manifest_filename
    if not manifest_path.exists():
        return {
            "valid": False,
            "reason": f"缺少清单文件 {manifest_filename}",
            "checked_files": 0,
            "mismatches": [manifest_filename],
        }
    manifest = load_strict_json(manifest_path)
    files = manifest.get("files", [])
    mismatches = []
    for entry in files:
        rel_path = entry.get("path", "")
        if rel_path == manifest_filename or Path(rel_path).name == manifest_filename:
            mismatches.append(f"清单违背自引用排除规则，包含了自身: {rel_path}")
            continue
        if Path(rel_path).is_absolute():
            mismatches.append(f"清单内部路径必须为相对路径，发现绝对路径: {rel_path}")
            continue
        target = base_dir / rel_path
        if not target.exists():
            mismatches.append(f"文件缺失: {rel_path}")
            continue
        actual_size = target.stat().st_size
        expected_size = int(entry.get("size_bytes", -1))
        if actual_size != expected_size:
            mismatches.append(f"文件大小漂移 {rel_path}: 实际={actual_size}, 预期={expected_size}")
            continue
        actual_sha = sha256_file(target)
        if actual_sha != entry.get("sha256"):
            mismatches.append(f"SHA-256 漂移 {rel_path}: 实际={actual_sha}, 预期={entry.get('sha256')}")

    for ext in manifest.get("external_local_evidence", []) or []:
        ext_path = Path(ext.get("local_path", ""))
        if not ext_path.exists():
            mismatches.append(f"外部本地原件缺失: {ext_path}")
            continue
        actual_size = ext_path.stat().st_size
        if actual_size != int(ext.get("size_bytes", -1)):
            mismatches.append(f"外部原件大小漂移: {ext_path}")
            continue
        actual_sha = sha256_file(ext_path)
        if actual_sha != ext.get("sha256"):
            mismatches.append(f"外部原件 SHA-256 漂移: {ext_path}")

    return {
        "valid": len(mismatches) == 0,
        "reason": "ALL_HASHES_VERIFIED" if not mismatches else "; ".join(mismatches[:5]),
        "checked_files": len(files) + len(manifest.get("external_local_evidence", []) or []),
        "mismatches": mismatches,
        "manifest_sha256": sha256_file(manifest_path),
    }


def segment_and_unwrap_frames(
    run_id: str,
    frames_by_boot: dict[str, dict[int, bytes]],
    provenance_by_boot_seq: dict[tuple[str, int], str],
    integrity_by_boot_seq: dict[tuple[str, int], str],
    obs_count_by_boot_seq: dict[tuple[str, int], int],
    source_ref_by_boot_seq: dict[tuple[str, int], str],
    timebase_cfg: dict,
    analysis_cfg: dict | None = None,
) -> dict:
    """对每个 boot 的已认证帧进行连续段切分、u32 模回绕检验、生成 samples 行与段事件。"""
    analysis_cfg = analysis_cfg or {}
    tb_policy = analysis_cfg.get("timebase_policy", {})
    max_unambiguous_gap_ms = int(tb_policy.get("max_unambiguous_gap_ms", 12000))
    use_nominal_when_unverified = bool(
        tb_policy.get("use_nominal_tick_for_observation_when_unverified", True)
    )

    irq_hz_verified = timebase_cfg.get("irq_cycles_hz_verified")
    irq_hz_nominal = timebase_cfg.get("irq_cycles_hz_nominal")
    tick_hz_verified = timebase_cfg.get("device_tick_hz_verified")
    tick_hz_nominal = timebase_cfg.get("device_tick_hz_nominal")

    effective_irq_hz = irq_hz_verified or (irq_hz_nominal if use_nominal_when_unverified else None)
    effective_tick_hz = tick_hz_verified or (tick_hz_nominal if use_nominal_when_unverified else None)
    timebase_is_verified = (irq_hz_verified is not None) or (tick_hz_verified is not None)

    sample_rows = []
    segment_events = []
    segment_summaries = []
    seq_to_segment = {}

    for boot_id in sorted(frames_by_boot.keys()):
        frames = frames_by_boot[boot_id]
        seqs = sorted(frames.keys())
        if not seqs:
            continue

        seg_num = 1
        current_seg_id = f"seg_{seg_num:04d}"
        cum_cycles = 0
        cum_tick = 0
        prev_seq = None
        prev_ms = None
        prev_cycles = None
        prev_flags = None
        seg_time_ambiguous = False
        dwt_wrap_count = 0
        ms_wrap_count = 0

        seg_records = []

        def _flush_segment(seg_id: str, records: list[dict], wraps_dwt: int, wraps_ms: int, ambiguous: bool):
            if not records:
                return
            n_events = len(records)
            first_rec = records[0]
            last_rec = records[-1]
            span_us = None
            sps_endpoint = None
            if (
                n_events >= 2
                and first_rec["device_time_us"] is not None
                and last_rec["device_time_us"] is not None
                and last_rec["device_time_us"] > first_rec["device_time_us"]
            ):
                span_us = last_rec["device_time_us"] - first_rec["device_time_us"]
                # 第 6 节：平均采样率以同一连续段不同 source_seq 的采样事件计算 (N-1)/(t_last-t_first)
                sps_endpoint = (n_events - 1) / (span_us / 1e6)
            segment_summaries.append(
                {
                    "boot_id": boot_id,
                    "segment_id": seg_id,
                    "first_seq": first_rec["source_seq"],
                    "last_seq": last_rec["source_seq"],
                    "distinct_seq_events": n_events,
                    "first_tick_raw": first_rec["device_tick_raw"],
                    "last_tick_raw": last_rec["device_tick_raw"],
                    "span_us": span_us,
                    "endpoint_sps": sps_endpoint,
                    "dwt_wrap_count": wraps_dwt,
                    "tick_wrap_count": wraps_ms,
                    "time_ambiguous": ambiguous,
                    "timebase_verified": timebase_is_verified,
                }
            )

        for seq in seqs:
            slot = frames[seq]
            fields = unpack_slot_fields(slot)
            ms = fields["device_tick_raw"]
            cycles = fields["irq_cycles_raw"]
            flags = fields["flags_raw"]
            status = fields["status_raw"]

            need_new_seg = False
            new_seg_reason = None

            if prev_seq is not None:
                if seq > prev_seq + 1:
                    segment_events.append(
                        {
                            "boot_id": boot_id,
                            "segment_id": current_seg_id,
                            "type": "SOURCE_GAP",
                            "device_seq_start": prev_seq + 1,
                            "device_seq_end": seq - 1,
                            "details": {
                                "missing_count": seq - prev_seq - 1,
                                "prev_seq": prev_seq,
                                "next_seq": seq,
                            },
                            "source_ref": source_ref_by_boot_seq.get((boot_id, seq), ""),
                        }
                    )
                delta_ms = (ms - prev_ms) & 0xFFFFFFFF
                delta_cycles = (cycles - prev_cycles) & 0xFFFFFFFF

                # 检查是否发生跨多周期无法唯一解卷绕的停顿或标志位断段
                if flags != 0 and prev_flags == 0:
                    need_new_seg = True
                    new_seg_reason = f"source_flags_raw={flags:#x} 指示源断段"
                elif delta_ms > max_unambiguous_gap_ms:
                    need_new_seg = True
                    new_seg_reason = (
                        f"相邻样本 ms 模差 {delta_ms} ms 超过可唯一解卷绕门限 {max_unambiguous_gap_ms} ms"
                    )
                elif effective_irq_hz and effective_tick_hz:
                    cyc_ms = (delta_cycles / float(effective_irq_hz)) * 1000.0
                    # DWT 约 25565 ms 回绕一次；若 delta_ms < max_unambiguous_gap_ms 但与 cyc_ms 偏差 > 2000 ms，说明调试暂停或时钟失步
                    if abs(cyc_ms - delta_ms) > 2000.0:
                        need_new_seg = True
                        new_seg_reason = (
                            f"DWT 周期差折算 {cyc_ms:.2f} ms 与 ms 计数差 {delta_ms} ms 不一致，无法唯一解卷绕"
                        )

                if need_new_seg:
                    _flush_segment(
                        current_seg_id, seg_records, dwt_wrap_count, ms_wrap_count, seg_time_ambiguous
                    )
                    seg_num += 1
                    current_seg_id = f"seg_{seg_num:04d}"
                    cum_cycles = 0
                    cum_tick = 0
                    dwt_wrap_count = 0
                    ms_wrap_count = 0
                    seg_records = []
                    segment_events.append(
                        {
                            "boot_id": boot_id,
                            "segment_id": current_seg_id,
                            "type": "TIME_AMBIGUOUS",
                            "device_seq_start": prev_seq,
                            "device_seq_end": seq,
                            "details": {"reason": new_seg_reason},
                            "source_ref": source_ref_by_boot_seq.get((boot_id, seq), ""),
                        }
                    )
                else:
                    if cycles < prev_cycles:
                        dwt_wrap_count += 1
                    if ms < prev_ms:
                        ms_wrap_count += 1
                    cum_cycles += delta_cycles
                    cum_tick += delta_ms

            seq_to_segment[(boot_id, seq)] = current_seg_id

            # 计算 device_time_us：优先使用无歧义解卷绕的 DWT 周期，其次使用 tick
            if effective_irq_hz and float(effective_irq_hz) > 0:
                device_time_us = int(round((cum_cycles * 1_000_000.0) / float(effective_irq_hz)))
            elif effective_tick_hz and float(effective_tick_hz) > 0:
                device_time_us = int(round((cum_tick * 1_000_000.0) / float(effective_tick_hz)))
            else:
                device_time_us = None

            prov = provenance_by_boot_seq.get((boot_id, seq), "REPEATED_IDENTICAL_OBSERVATION")
            integ = integrity_by_boot_seq.get((boot_id, seq), "CONSISTENT_RECONSTRUCTION")
            obs_cnt = obs_count_by_boot_seq.get((boot_id, seq), 1)
            s_ref = source_ref_by_boot_seq.get((boot_id, seq), "")

            seg_records.append(
                {
                    "source_seq": seq,
                    "device_tick_raw": ms,
                    "device_time_us": device_time_us,
                    "irq_cycles_raw": cycles,
                    "resp_raw": fields["ch1_raw"],
                    "ecg_raw": fields["ch2_raw"],
                    "adc_status_raw": status,
                    "source_flags_raw": flags,
                }
            )

            # 逐采样点、逐通道长表：resp (CH1) 与 ecg (CH2) 共用同一 source_seq 与时刻
            for ch_id, raw_val in (("resp", fields["ch1_raw"]), ("ecg", fields["ch2_raw"])):
                sample_rows.append(
                    {
                        "run_id": run_id,
                        "boot_id": boot_id,
                        "segment_id": current_seg_id,
                        "source_seq": seq,
                        "device_tick_raw": ms,
                        "device_time_us": device_time_us,
                        "irq_cycles_raw": cycles,
                        "channel_id": ch_id,
                        "raw_code": raw_val,
                        "adc_status_raw": status,
                        "source_flags_raw": flags,
                        "integrity": integ,
                        "provenance": prov,
                        "observation_count": obs_cnt,
                        "source_ref": s_ref,
                    }
                )

            prev_seq = seq
            prev_ms = ms
            prev_cycles = cycles
            prev_flags = flags

        _flush_segment(current_seg_id, seg_records, dwt_wrap_count, ms_wrap_count, seg_time_ambiguous)

    return {
        "sample_rows": sample_rows,
        "segment_events": segment_events,
        "segment_summaries": segment_summaries,
        "seq_to_segment": seq_to_segment,
        "timebase_is_verified": timebase_is_verified,
    }


def _unpack_typed_value(ram: bytes, offset: int, value_type: str, endianness: str = "little") -> Any:
    prefix = "<" if endianness == "little" else ">"
    fmt_map = {
        "u8": "B",
        "i8": "b",
        "u16": "H",
        "i16": "h",
        "u32": "I",
        "i32": "i",
        "f32": "f",
    }
    if value_type not in fmt_map:
        raise ValueError(f"不支持的符号数据类型: {value_type!r}")
    val = struct.unpack_from(prefix + fmt_map[value_type], ram, offset)[0]
    if value_type == "f32" and not math.isfinite(val):
        return None
    return val


def decode_firmware_state_snapshot(
    ram: bytes,
    base_addr: int,
    symbol_table: list[dict],
    run_id: str,
    boot_id: str,
    segment_id: str,
    observation_id: int,
    coherence: str,
    source_ref: str,
    read_start_host_ns: int | str | None = None,
    read_end_host_ns: int | str | None = None,
) -> list[dict]:
    """根据经核对的 adapter_profile.symbol_table 严格按地址和有符号类型解码实机状态。"""
    if coherence not in COHERENCE_KINDS:
        raise ValueError(f"未知的 coherence 类型: {coherence!r}")

    # 第一遍：解码所有在当前 RAM 窗口范围内的字段值，以便关联 valid_field_ref 与 sample_tick_field_ref
    decoded_by_key = {}
    for sym in symbol_table:
        addr = int(str(sym["address"]), 0)
        byte_len = int(sym["byte_length"])
        offset = addr - base_addr
        if offset < 0 or offset + byte_len > len(ram):
            continue
        key = f"{sym['module']}.{sym['field']}"
        decoded_by_key[key] = _unpack_typed_value(
            ram, offset, sym["value_type"], sym.get("endianness", "little")
        )

    rows = []
    for sym in symbol_table:
        module = sym["module"]
        if module not in STATE_MODULES:
            raise ValueError(f"非法的固件状态模块名: {module!r}")
        field_name = sym["field"]
        key = f"{module}.{field_name}"
        if key not in decoded_by_key:
            continue
        val = decoded_by_key[key]

        valid_ref = sym.get("valid_field_ref")
        if valid_ref and valid_ref in decoded_by_key and decoded_by_key[valid_ref] is not None:
            valid_val = 1 if int(decoded_by_key[valid_ref]) != 0 else 0
        else:
            valid_val = None

        tick_ref = sym.get("sample_tick_field_ref")
        sample_tick_raw = decoded_by_key.get(tick_ref) if tick_ref else None

        seq_ref = sym.get("sample_seq_field_ref")
        sample_seq = decoded_by_key.get(seq_ref) if seq_ref else None

        rows.append(
            {
                "run_id": run_id,
                "boot_id": boot_id,
                "segment_id": segment_id,
                "observation_id": observation_id,
                "module": module,
                "field": field_name,
                "value": val,
                "value_type": sym["value_type"],
                "unit": sym.get("unit", ""),
                "valid": valid_val,
                "sample_seq": sample_seq,
                "sample_tick_raw": sample_tick_raw,
                "read_start_host_ns": str(read_start_host_ns) if read_start_host_ns is not None else None,
                "read_end_host_ns": str(read_end_host_ns) if read_end_host_ns is not None else None,
                "coherence": coherence,
                "source_ref": source_ref,
            }
        )
    return rows
