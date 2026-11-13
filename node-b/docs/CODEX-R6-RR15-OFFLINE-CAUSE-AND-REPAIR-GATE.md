# MPM-B5 | RR15 false-HR causal gate and bounded repair contract (offline only)

Base: `codex/b5-r6-ecg-temp-20261030@e24e9705a31ed9c2237ed38dd6bc843b6ffaa45c`.
Status: `ROOT_CAUSE_HYPOTHESIS / OFFLINE_REPLAY_TOOL_ONLY / FIELD_NO_GO`.

## Established facts
- R6 RR15: 600 diagnostics, 20 unexpected valid HR, 10 anomalous cloud HR values; formal `NOT_PASS/exit=3`. Six short HR-valid bursts (52/64/73/82/38/58/39 bpm).
- RESP at 15 bpm and transport/STOP succeeded. B-side `hr_valid` is already true; cloud is an observer, not the origin.
- `bio_v2.c` heart peak gate: `max(30, 2.5*sqrt(band_power))`; accepted peak width 12..160ms, 3 fresh intervals, all intervals within 20% of median; mains rejection requires fraction > 0.95 AND raw_power > 10000.
- RR-window ECG RMS ~41..58 codes and mains fraction .89..92 overlap valid and invalid HR frames. This supports but **does not prove** intermittent coherent mains/coupled noise. The simulator's exact ECG output and physical CH2 signal remain UNKNOWN.
- ECG60 and TEMP_OBJECT later passed independent engineering reviews (exit 0); this does not rewrite RR15 history or prove a new firmware fix.

## Diagnostic tool delivered
`node-b/tools/b5_rr15_causal_replay.py` checks SHA256 of each private blocks.bin, verifies per-block hashes/offsets and >=2 identical raw copies, feeds exact signed 24-bit CH2/CH1 and original device tick/sequence/flags to unchanged BioV2 C via a newly compiled local host library, compares RR15-negative vs ECG60-positive and records candidate periods, valid-HR episodes, independent 50Hz projections. Full data and output stay outside Git.

Inputs are private EFS and supplied explicit hashes. This is not a field run and not a frozen reviewer. Do not assume an exact device-epoch start equal to T0 from its warmup-only summary.

## Required test gates BEFORE firmware change
1. Compare baseline C replay against archived RR15 sequences and diagnostic epochs. If there are disagreements in counts/time offsets, diagnose replay input mapping first; no threshold tuning.
2. Compare RR15 false bursts to adjacent HR-invalid samples and a genuine ECG60 positive: band-power, 50/100Hz, QRS width/prominence/morphology, candidate timestamps, `hr_fresh_intervals`, relative RESP phase, sample discontinuities, raw CH2 saturation, and simulator settings.
3. Use >=1 independent RR holdout and ECG60/90/120 + noisy ECG positives. Pre-register acceptance before modifying `bio_v2.c`. Disallow thresholds selected solely to eliminate the six observed RR bursts.
4. If real ECG is present on simulator output, classify as physical-source/config ambiguity and propose an isolated physical correction; **do not suppress real HR**.
5. If verified non-QRS interference, implement one minimal, signal-evidence-supported quality gate independent of test profile and return INVALID only for *failed evidence*, not because mode==RR15; preserve real QRS including low amplitude cases. Carry original reason bits and raw evidence, no clamp.
6. Host C compile + deterministic false/true replay, ECG60/90/120 regression, RR15 real negative, long/noisy/phase-shift, wrap/discontinuity, clipping and ABI checks; candidate cannot ship without fail-closed review.

## Stop
No real DLL/SWD/COM, no RESET/B5START, no MCU build or flash, no cloud actions, no changes to frozen criteria/reviewer, no rerun of a consumed RR token, no main or active release branch mutation. This is diagnosis and offline tool delivery; device-level repair remains unproven.
