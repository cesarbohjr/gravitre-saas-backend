"""Offline acoustic diagnostics for bounded synthetic PCM16 fixtures.

No runtime imports, model downloads or provider calls. Pitch and pause statistics
are proxies, not speaker identity, emotional classification or human MOS.
Thresholds are conservative integrity screens, not calibrated release budgets.
"""
import math
import statistics
import struct
import wave
import io
import re

RATE = 16000
MAX_SECONDS = 30
MIN_SECONDS = 0.25
FRAME = RATE // 50  # 20 ms
PITCH_WINDOW = RATE // 25
SILENCE_RMS = 0.003
MAX_CLIP_FRACTION = 0.001
MIN_ACTIVE_FRACTION = 0.10


def pcm_from_wav(data):
    with wave.open(io.BytesIO(data), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, RATE):
            raise ValueError("expected mono PCM16 at 16 kHz")
        count = wav.getnframes()
        if not RATE * MIN_SECONDS <= count <= RATE * MAX_SECONDS:
            raise ValueError("audio duration outside fixture bounds")
        pcm = wav.readframes(count)
        if len(pcm) != count * 2:
            raise ValueError("truncated PCM")
        return pcm


def pitch_hz(frame):
    """Approximate voiced F0 using normalized autocorrelation, with octave guard."""
    mean = statistics.fmean(frame)
    x = [v - mean for v in frame]
    if sum(v*v for v in x) / len(x) < SILENCE_RMS ** 2:
        return None
    lo, hi = RATE // 400, RATE // 65
    scores = []
    for lag in range(lo - 1, hi + 2):
        # Downsample the correlation sum only, not the lag grid.
        a, b = x[:-lag:2], x[lag::2]
        denom = math.sqrt(sum(v*v for v in a) * sum(v*v for v in b))
        scores.append(sum(u*v for u,v in zip(a,b)) / denom if denom else 0.0)
    peaks = [(scores[i], lo - 1 + i) for i in range(1, len(scores)-1)
             if scores[i] >= scores[i-1] and scores[i] > scores[i+1]]
    if not peaks:
        return None
    best = max(s for s,_ in peaks)
    if best < 0.65:
        return None
    lag = min(l for s,l in peaks if s >= max(0.65, best * 0.9))
    return RATE / lag


def analyze_pcm(pcm):
    if len(pcm) % 2 or not RATE * MIN_SECONDS * 2 <= len(pcm) <= RATE * MAX_SECONDS * 2:
        raise ValueError("invalid or out-of-bounds PCM")
    ints = [v[0] for v in struct.iter_unpack("<h", pcm)]
    x = [v / 32768 for v in ints]
    levels = [math.sqrt(statistics.fmean(v*v for v in x[i:i+FRAME]))
              for i in range(0, len(x), FRAME)]
    active = [i for i, level in enumerate(levels) if level >= SILENCE_RMS]
    pauses = []
    if active:
        pauses = [(b-a-1)*20 for a,b in zip(active, active[1:]) if b-a > 1]
    # Sample at most 100 windows deterministically to bound offline CPU.
    starts = list(range(0, len(x)-PITCH_WINDOW+1, RATE//10))
    stride = max(1, math.ceil(len(starts)/100))
    pitches = [p for i in starts[::stride] if (p := pitch_hz(x[i:i+PITCH_WINDOW])) is not None]
    median = statistics.median(pitches) if pitches else None
    rms = math.sqrt(statistics.fmean(v*v for v in x))
    return {
        "duration_ms": len(x)*1000/RATE,
        "rms": rms,
        "peak": max(abs(v) for v in x),
        "clip_fraction": sum(abs(v)>=32760 for v in ints)/len(x),
        "active_fraction": len(active)/len(levels),
        "internal_pause_count": len(pauses),
        "max_internal_pause_ms": max(pauses, default=0),
        "pitch_median_hz": median,
        "pitch_iqr_hz": (statistics.quantiles(pitches,n=4)[2]-statistics.quantiles(pitches,n=4)[0]
                         if len(pitches)>=4 else None),
        "voiced_windows": len(pitches),
    }


def integrity_failures(metrics):
    limits = {"duration_ms": (250,30000), "rms": (SILENCE_RMS,1),
              "peak": (SILENCE_RMS,1), "clip_fraction": (0,MAX_CLIP_FRACTION),
              "active_fraction": (MIN_ACTIVE_FRACTION,1)}
    failures = []
    for name,(lo,hi) in limits.items():
        value = metrics.get(name)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            failures.append("missing_or_invalid:" + name)
        elif not lo <= value <= hi:
            failures.append("out_of_bounds:" + name)
    return failures


def compare(baseline, candidate):
    """Paired measurements, deliberately no calibrated similarity score."""
    def delta(name):
        a,b = baseline.get(name),candidate.get(name)
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (a,b)):
            return None
        return b-a
    return {"pitch_delta_hz": delta("pitch_median_hz"),
            "pitch_iqr_delta_hz": delta("pitch_iqr_hz"),
            "duration_delta_ms": delta("duration_ms"),
            "pause_delta_ms": delta("max_internal_pause_ms"),
            "rms_delta": delta("rms"),
            "baseline_integrity_failures": integrity_failures(baseline),
            "candidate_integrity_failures": integrity_failures(candidate),
            "identity_similarity": "NOT ESTABLISHED",
            "emotional_quality": "NOT ESTABLISHED"}


def word_error_rate(reference, transcript):
    def words(text):
        return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())
    a,b = words(reference),words(transcript)
    if not a or len(a)>200 or len(b)>400:
        raise ValueError("invalid transcript fixture bounds")
    prev = list(range(len(b)+1))
    for i,u in enumerate(a,1):
        curr = [i]
        for j,v in enumerate(b,1):
            curr.append(min(curr[-1]+1,prev[j]+1,prev[j-1]+(u!=v)))
        prev = curr
    return prev[-1]/len(a)


REQUIRED_GATES = ("flash_http", "v3_dialogue", "acoustic_integrity",
                  "paired_quality", "intelligibility", "prosody_review",
                  "live_streaming", "interruption", "playback_continuity",
                  "physical_mobile", "physical_desktop", "preference_migration")


def certification_blockers(evidence):
    """Unknown, skipped or malformed evidence never qualifies a candidate.

    This is a gate-state reducer, not an evidence authenticator. The caller
    must bind evidence to candidate ID, model, fixture and exact source SHA.
    """
    return [name for name in REQUIRED_GATES if evidence.get(name) != "PASS"]
