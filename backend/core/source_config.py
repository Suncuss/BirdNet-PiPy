"""Stable identities for resource configuration; labels never reconnect audio."""
import hashlib
import json


def source_revision(source, recording_length=None):
    # Same wire contract as deployment/audio/scripts/stream_supervisor.py.
    values = [source.get('type'),
              source.get('url', '') if source.get('type') == 'rtsp' else source.get('device', 'default')]
    if recording_length is not None:
        values.append(int(recording_length))
    return hashlib.sha256(json.dumps(values, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def recorder_source_revision(source, settings):
    """Settings consumed for one source, independent of every other source.

    This acknowledges the recorder loop's settings, not successful capture.
    Disabled sources only need their disabled flag acknowledged; connection,
    duration and schedule changes cannot affect a source that stays disabled.
    """
    enabled = source.get('enabled', True)
    values = [enabled]
    if enabled:
        values.extend([source_revision(source, settings.get('audio', {}).get('recording_length', 9)),
                       settings.get('schedule', {}), settings.get('location', {}).get('timezone')])
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def reconcile_recorders(recorders, sources, recording_length, factory):
    """Keep unchanged recorders; never start a replacement until stop succeeds.

    Returns failures keyed by source ID. Each source is independent, including
    retrying a failed constructor while healthy sources continue recording.
    """
    desired = {source['id']: source for source in sources}
    errors = {}
    for sid, recorder in list(recorders.items()):
        if sid not in desired or recorder.config_revision != source_revision(desired[sid], recording_length):
            try:
                recorder.stop()
                del recorders[sid]
            except Exception:
                errors[sid] = 'Could not stop previous recorder; retrying'
    for sid, source in desired.items():
        if sid in recorders:
            continue
        try:
            recorder = factory(source, recording_length)
            recorder.config_revision = source_revision(source, recording_length)
            recorders[sid] = recorder
            recorder.start()
        except Exception:
            errors[sid] = 'Could not start recorder; retrying'
    return errors
