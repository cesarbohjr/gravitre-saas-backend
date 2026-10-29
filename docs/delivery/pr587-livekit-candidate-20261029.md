# Isolated LiveKit candidate checkpoint — 2026-10-29

Status: PARTIAL. No recorded-speech comparison or production certification.

Implemented `backend/app/services/pipecat_voice/livekit_candidate.py`: a native
LiveKit RTC audio/data adapter feeding the unchanged Gravitre Pipecat pipeline.
It uses Deepgram, ElevenLabs, the cognitive bridge, and the existing authorization
path when configured with a complete isolated backend environment. This is a
transport candidate, **not an independent LiveKit Agents engine**. SDK contracts
do not prove the complete pipeline can run; that integration remains NOT RUN.

The adapter pins input to one participant, bounds the input queue, prioritizes
interrupt controls, clears queued output on interruption/disconnection, preserves
reply identifiers and playback reports, and requires an explicit isolated entry
point. It accepts neither tenant identity nor text/tool/approval commands from
room data. The trusted test controller must authenticate the smoke tenant and
issue short-lived room-scoped tokens. Do not reuse production rooms or tenants.

## Execution evidence

Local Python 3.12, LiveKit RTC SDK 1.2.0:

```
python -m pytest -q --confcutdir=backend/tests/unit backend/tests/unit/test_livekit_candidate.py
```

Seven SDK/boundary tests cover native PCM handling, participant/control filtering,
interrupt priority under full queues, disconnect wakeup, reply/playback metadata,
invalid PCM, and required isolation. These use real SDK audio objects with room
test doubles, **not actual connected rooms or provider inference**.

`pip-audit --no-deps --disable-pip` on `livekit==1.2.0`: no known vulnerabilities
reported. This is a direct-package check, not a full transitive dependency audit.

Attempted local LiveKit server 1.13.11 startup on loopback, with explicit node IP:

```
livekit-server --dev --bind 127.0.0.1 --node-ip 127.0.0.1
failed to get create network: route ip+net: netlinkrib: operation not permitted
```

The binary cannot initialize its RTC networking in this execution host. No
connected-room result is claimed. Railway inventory exposed only the existing
production environment; no isolated LiveKit service/configuration was present.
The connected Railway API exposes provider variable names but redacts their
values. Existing production provider variables were not changed or recreated.

## Running on a suitable isolated host

Install normal backend dependencies plus `backend/requirements-voice-comparison.txt`.
Configure a dedicated reachable LiveKit server and provide `LIVEKIT_URL`,
`LIVEKIT_AGENT_TOKEN`, `LIVEKIT_REPLAY_IDENTITY`, `GRAVITRE_TEST_ORG_ID`,
`GRAVITRE_TEST_USER_ID`, and `GRAVITRE_TEST_CONVERSATION_ID` through the environment.
Backend settings must reference an authorized isolated smoke tenant and have
working inference/STT/TTS configuration. Never put tokens in CLI arguments/logs.

From `backend`, set `GRAVITRE_VOICE_ISOLATED=1` and run:

```
python -m app.services.pipecat_voice.livekit_candidate
```

The pinned peer publishes 16 kHz mono speech. The candidate publishes 24 kHz
mono response audio. Controls use the `gravitre-control` data topic; events use
`gravitre-events`. On participant loss the pipeline ends; a fresh authenticated
session is required to reconnect. This candidate is not yet a WAV-in/WAV-out
command compatible with `isolated_audio_replay.py`; the paired capture peer and
end-to-end runner integration remain required.

## Open gate

Actual paired speech, response latency, interruption latency, reconnect recovery,
cancelled-write audit evidence, provider cost, human listening and audio quality:
**NOT RUN**. No engine selection, merge, deployment, or runtime-default change.
New isolated SDK CI must pass on the resulting exact commit. Existing PR checks
are not substituted for these missing trials.
