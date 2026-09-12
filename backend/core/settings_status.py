"""Compare saved resource configuration with fresh runtime acknowledgements.

Hot scalar settings are read at their next request/clip/cycle. They have no
separate activation acknowledgement and must not be labelled 'active' on save.
"""
import json
import time

from config.settings import BASE_DIR
from core.settings_store import settings_etag
from core.source_config import recorder_source_revision, source_revision

STREAMING_STATUS_PATH = f'{BASE_DIR}/data/streaming_status.json'
STATUS_MAX_AGE = 20


def read_streaming_status():
    try:
        with open(STREAMING_STATUS_PATH) as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def fresh(status, now):
    updated = status.get('updated_at')
    return type(updated) in (int, float) and 0 <= now - updated <= STATUS_MAX_AGE


def build_settings_status(settings, recorder, streaming, model_service, *, now=None):
    now = time.time() if now is None else now
    recorder_fresh, stream_fresh = fresh(recorder, now), fresh(streaming, now)
    active_model = (model_service.get('model') or {}).get('type')
    requested_model = settings['model']['type']
    recorder_model = recorder.get('model_type') if recorder_fresh else None
    restart_required = any(model and model != requested_model for model in (active_model, recorder_model))
    model_state = ('restart_required' if restart_required else
                   'active' if active_model == recorder_model == requested_model else 'unknown')
    audio = settings['audio']
    desired_ids = {s['id'] for s in audio['sources'] if s.get('enabled', True)}
    acknowledged = (recorder.get('source_settings_revisions') or {}) if recorder_fresh else {}
    pause = recorder.get('pause') if recorder_fresh else None
    every_source_current = recorder_fresh
    sources = {}
    for source in audio['sources']:
        sid = source['id']
        recording = recorder.get('sources', {}).get(sid, {})
        stream = streaming.get('sources', {}).get(sid, {})
        # Each source is acknowledged on its own: a change to another source
        # must not invalidate this source's pause, disabled state or reload error.
        source_current = acknowledged.get(sid) == recorder_source_revision(source, settings)
        every_source_current = every_source_current and source_current
        if not source.get('enabled', True):
            recording_state = 'disabled' if source_current and not recording else 'pending' if recorder_fresh else 'unknown'
            stream_state = 'disabled' if stream_fresh and not stream else 'pending' if stream_fresh else 'unknown'
        else:
            recording_state = 'unknown'
            if recorder_fresh:
                recording_state = 'pending'
                if source_current and pause and not recording.get('config_revision'):
                    recording_state = 'paused'
                elif recording.get('config_revision') == source_revision(source, audio['recording_length']):
                    recording_state = recording.get('application_state', 'connecting')
            stream_state = 'unknown'
            if stream_fresh:
                stream_state = (stream.get('state', 'connecting') if
                                stream.get('config_revision') == source_revision(source) else 'pending')
        if source_current and recording.get('reload_error'):
            recording_state = 'failed'
        sources[sid] = {'recording': recording_state, 'streaming': stream_state}
        if recording_state == 'failed':
            sources[sid]['error'] = recording.get('reload_error') or recording.get('last_error_message') or ''
    # Removed sources keep the whole recorder pending until their process stops.
    recording_current = every_source_current and not (set(recorder.get('sources', {})) - desired_ids)
    return {
        'revision': settings_etag(settings),
        'model': {'requested': requested_model, 'active': active_model, 'recorder': recorder_model,
                  'state': model_state, 'restart_required': bool(restart_required)},
        'sources': sources,
        'pause': pause,
        'recording': 'current' if recording_current else 'pending' if recorder_fresh else 'unknown',
        'streaming': ('pending' if set(streaming.get('sources', {})) - desired_ids else 'current') if stream_fresh else 'unknown',
        'streaming_error': streaming.get('error') if stream_fresh else 'Streaming status unavailable',
        'model_service': model_service,
    }
