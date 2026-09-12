# Architecture

BirdNET-PiPy uses a containerized microservices architecture with five Docker containers.

## Container Details

| Container | Port | Technology | Purpose |
|-----------|------|------------|---------|
| **frontend** | 80 | Nginx + Vue.js 3 | Web dashboard, SPA routing, API/stream proxy |
| **api** | 5002 | Flask + Socket.IO | REST API, WebSocket events, database access |
| **model-server** | 5001 | TFLite (V2.4) / ONNX (V3.1) | AI model inference, species detection |
| **main** | - | Python + FFmpeg | Audio recording, analysis orchestration |
| **icecast** | 8888 | Icecast + FFmpeg | Live audio streaming to browsers |

## Container Architecture

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│     frontend     │      │       main       │      │     icecast      │
│       :80        │      │                  │      │      :8888       │
├──────────────────┤      ├──────────────────┤      ├──────────────────┤
│ Nginx + Vue.js 3 │      │   Main Loop      │      │ FFmpeg + Icecast │
│ Serves UI        │      │   Recording      │      │   Livestream     │
│ Reverse proxy    │      │ Analysis Pipeline│      │                  │
└────────┬─────────┘      └────────┬─────────┘      └──────────────────┘
         │                         │
         │          ┌──────────────┴──────────────┐
         │          │                             │
         │          ▼                             ▼
         │   ┌─────────────────┐          ┌─────────────────┐
         │   │      api        │          │  model-server   │
         │   │     :5002       │          │     :5001       │
         │   ├─────────────────┤          ├─────────────────┤
         └──▶│ Flask + SocketIO│          │ TFLite V2.4 /   │
             │ WebSocket events│          │ ONNX V3.1 model │
             └─────────────────┘          └─────────────────┘
```

## Audio Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      RASPBERRY PI HOST                           │
│                                                                  │
│   ┌─────────────┐       ┌─────────────────────────────────┐      │
│   │     USB     │       │   PulseAudio or PipeWire        │      │
│   │ Microphone  │──────▶│   (audio server)                │      │
│   └─────────────┘       └───────────────┬─────────────────┘      │
│                                         │                        │
│                              /run/pulse/native                   │
│                                 (socket)                         │
└─────────────────────────────────┬────────────────────────────────┘
                                  │ bind-mount
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐
        │  main container   │       │ icecast container │
        │                   │       │                   │
        │  Records audio    │       │  Streams audio    │
        │  for analysis     │       │  to browsers      │
        └───────────────────┘       └───────────────────┘
```

- **RPi OS Desktop**: Uses PipeWire with `pipewire-pulse` compatibility layer
- **RPi OS Lite**: Installs PulseAudio in system-wide mode

## Data Flow

```
 ┌─────────┐     WAV     ┌─────────────┐  detections  ┌───────────┐
 │  main   │────────────▶│ model-      │─────────────▶│   main    │
 │ recorder│   chunks    │ server      │    JSON      │ pipeline  │
 └─────────┘             └─────────────┘              └─────┬─────┘
                                                            │
                         ┌──────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────────────────┐
          │  For each detection:                     │
          │  1. Extract audio clip                   │
          │  2. Generate spectrogram                 │
          │  3. Save to SQLite database              │
          │  4. Broadcast via WebSocket              │
          └──────────────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────────────────┐
          │            Vue.js Dashboard              │
          │                                          │
          │  - Real-time detection feed (WebSocket)  │
          │  - Historical data (REST API)            │
          │  - Audio playback & spectrograms         │
          └──────────────────────────────────────────┘
```

## Settings lifecycle

The API is the only settings writer. Each write validates and merges a partial
update under one transaction lock, then atomically replaces the private JSON
file. GET and successful writes return a content ETag; the browser serializes
its writes and sends `If-Match` to reject changes based on an obsolete revision.
Manual Save sends changed fields. Source and species dialogs save only their
own fields, leaving unrelated form drafts untouched.

Runtime readers validate a stable file snapshot and keep the last valid snapshot
if the file becomes unreadable. A settings read never persists a migration.
An unreadable saved file blocks API writes and the Settings form instead of
silently replacing the station's configuration with defaults.

| Change | Takes effect |
|--------|--------------|
| Detection, overlap, location, species lists | Next analysis request |
| Playback normalization and spectrogram preferences | Next generated clip/image |
| Notifications and BirdWeather | Next event; disabled/replaced BirdWeather workers discard queued uploads |
| Storage policy | Next cleanup cycle |
| Display, update channel, access | Next request; browser preferences refresh on entering/focusing Settings |
| Source connection or enabled flag | Only that source's recorder and stream reconnect |
| Recording length | Recorders reconnect; queued WAVs keep their actual duration |
| Source label | No audio reconnection |
| Quiet hours | Next recording-loop tick; live streaming continues |
| Model type | Explicit service restart |

The main loop owns recorders by source ID. The streaming container runs the
standard-library Python `stream_supervisor.py`, which owns one FFmpeg publisher
per source. Both compare the connection configuration and retain unchanged
processes. A replacement starts only after the previous process stops. Failed
stream connections retry independently with bounded backoff. Access revocation
reconnects publishers so established HTTP listeners must pass nginx's access
check again; the API also evicts anonymous WebSocket listeners.

A save acknowledges persistence. `/api/settings/status` separately compares the
saved model/source configuration with recorder heartbeats, model service status,
and the streaming supervisor's private `data/streaming_status.json` heartbeat.
The API shares the same snapshot through the `settings_status` socket event
with owner sockets that asked for it (`watch_settings_status`, sent by the
Settings page while mounted and again on every reconnection). One monitor per
API worker samples audio once per second and refreshes model health
independently every five seconds while anyone is watching, with at most one
model request in flight; pages that do not show settings status cost nothing.
Model results expire after fifteen seconds, so ongoing audio updates cannot keep
old model health alive. It sends changes, a fresh snapshot for each new watcher,
and a five-second heartbeat. Settings consumes these pushes instead of polling
the REST endpoint; leaving the page, disconnects or fifteen seconds without a
heartbeat clear the browser's status. The REST endpoint remains available for
diagnostics. Each snapshot carries per-source recording and streaming state,
the recorder's error text for a failed source, and the pause in force, all
from one acknowledged revision.
The recorder loop acknowledges settings per source (a change to one source
never invalidates another's state) and broadcasts per-source state, error,
pause and acknowledgement changes on its next two-second pass, retaining a
five-second heartbeat for unchanged status. Failed deliveries retry on the
next pass.
Recorders confirm activity after capturing audio; streams confirm it after
FFmpeg reports advancing output. Missing or old heartbeats mean unknown status,
not success. Pending model changes remain visible across refreshes and repeated
saves. The loaded model continues serving while awaiting restart, retaining its
own location-filter threshold; queued audio is resampled to its sample rate.

The restart boundary for model changes keeps model allocation, sample-rate
selection and process recovery simple on memory-constrained devices. A general
settings event bus or dynamic model replacement is not required for source reload.

Home Assistant deployments need the `ha` snapshot re-synced and their add-on
packaging updated to include/start `stream_supervisor.py` with Python 3, the shared
data directory and the existing Icecast credentials/environment. Older wrappers
that still own static FFmpeg processes cannot provide live source reload; their
stream status remains unavailable until the packaging is updated.

Streaming supervisor tests run independently with:
`python3 -m unittest discover -s deployment/audio/tests -v`.
