---
name: webrtc-media
description: Browser call audio — microphone capture, noise suppression, echo, choppy or silent audio, dropouts, TURN/ICE reachability, WebRTC stats and recordings for softphones and voice pages.
---

# WebRTC media

Audio complaints are diagnosed per side before anything changes. The project's own media document
(softphone or call architecture) outranks this skill; a call in production is never placed by an agent
when the project forbids it: reproduce on its isolated stack.

## Triage: which side, from what evidence

1. **Locate the loss.** Per call, compare the recording's channels (level, silences, gaps) with the
   browser's own stats. Agent voice missing while the remote party is clean points at the agent's
   capture or CPU; both sides missing points at the network or the media server.
2. **Control.** The same agent's other calls, another agent at the same time, the same headset on
   another softphone. A complaint that follows the person is device or PC; one that follows the time is
   network or server.
3. **Evidence per conclusion**: measurement (stats, recording levels, CPU), log, recording, the user's
   own test call, or a guess said as one. One bad call is an anecdote; count.

## What to read

- `chrome://webrtc-internals` (or a `getStats()` dump): candidate pair type (`host`/`srflx`/`relay`)
  and its `currentRoundTripTime`; inbound `packetsLost`, `jitter`, `concealedSamples`; outbound
  `bytesSent` advancing; `audioLevel`/`totalAudioEnergy` of the media source.
- Recordings: per channel speech level, silent share and longest silence (a silence on one channel
  while the other talks is dropped audio on that side).
- App diagnostics stored per call id, without raw audio, device labels, SDP, ICE addresses or call ids.

## Capture rules

- One base microphone stream per page owner; clone its track per call. Some stacks (SIP.js) stop
  sender tracks when a session closes, so a session never gets the base track itself.
- Chrome keeps one processing setup per device: capturing it again with different echo-cancellation
  or noise-suppression constraints inherits or loses processing. Stop the other capture's tracks first.
- Swap tracks with `RTCRtpSender.replaceTrack` (no renegotiation) and keep the mute state. A processed
  track has no device id and never ends on unplug: keep the mapping to its capture track for device and
  liveness checks.

## Noise suppression

- Off (level 0) is exactly the ordinary browser capture. A level change applies from the next call;
  never swap processing into a healthy live call.
- Choose the model by cost on the weakest PCs, not only by quality: measure CPU per core, added latency
  and missed audio deadlines under a starved core. Average load misses slow frames that drop 0.1-0.3 s
  of voice; detect render loss directly (audio clock against wall time).
- Any processor failure, overload or render loss falls back to the ordinary microphone with the
  browser's noise suppression via `replaceTrack`, then disables the processor for that page.
- Judge quality at the call's real bandwidth (8 kHz for PSTN G.711) with a listening A/B, not only an
  objective score at 48 kHz. AudioWorklet needs HTTPS or localhost.
- Keep a warm processing chain for auto-answer and suspend its AudioContext while idle.

## Health semantics

Keep four axes apart: transport (only peer-connection state sets disconnected/failed), inbound RTP
flow, microphone capture/sender, and playback. A remote track `mute` or an RTP stall is degraded, not
disconnected. A silent microphone is several consecutive samples with bytes advancing and no capture
energy, excluding intentional mute.

## Network and server

- Zero packets both ways: read the ICE candidates first. A media server that advertises only its
  internal address cannot reach a browser that came in through the public hostname; a TURN server can
  stop listening on the expected address after a reboot. Prove TURN with a real relay allocation and
  packets, not with its configuration.
- Choose the route by the hostname the page was opened on (public name: relay-only TURN over TLS on
  443; internal name: all candidates), so one internal agent on the public name keeps working.
- Bound ICE gathering (SIP.js waits 5000 ms by default) while keeping every STUN/TURN server and
  `iceTransportPolicy: "all"`; verify relay calls still connect.
- Before blaming a recent network change, compare loss on relay and direct calls; equal loss means
  the network is not the cause.
- Loss across every agent at once points at the server: check its CPU and per-call resources started
  against stopped (mixers, rooms, tasks). Capture that evidence before any restart; a restart erases it.
- A server that swaps the sender mid-call (consult, conference, transfer) must continue the RTP
  sequence numbering, or the browser discards the new stream as old packets: silent consults.

## Pitfalls seen in production

- Chrome already enables echo cancellation, noise suppression and auto-gain by default; requesting them
  explicitly changes nothing. Check `track.getSettings()` and measure before and after.
- A self-listening test page with echo cancellation on cancels the tester's own voice; open its
  microphone without it.
- No browser filter removes other people's speech, and loud music or room sound near voice level
  survives the built-in filter: the lever is a close-talk headset microphone with auto-gain off.
- A device named like "High Definition Audio Device" is usually the PC's built-in sound card, not the
  headset; select the headset by name.
- Whole seconds of digital zero in the agent channel with no packet gaps were produced on the PC before
  encoding (device, driver, processing), not by the network.
- Always-on processing in a page held open all shift costs CPU while idle: pause it between calls.
- Unplugging a headset never hangs up; an unexpected call end has a sender in the logs.
- Agents run the old bundle until they reload the page: a frontend fix reaches the floor only after
  a refresh. Levels that look normal still need a listen (clipping at call start).

## Verify

At least 20 production-like calls including the relay path, p95 answer latency, per-channel recording
levels before and after, and a listening check. A regression returns everyone to plain capture first,
then gets diagnosed.
