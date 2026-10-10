# Voice scenario bench: final-all-flags-duck

Runs per scenario: 20 · seed base: 1000 · git: 010b9784 · wall time: 108.5 s · settings overrides: {'voice_interrupt_intents_v1': 'true', 'voice_request_revisions_v1': 'true', 'voice_playback_grounded_history_v1': 'true', 'voice_tts_idle_refresh_v1': 'true', 'voice_incomplete_turn_hold_v1': 'true', 'voice_answer_first_v1': 'true', 'voice_overlap_duck_v1': 'true'}

Times are milliseconds, shown as P50 / P95 (n = runs where the event happened). "played" is the modelled browser speaker; "sent" is arrival at the client socket. First-audio and completion are measured from the user's acoustic end of speech of the measured request.

## Latency

| Scenario | first audio (any) | first filler/progress | first answer (played) | first answer (sent) | talk time (filler/progress part) | task completion |
|---|---|---|---|---|---|---|
| S1 long pause / incomplete thought | 1374 / 1509 (n=20) | 1374 / 1509 (n=20) | 3282 / 4603 (n=20) | 3122 / 4443 (n=20) | 13760 / 15040 (n=20) (1920 / 3200 (n=20)) | 3458 / 3697 (n=20) |
| S1b long pause, STT commits early | 1433 / 1554 (n=20) | 1433 / 1554 (n=20) | 4564 / 4754 (n=20) | 4404 / 4594 (n=20) | 15040 / 15056 (n=20) (3200 / 3216 (n=20)) | 3685 / 4000 (n=20) |
| S2 backchannel during playback | 1413 / 1512 (n=20) | 1413 / 1512 (n=20) | 3284 / 4396 (n=20) | 3124 / 4236 (n=20) | 13760 / 14736 (n=20) (1920 / 2896 (n=20)) | 3372 / 3641 (n=20) |
| S2b backchannel "Yeah." (control) | 1386 / 1524 (n=20) | 1386 / 1524 (n=20) | 3249 / 4605 (n=20) | 3089 / 4445 (n=20) | 13760 / 15040 (n=20) (1920 / 3200 (n=20)) | 3434 / 3687 (n=20) |
| S3 correction before speech starts | 1347 / 1470 (n=20) | 1347 / 1470 (n=20) | 3245 / 3426 (n=20) | 3085 / 3252 (n=20) | 13760 / 13808 (n=20) (1920 / 1968 (n=20)) | 3335 / 3576 (n=20) |
| S4 correction after speech starts (barge-in) | 1935 / 2026 (n=20) | 1935 / 2026 (n=20) | 4792 / 5245 (n=20) | 4632 / 5085 (n=20) | 8000 / 8336 (n=20) (2880 / 3216 (n=20)) | 3334 / 3614 (n=20) |
| S5 repeated interruptions then resumed request | 1379 / 1497 (n=20) | 1379 / 1497 (n=20) | 3168 / 4226 (n=20) | 2978 / 4066 (n=20) | 9600 / 11216 (n=20) (1280 / 2896 (n=20)) | 2814 / 3084 (n=20) |
| S6 late TTS audio after cancellation | 1947 / 2024 (n=20) | 1947 / 2024 (n=20) | 4836 / 5163 (n=20) | 4676 / 5003 (n=20) | 8000 / 8320 (n=20) (2880 / 3200 (n=20)) | 3390 / 3636 (n=20) |
| S7 slow tool (4 s) | 1373 / 1527 (n=20) | 1373 / 1527 (n=20) | 6115 / 6609 (n=20) | 5995 / 6489 (n=20) | 7360 / 7680 (n=20) (3200 / 3520 (n=20)) | 5965 / 6459 (n=20) |
| S7b failed tool | 1345 / 1526 (n=20) | 1345 / 1526 (n=20) | 4524 / 4893 (n=20) | 4364 / 4733 (n=20) | 8000 / 8320 (n=20) (3200 / 3520 (n=20)) | 3135 / 3557 (n=20) |
| S8 approval "yes... wait" | 1714 / 1998 (n=20) | – | 1714 / 1998 (n=20) | 1594 / 1878 (n=20) | 1600 / 1600 (n=20) (0 / 0 (n=20)) | 1342 / 1563 (n=20) |
| S9 complex reasoning turn (deep tier) | 1433 / 1565 (n=20) | 1433 / 1565 (n=20) | 7633 / 8170 (n=20) | 7453 / 8050 (n=20) | 16640 / 16960 (n=20) (4800 / 5120 (n=20)) | 7948 / 8545 (n=20) |
| S10 "stop talking, keep working" | 1379 / 1480 (n=20) | 1379 / 1480 (n=20) | 7920 / 9229 (n=20) | 7800 / 9109 (n=20) | 7360 / 7680 (n=20) (3200 / 3520 (n=20)) | 7589 / 8850 (n=20) |
| S11 "cancel it" during a running task | 1336 / 1502 (n=20) | 1336 / 1502 (n=20) | 4700 / 5219 (n=20) | 4580 / 5099 (n=20) | 5120 / 5440 (n=20) (2240 / 2560 (n=20)) | 4325 / 4906 (n=20) |
| S12 reconnect mid-reply (socket drop) | 1345 / 1481 (n=20) | 1345 / 1481 (n=20) | 3263 / 4599 (n=20) | 3103 / 4439 (n=20) | 6160 / 7440 (n=20) (1920 / 3200 (n=20)) | 9747 / 11172 (n=20) |

## Interruption, correctness and speculation

| Scenario | barge-in → last old frame sent | barge-in → silence (played) | late old frames recv / played | mis-stamped frames | premature response | premature actions | history = heard | brain s after interrupt (orphan runs) | spec started / adopted / wasted s | outcome |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 40 / 20 / 19.391 | answered 11, clarified_then_answered 9 |
| S1b | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 40 / 20 / 5.186 | clarified_then_answered 20 |
| S2 | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 20 / 20 / 0.0 | kept_speaking 20 |
| S2b | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 20 / 20 / 0.0 | kept_speaking 20 |
| S3 | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 40 / 20 / 3.221 | answered_last_month 20 |
| S4 | 1633 / 1792 (n=20) | 1638 / 1809 (n=20) | 0 / 0 | 0 | – | 0 | 20/20 | 0.0 (0) | 40 / 20 / 4.971 | corrected 20 |
| S5 | 746 / 841 (n=20) | 757 / 845 (n=20) | 0 / 0 | 0 | – | 0 | 20/20 | 0.0 (0) | 40 / 40 / 0.0 | resumed_answered+interrupts=1 20 |
| S6 | 1610 / 1788 (n=20) | 1624 / 1806 (n=20) | 0 / 0 | 0 | – | 0 | 19/20 | 0.0 (0) | 40 / 20 / 4.696 | late_audio_contained 20 |
| S7 | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 20 / 20 / 0.0 | answered 20 |
| S7b | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 20 / 20 / 0.0 | failure_in_answer_only 20 |
| S8 | – | – | – | 0 | 0/20 | 0 | 0/20 | 0.0 (0) | 20 / 20 / 0.0 | no_send_attempted 20 |
| S9 | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 20 / 20 / 0.0 | answer+filler+progress 20 |
| S10 | 1212 / 1216 (n=20) | 1412 / 1416 (n=20) | 0 / 0 | 0 | 0/20 | 0 | 20/20 | 63.213 (20) | 20 / 20 / 0.0 | task_completed+report_spoken 20 |
| S11 | 570 / 578 (n=20) | 770 / 778 (n=20) | 0 / 0 | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 20 / 20 / 0.0 | task_cancelled 20 |
| S12 | – | – | – | 0 | 0/20 | 0 | 20/20 | 0.0 (0) | 40 / 40 / 0.0 | brain_saw_partial_reply_marked 20 |

## Overlap ducking (voice_overlap_duck_v1)

"ducked (played)" is the time from the overlap's start until the old reply is no longer heard at full level: the duck ramp has finished, or its audio has stopped, whichever comes first. Ducked audio still counts as heard.

| Scenario | barge-in → ducked (played) | barge-in → silence (played) | ducked for | duck restored | outcome |
|---|---|---|---|---|---|
| S2 | 197 / 230 (n=20) | – | 595 / 709 (n=20) | 20/20 | kept_speaking 20 |
| S2b | 200 / 225 (n=20) | – | 580 / 691 (n=20) | 20/20 | kept_speaking 20 |
| S4 | 211 / 239 (n=20) | 1638 / 1809 (n=20) | 1506 / 1640 (n=20) | 0/20 | corrected 20 |
| S5 | 215 / 239 (n=20) | 757 / 845 (n=20) | 598 / 688 (n=20) | 0/20 | resumed_answered+interrupts=1 20 |
| S6 | 230 / 242 (n=20) | 1624 / 1806 (n=20) | 1448 / 1690 (n=20) | 0/20 | late_audio_contained 20 |
| S10 | 205 / 232 (n=20) | 1412 / 1416 (n=20) | 1559 / 1654 (n=20) | 0/20 | task_completed+report_spoken 20 |
| S11 | 213 / 245 (n=20) | 770 / 778 (n=20) | 884 / 975 (n=20) | 0/20 | task_cancelled 20 |

## Scenario conditions

- **S1 long pause / incomplete thought**: User: "I want to check... [1.2 s pause] ...last month's traffic". Flux emits EagerEndOfTurn in the pause and TurnResumed when speech resumes (the turn is not committed). Expected: No bot audio during the pause; one answer about last month. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S1b long pause, STT commits early**: Same words, but Flux commits EndOfTurn on "I want to check" during the 1.2 s pause; the rest arrives as a new turn. Expected: Ideally no audible reply to the fragment; the full request answered once. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S2 backchannel during playback**: User asks for traffic; 1.5 s into the spoken answer says "Mm-hmm." (0.4 s). Expected: Bot keeps speaking; no new turn; history = full answer. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S2b backchannel "Yeah." (control)**: As S2 with "Yeah.", a word the utterance gate does not drop. Expected: Bot keeps speaking. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S3 correction before speech starts**: User: "show me traffic for last week, no, last month" with a 0.35 s hesitation after "week". Expected: One answer about last month; nothing about last week is spoken. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S4 correction after speech starts (barge-in)**: User asks for last week's traffic; 1.2 s into the answer barges in: "use last quarter instead". Expected: Old answer stops quickly; new answer about last quarter; history holds only what was heard. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S5 repeated interruptions then resumed request**: Pipeline summary request; user cuts in with "wait" 1 s into the answer, then "actually hold on" while the bot answers that, then "okay go on, give me the pipeline summary". Expected: Each cut-in silences the bot; the final request gets the summary once. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S6 late TTS audio after cancellation**: As S4, but the TTS provider keeps emitting the cancelled context's audio for 300 ms after close. Expected: No frame of the cancelled reply is played after the interruption. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.3, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S7 slow tool (4 s)**: "pull the pipeline report for this quarter": one CRM tool call taking 4 s. Expected: Progress narration covers the wait; answer after the tool. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S7b failed tool**: "what was our website traffic last month": the analytics tool fails after 1.5 s. Expected: Failure narrated honestly; no invented numbers. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S8 approval "yes... wait"**: Bot drafts an email and asks to send; user says "yes", pauses ~0.5 s, says "wait". Flux may commit "yes" on the pause. Expected: No email is sent (the final intent is "wait"). Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S9 complex reasoning turn (deep tier)**: Multi-part analysis request; brain thinks 2.5 s, runs two tools (1.5 s, 1.0 s), thinks 1.5 s, then answers. Expected: Early acknowledgement and progress narration; answer when ready. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S10 "stop talking, keep working"**: During a 6 s CRM task, while progress narration plays, the user says "stop talking, keep working". Expected: Ideal: narration stops, the task keeps running and its result is delivered. (No dedicated path in current code.) Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S11 "cancel it" during a running task**: An approved CRM batch write is running (user: "yes, go ahead and move them all"; the provider call is made 4 s into a 5 s tool call). 0.5 s into the progress narration the user says "cancel it". Expected: The task stops and the write is not committed. (Cancellation rides on barge-in + stop marker.) Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.
- **S12 reconnect mid-reply (socket drop)**: 1.5 s into the spoken traffic answer the socket drops; 1 s later a new socket opens on the same conversation and the user asks what was said last. Expected: Durable history (and the brain's view of it after reconnect) holds only what was heard. Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.

## What the harness models, and what it does not

- Real: every Pipecat processor between the socket and the providers, exactly as build_pipecat_voice_task wires it (utterance gate, transcript relay, speculative prefetch/generation, Flux turn strategies incl. backchannel grace window, Cognitive LLM bridge with deep ack and tool narration, interrupt reporter with stop marker and played-audio reconciliation, Pipecat TTS audio contexts and word timestamps, websocket output pacing, spoken-text tap, durable persistence and the barge-in write gate).
- Scripted STT follows Pipecat 1.12 Deepgram Flux frame semantics: StartOfTurn, EagerEndOfTurn/TurnResumed, EndOfTurn with finalized transcript. Flux 1.12 pushes no interim transcripts, so none are sent (as in production). Flux's own end-of-turn decision is a fixed, jittered delay after speech ends, not a model of its confidence.
- Fake TTS is shaped like the ElevenLabs websocket service (one context per reply, first-byte delay, faster-than-real-time streaming, flush/close). Audio is a constant tone whose sample value encodes the segment, so labels survive re-chunking. Provider-side late frames are modelled; ElevenLabs alignment quirks are not.
- Brain is scripted (first-token delay, streamed tokens, tool calls, failures, governed writes checked with the real raise_if_barge_in_blocks_invoke). It does not model the real CognitiveTurnKernel, model routing or tool selection; the plans are fixed per scenario.
- Browser model reproduces use-voice-duplex-session.ts drop rules (reply_id <= interrupted id, flush on speech.interrupted) and the voice-pcm-jitter.ts lead (120 ms initial, +60 ms per mid-reply underrun, max 320 ms). It does not model the client-side bargeIn() path (the server does not relay interim transcripts), the HTTP fallback watchdog, or AudioContext scheduling jitter.
- NOT modelled: acoustics, microphone echo and echo cancellation, real Deepgram/ElevenLabs/model latency distributions, network latency/jitter/loss (network_s=0), CPU load (virtual time makes processing free), multi-worker Redis stop markers (in-process fallback), and the read-only prefetch services (counted, not run).
- Virtual clock: asyncio timers and time.time/monotonic/perf_counter are virtual; worker threads take zero virtual time. Results are deterministic for a given seed and code version.
