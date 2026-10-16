"""只验证/重建已读取的槽数据；本模块不连接J-Link、不复位、不烧录。

v1.0 协议增强规则（对应《通用多样本采集工具与数据协议设计 v1.0》第 6、8、12 节）：
1. 每个运行槽块必须精确 3072 B，记录真实 IO 顺序与区间。
2. 同一 boot/segment 内保存完整 24 B 的所有版本；A 出现至少两次且其它版本均只出现一次时可选 A，仍保留冲突。
3. 若两个不同版本均出现至少两次（>=2），停止该序号的一致性认证（记入 multi_repeat_conflicts 与 pending），不按票数大小选取。
4. 单次版本标 pending；全零空槽（empty_zero_slots）与非零非法槽（invalid_nonzero_slots）分开统计与记录。
5. 暂停尾段只读取同一份 RAM 的 head/slots，采用已发布最后 127 槽规则 [max(0, head-127), head)，避开 head%128 潜在写入槽。
6. 已认证版本与暂停版不一致时停止该序号认证并记入 paused_conflicts（raise_on_paused_conflict=True 时抛出异常）。
7. 跨复位序号重用与跨复位混合块隔离：
   - 若单次槽块内部跨度超过环形容量上界（同块混有复位前高序号与复位后低序号），标为 CROSS_RESET_AMBIGUOUS，boot_id/segment_id 留空，不合并进稳定样本；
   - 若新槽块最大序号回退至当前启动已观测最大序号之下，判定发生复位重启，自动分配新 boot_id，按 (boot_id, source_seq) 独立重建。
"""
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import struct

SLOT_SIZE = 24
CAPACITY = 128


@dataclass(frozen=True)
class SlotObservation:
    observation_id: int
    source_path: str
    byte_offset: int
    byte_length: int
    record_sha256: str
    source_seq: int
    status_raw: int
    flags_raw: int
    irq_cycles_raw: int
    device_tick_raw: int
    ch1_raw: int
    ch2_raw: int
    validation_status: str  # VALID_FORMAT / EMPTY_ZERO_SLOT / INVALID_NONZERO_SLOT / POTENTIAL_OVERWRITE_EXCLUDED / CROSS_RESET_AMBIGUOUS
    is_paused_snapshot: bool = False
    slot_index: int = -1
    boot_id: str = ""
    chunk_index: int = -1


@dataclass(frozen=True)
class Selection:
    frames: dict
    pending: tuple
    conflicts: tuple
    single_reads: tuple
    multi_repeat_conflicts: tuple = ()
    paused_conflicts: tuple = ()
    provenance_by_seq: dict = field(default_factory=dict)
    integrity_by_seq: dict = field(default_factory=dict)
    observation_count_by_seq: dict = field(default_factory=dict)
    conflict_details: dict = field(default_factory=dict)
    boots: tuple = ("boot_0001",)
    frames_by_boot: dict = field(default_factory=dict)
    pending_by_boot: dict = field(default_factory=dict)
    conflicts_by_boot: dict = field(default_factory=dict)
    multi_repeat_by_boot: dict = field(default_factory=dict)
    paused_conflicts_by_boot: dict = field(default_factory=dict)
    provenance_by_boot_seq: dict = field(default_factory=dict)
    integrity_by_boot_seq: dict = field(default_factory=dict)
    observation_count_by_boot_seq: dict = field(default_factory=dict)
    conflict_details_by_boot_seq: dict = field(default_factory=dict)
    boot_events: tuple = ()
    ambiguous_reset_chunks: tuple = ()


def s24_be(blob: bytes) -> int:
    val = int.from_bytes(blob, "big")
    return val - 0x1000000 if (val & 0x800000) else val


def unpack_slot_fields(slot: bytes) -> dict:
    status_raw = int.from_bytes(slot[:3], "big")
    ch1_raw = s24_be(slot[3:6])
    ch2_raw = s24_be(slot[6:9])
    flags_raw = slot[9]
    padding = slot[10:12]
    seq, irq_cycles, sample_ms = struct.unpack_from("<III", slot, 12)
    return {
        "status_raw": status_raw,
        "ch1_raw": ch1_raw,
        "ch2_raw": ch2_raw,
        "flags_raw": flags_raw,
        "padding": padding,
        "source_seq": seq,
        "irq_cycles_raw": irq_cycles,
        "device_tick_raw": sample_ms,
    }


class StableSlots:
    def __init__(self, raise_on_paused_conflict: bool = True):
        self.versions = {}  # 兼容单 boot 访问：当前/主 boot 的 {seq: Counter}
        self.versions_by_boot = {"boot_0001": {}}
        self.atomic = {}
        self.atomic_by_boot = {"boot_0001": {}}
        self.empty = 0  # 兼容旧属性：等于 empty_zero_slots + invalid_nonzero_slots
        self.empty_zero_slots = 0
        self.invalid_nonzero_slots = 0
        self.cross_reset_ambiguous_slots = 0
        self.invalid_slot_records = []
        self.observations = []
        self.boot_events = []
        self.ambiguous_reset_chunks = []
        self._next_obs_id = 1
        self._chunk_counter = 0
        self._current_boot_num = 1
        self._current_boot_id = "boot_0001"
        self._current_boot_max_seq = 0
        self.raise_on_paused_conflict = raise_on_paused_conflict

    @staticmethod
    def classify_slot(slot: bytes) -> str:
        if len(slot) != SLOT_SIZE:
            return "INVALID_LENGTH"
        if not any(slot):
            return "EMPTY_ZERO_SLOT"
        status = int.from_bytes(slot[:3], "big")
        seq = struct.unpack_from("<I", slot, 12)[0]
        if (status & 0xF01FFF) == 0xC00000 and seq != 0:
            return "VALID_FORMAT"
        return "INVALID_NONZERO_SLOT"

    @staticmethod
    def valid(slot: bytes) -> bool:
        return StableSlots.classify_slot(slot) == "VALID_FORMAT"

    def start_new_boot(self, reason: str, source_path: str = "", prev_max_seq: int = 0, new_min_seq: int = 0) -> str:
        self._current_boot_num += 1
        self._current_boot_id = f"boot_{self._current_boot_num:04d}"
        self._current_boot_max_seq = 0
        self.versions_by_boot.setdefault(self._current_boot_id, {})
        self.atomic_by_boot.setdefault(self._current_boot_id, {})
        self.boot_events.append(
            {
                "boot_id": self._current_boot_id,
                "reason": reason,
                "source_path": source_path,
                "prev_boot_max_seq": prev_max_seq,
                "new_boot_min_seq": new_min_seq,
            }
        )
        return self._current_boot_id

    def add_running_chunk(self, blob: bytes, source_path: str = "memory_chunk"):
        if len(blob) != SLOT_SIZE * CAPACITY:
            raise ValueError("槽块长度错误，拒绝把部分读取当成完整快照")
        chunk_idx = self._chunk_counter
        self._chunk_counter += 1

        # 先预扫描本块内的合法格式槽，判断是否存在跨复位混叠或整块复位重启
        valid_seqs = []
        parsed_slots = []
        for index in range(CAPACITY):
            offset = index * SLOT_SIZE
            slot = blob[offset : offset + SLOT_SIZE]
            kind = self.classify_slot(slot)
            fields = unpack_slot_fields(slot)
            parsed_slots.append((index, offset, slot, kind, fields))
            if kind == "VALID_FORMAT":
                valid_seqs.append(fields["source_seq"])

        chunk_is_ambiguous_reset = False
        if valid_seqs:
            min_seq = min(valid_seqs)
            max_seq = max(valid_seqs)
            # 同一 128 槽环形缓冲在单次启动内序号跨度不可能超过 CAPACITY (128)。
            # 若 max_seq - min_seq >= CAPACITY * 2，说明槽块内同时残留复位前高序号与复位后低序号，归属无法唯一确定。
            if max_seq - min_seq >= CAPACITY * 2:
                chunk_is_ambiguous_reset = True
                self.ambiguous_reset_chunks.append(
                    {
                        "chunk_index": chunk_idx,
                        "source_path": source_path,
                        "min_seq": min_seq,
                        "max_seq": max_seq,
                        "reason": "单次槽块内同时存在跨代/跨复位高低序号，无法确认槽归属",
                    }
                )
            elif self._current_boot_max_seq > 0 and max_seq < self._current_boot_max_seq:
                # 整块的最大序号已回退到当前 boot 历史最大序号之下，说明发生了复位且新启动已开始编号
                self.start_new_boot(
                    reason="检测到槽块最大 source_seq 回退，判定发生设备复位重启",
                    source_path=source_path,
                    prev_max_seq=self._current_boot_max_seq,
                    new_min_seq=min_seq,
                )

        for index, offset, slot, kind, fields in parsed_slots:
            rec_sha = hashlib.sha256(slot).hexdigest()
            obs_id = self._next_obs_id
            self._next_obs_id += 1

            if kind == "EMPTY_ZERO_SLOT":
                self.empty_zero_slots += 1
                self.empty += 1
                self.observations.append(
                    SlotObservation(
                        observation_id=obs_id,
                        source_path=source_path,
                        byte_offset=offset,
                        byte_length=SLOT_SIZE,
                        record_sha256=rec_sha,
                        source_seq=0,
                        status_raw=fields["status_raw"],
                        flags_raw=fields["flags_raw"],
                        irq_cycles_raw=fields["irq_cycles_raw"],
                        device_tick_raw=fields["device_tick_raw"],
                        ch1_raw=fields["ch1_raw"],
                        ch2_raw=fields["ch2_raw"],
                        validation_status="EMPTY_ZERO_SLOT",
                        is_paused_snapshot=False,
                        slot_index=index,
                        boot_id="",
                        chunk_index=chunk_idx,
                    )
                )
                continue

            if kind == "INVALID_NONZERO_SLOT":
                self.invalid_nonzero_slots += 1
                self.empty += 1
                obs = SlotObservation(
                    observation_id=obs_id,
                    source_path=source_path,
                    byte_offset=offset,
                    byte_length=SLOT_SIZE,
                    record_sha256=rec_sha,
                    source_seq=fields["source_seq"],
                    status_raw=fields["status_raw"],
                    flags_raw=fields["flags_raw"],
                    irq_cycles_raw=fields["irq_cycles_raw"],
                    device_tick_raw=fields["device_tick_raw"],
                    ch1_raw=fields["ch1_raw"],
                    ch2_raw=fields["ch2_raw"],
                    validation_status="INVALID_NONZERO_SLOT",
                    is_paused_snapshot=False,
                    slot_index=index,
                    boot_id="",
                    chunk_index=chunk_idx,
                )
                self.invalid_slot_records.append(obs)
                self.observations.append(obs)
                continue

            if chunk_is_ambiguous_reset:
                self.cross_reset_ambiguous_slots += 1
                self.observations.append(
                    SlotObservation(
                        observation_id=obs_id,
                        source_path=source_path,
                        byte_offset=offset,
                        byte_length=SLOT_SIZE,
                        record_sha256=rec_sha,
                        source_seq=fields["source_seq"],
                        status_raw=fields["status_raw"],
                        flags_raw=fields["flags_raw"],
                        irq_cycles_raw=fields["irq_cycles_raw"],
                        device_tick_raw=fields["device_tick_raw"],
                        ch1_raw=fields["ch1_raw"],
                        ch2_raw=fields["ch2_raw"],
                        validation_status="CROSS_RESET_AMBIGUOUS",
                        is_paused_snapshot=False,
                        slot_index=index,
                        boot_id="",
                        chunk_index=chunk_idx,
                    )
                )
                continue

            seq = fields["source_seq"]
            if seq > self._current_boot_max_seq:
                self._current_boot_max_seq = seq
            boot_versions = self.versions_by_boot.setdefault(self._current_boot_id, {})
            boot_versions.setdefault(seq, Counter())[slot] += 1
            if self._current_boot_id == "boot_0001":
                self.versions = boot_versions
            self.observations.append(
                SlotObservation(
                    observation_id=obs_id,
                    source_path=source_path,
                    byte_offset=offset,
                    byte_length=SLOT_SIZE,
                    record_sha256=rec_sha,
                    source_seq=seq,
                    status_raw=fields["status_raw"],
                    flags_raw=fields["flags_raw"],
                    irq_cycles_raw=fields["irq_cycles_raw"],
                    device_tick_raw=fields["device_tick_raw"],
                    ch1_raw=fields["ch1_raw"],
                    ch2_raw=fields["ch2_raw"],
                    validation_status="VALID_FORMAT",
                    is_paused_snapshot=False,
                    slot_index=index,
                    boot_id=self._current_boot_id,
                    chunk_index=chunk_idx,
                )
            )

    def add_paused_snapshot(
        self,
        blob: bytes,
        published_head: int,
        source_path: str = "final-paused-ram.bin",
        base_offset: int = 0,
    ):
        """仅在CPU已确认暂停后调用；head来自该同一份RAM快照。

        head计数Push发布位置，不与IRQ序号作等同。短采集从复位开始，本接口不
        推测跨2^32次Push的历史；最后127槽均已发布，避开head%128的潜在写入槽。
        """
        if len(blob) != SLOT_SIZE * CAPACITY or not 0 <= published_head < 2**31:
            raise ValueError("暂停快照或发布计数不符合本轮短采集约束")

        boot_atomic = self.atomic_by_boot.setdefault(self._current_boot_id, {})
        if self._current_boot_id == "boot_0001":
            self.atomic = boot_atomic

        excluded_index = published_head & (CAPACITY - 1) if published_head >= CAPACITY else None
        if excluded_index is not None:
            offset = excluded_index * SLOT_SIZE
            slot = blob[offset : offset + SLOT_SIZE]
            fields = unpack_slot_fields(slot)
            obs_id = self._next_obs_id
            self._next_obs_id += 1
            self.observations.append(
                SlotObservation(
                    observation_id=obs_id,
                    source_path=source_path,
                    byte_offset=base_offset + offset,
                    byte_length=SLOT_SIZE,
                    record_sha256=hashlib.sha256(slot).hexdigest(),
                    source_seq=fields["source_seq"],
                    status_raw=fields["status_raw"],
                    flags_raw=fields["flags_raw"],
                    irq_cycles_raw=fields["irq_cycles_raw"],
                    device_tick_raw=fields["device_tick_raw"],
                    ch1_raw=fields["ch1_raw"],
                    ch2_raw=fields["ch2_raw"],
                    validation_status="POTENTIAL_OVERWRITE_EXCLUDED",
                    is_paused_snapshot=True,
                    slot_index=excluded_index,
                    boot_id=self._current_boot_id,
                    chunk_index=self._chunk_counter,
                )
            )

        for number in range(max(0, published_head - (CAPACITY - 1)), published_head):
            index = number & (CAPACITY - 1)
            offset = index * SLOT_SIZE
            slot = blob[offset : offset + SLOT_SIZE]
            if not self.valid(slot):
                raise ValueError("已发布槽格式无效，不能认证完整导出")
            fields = unpack_slot_fields(slot)
            seq = fields["source_seq"]
            old = boot_atomic.get(seq)
            if old is not None and old != slot:
                raise ValueError("暂停快照同序号内容冲突，可能存在复位/身份漂移")
            boot_atomic[seq] = slot
            obs_id = self._next_obs_id
            self._next_obs_id += 1
            self.observations.append(
                SlotObservation(
                    observation_id=obs_id,
                    source_path=source_path,
                    byte_offset=base_offset + offset,
                    byte_length=SLOT_SIZE,
                    record_sha256=hashlib.sha256(slot).hexdigest(),
                    source_seq=seq,
                    status_raw=fields["status_raw"],
                    flags_raw=fields["flags_raw"],
                    irq_cycles_raw=fields["irq_cycles_raw"],
                    device_tick_raw=fields["device_tick_raw"],
                    ch1_raw=fields["ch1_raw"],
                    ch2_raw=fields["ch2_raw"],
                    validation_status="VALID_FORMAT",
                    is_paused_snapshot=True,
                    slot_index=index,
                    boot_id=self._current_boot_id,
                    chunk_index=self._chunk_counter,
                )
            )

    def _select_for_boot(self, boot_id: str, versions_map: dict, atomic_map: dict) -> dict:
        frames = {}
        pending = []
        conflicts = []
        singles = []
        multi_repeat_conflicts = []
        paused_conflicts = []
        provenance_by_seq = {}
        integrity_by_seq = {}
        observation_count_by_seq = {}
        conflict_details = {}

        field_ranges = {
            "status": range(0, 3),
            "ch1": range(3, 6),
            "ch2": range(6, 9),
            "flags": range(9, 10),
            "padding": range(10, 12),
            "seq": range(12, 16),
            "cycles": range(16, 20),
            "ms": range(20, 24),
        }

        for seq, versions in versions_map.items():
            rank = versions.most_common()
            total_obs = sum(versions.values())
            observation_count_by_seq[seq] = total_obs

            if len(rank) > 1:
                conflicts.append(seq)
                byte_changes = [i for i in range(SLOT_SIZE) if len({v[i] for v in versions}) > 1]
                changed_fields = [
                    name for name, rng in field_ranges.items() if any(i in byte_changes for i in rng)
                ]
                conflict_details[seq] = {
                    "boot_id": boot_id,
                    "version_counts": [n for _, n in rank],
                    "version_hashes": [hashlib.sha256(v).hexdigest() for v, _ in rank],
                    "changed_fields": changed_fields,
                }

            if total_obs == 1:
                singles.append(seq)

            # v1.0 第 8 节规则 2 & 3：
            # A 出现至少两次且其它版本均只出现一次（即次高票 < 2）时可选 A；
            # 若两个不同版本均出现至少两次（rank[1][1] >= 2），停止该序号的一致性认证，不按票数大小选取！
            if len(rank) > 1 and rank[1][1] >= 2:
                multi_repeat_conflicts.append(seq)
                pending.append(seq)
            elif rank[0][1] >= 2 and (len(rank) == 1 or rank[1][1] == 1):
                frames[seq] = rank[0][0]
                provenance_by_seq[seq] = (
                    "REPEATED_CONSENSUS_WITH_SINGLE_CONFLICT"
                    if len(rank) > 1
                    else "REPEATED_IDENTICAL_OBSERVATION"
                )
                integrity_by_seq[seq] = "CONSISTENT_RECONSTRUCTION"
            else:
                pending.append(seq)

        for seq, slot in atomic_map.items():
            observation_count_by_seq[seq] = observation_count_by_seq.get(seq, 0) + 1
            if seq in multi_repeat_conflicts:
                paused_conflicts.append(seq)
                if self.raise_on_paused_conflict:
                    raise ValueError(f"序号 {seq} 存在多版本重复冲突，拒绝通过暂停快照强行认证")
                continue
            if seq in frames and frames[seq] != slot:
                paused_conflicts.append(seq)
                if seq not in conflicts:
                    conflicts.append(seq)
                del frames[seq]
                if seq not in pending:
                    pending.append(seq)
                if self.raise_on_paused_conflict:
                    raise ValueError("已稳定版本与暂停发布版本冲突，保留原件并停止导出")
                continue
            if seq in frames and frames[seq] == slot:
                provenance_by_seq[seq] = "REPEATED_AND_PAUSED_PUBLISHED_TAIL"
                integrity_by_seq[seq] = "CONSISTENT_RECONSTRUCTION"
                continue
            if seq in versions_map:
                running_versions = list(versions_map[seq].keys())
                if len(running_versions) == 1 and running_versions[0] == slot:
                    frames[seq] = slot
                    provenance_by_seq[seq] = "SINGLE_RUNNING_PLUS_PAUSED_TAIL"
                    integrity_by_seq[seq] = "CONSISTENT_RECONSTRUCTION"
                    if seq in pending:
                        pending.remove(seq)
                else:
                    paused_conflicts.append(seq)
                    if seq not in conflicts:
                        conflicts.append(seq)
                    if self.raise_on_paused_conflict:
                        raise ValueError("单次运行观察版本与暂停发布版本冲突，保留原件并停止导出")
            else:
                frames[seq] = slot
                provenance_by_seq[seq] = "PAUSED_PUBLISHED_TAIL_127"
                integrity_by_seq[seq] = "PUBLISHED_SNAPSHOT"
                if seq in pending:
                    pending.remove(seq)

        return {
            "frames": dict(sorted(frames.items())),
            "pending": tuple(sorted(pending)),
            "conflicts": tuple(sorted(conflicts)),
            "single_reads": tuple(sorted(singles)),
            "multi_repeat_conflicts": tuple(sorted(multi_repeat_conflicts)),
            "paused_conflicts": tuple(sorted(paused_conflicts)),
            "provenance_by_seq": provenance_by_seq,
            "integrity_by_seq": integrity_by_seq,
            "observation_count_by_seq": observation_count_by_seq,
            "conflict_details": conflict_details,
        }

    def select(self) -> Selection:
        # 兼容外部直接修改 self.versions 或 self.atomic 的单启动测试
        if self.versions and not self.versions_by_boot.get("boot_0001"):
            self.versions_by_boot["boot_0001"] = self.versions
        if self.atomic and not self.atomic_by_boot.get("boot_0001"):
            self.atomic_by_boot["boot_0001"] = self.atomic

        active_boots = [
            b
            for b in sorted(self.versions_by_boot.keys())
            if self.versions_by_boot.get(b) or self.atomic_by_boot.get(b)
        ]
        if not active_boots:
            active_boots = ["boot_0001"]

        frames_by_boot = {}
        pending_by_boot = {}
        conflicts_by_boot = {}
        multi_repeat_by_boot = {}
        paused_conflicts_by_boot = {}
        provenance_by_boot_seq = {}
        integrity_by_boot_seq = {}
        observation_count_by_boot_seq = {}
        conflict_details_by_boot_seq = {}

        for b in active_boots:
            res = self._select_for_boot(
                b,
                self.versions_by_boot.get(b, {}),
                self.atomic_by_boot.get(b, {}),
            )
            frames_by_boot[b] = res["frames"]
            pending_by_boot[b] = res["pending"]
            conflicts_by_boot[b] = res["conflicts"]
            multi_repeat_by_boot[b] = res["multi_repeat_conflicts"]
            paused_conflicts_by_boot[b] = res["paused_conflicts"]
            for seq, val in res["provenance_by_seq"].items():
                provenance_by_boot_seq[(b, seq)] = val
            for seq, val in res["integrity_by_seq"].items():
                integrity_by_boot_seq[(b, seq)] = val
            for seq, val in res["observation_count_by_seq"].items():
                observation_count_by_boot_seq[(b, seq)] = val
            for seq, val in res["conflict_details"].items():
                conflict_details_by_boot_seq[(b, seq)] = val

        primary_boot = active_boots[0]
        primary = self._select_for_boot(
            primary_boot,
            self.versions_by_boot.get(primary_boot, {}),
            self.atomic_by_boot.get(primary_boot, {}),
        )

        return Selection(
            frames=primary["frames"],
            pending=primary["pending"],
            conflicts=primary["conflicts"],
            single_reads=primary["single_reads"],
            multi_repeat_conflicts=primary["multi_repeat_conflicts"],
            paused_conflicts=primary["paused_conflicts"],
            provenance_by_seq=primary["provenance_by_seq"],
            integrity_by_seq=primary["integrity_by_seq"],
            observation_count_by_seq=primary["observation_count_by_seq"],
            conflict_details=primary["conflict_details"],
            boots=tuple(active_boots),
            frames_by_boot=frames_by_boot,
            pending_by_boot=pending_by_boot,
            conflicts_by_boot=conflicts_by_boot,
            multi_repeat_by_boot=multi_repeat_by_boot,
            paused_conflicts_by_boot=paused_conflicts_by_boot,
            provenance_by_boot_seq=provenance_by_boot_seq,
            integrity_by_boot_seq=integrity_by_boot_seq,
            observation_count_by_boot_seq=observation_count_by_boot_seq,
            conflict_details_by_boot_seq=conflict_details_by_boot_seq,
            boot_events=tuple(self.boot_events),
            ambiguous_reset_chunks=tuple(self.ambiguous_reset_chunks),
        )


def validate_sequence(frames: dict) -> dict:
    keys = sorted(frames)
    if not keys:
        raise ValueError("没有已认证的稳定记录")
    missing = keys[-1] - keys[0] + 1 - len(keys)
    gaps = []
    for a, b in zip(keys, keys[1:]):
        if b > a + 1:
            gaps.append({"gap_start_seq": a + 1, "gap_end_seq": b - 1, "missing_count": b - a - 1})
    return {
        "first_seq": keys[0],
        "last_seq": keys[-1],
        "frames": len(keys),
        "missing_in_span": missing,
        "sequence_complete": missing == 0,
        "gaps": gaps,
    }
