"""Validation shared by persisted settings and every settings write route."""
import math
import re
from zoneinfo import ZoneInfo

from config.constants import (
    OVERLAP_OPTIONS,
    RECORDING_LENGTH_OPTIONS,
    UPDATE_CHANNELS,
    VALID_MODEL_TYPES,
)


def validate_settings(settings, *, partial=False):
    """Return a user-facing error, or None. Accept partial documents too."""
    from config.settings import DEFAULT_SETTINGS

    def shape(value, default, path=''):
        if isinstance(default, dict):
            if not isinstance(value, dict):
                return f'{path or "Settings"} must be a JSON object'
            for key, item in value.items():
                name = f'{path}.{key}' if path else key
                if key not in default:
                    return f'Unknown setting: {name}'
                error = shape(item, default[key], name)
                if error:
                    return error
        elif isinstance(default, bool):
            if type(value) is not bool:
                return f'{path} must be a boolean'
        elif isinstance(default, (int, float)):
            if type(value) not in (int, float) or not math.isfinite(value):
                return f'{path} must be a finite number'
        elif isinstance(default, list):
            if not isinstance(value, list):
                return f'{path} must be an array'
            if path != 'audio.sources' and not all(isinstance(v, str) for v in value):
                return f'{path} must be a list of strings'
        elif default is None:
            if value is not None and not isinstance(value, str):
                return f'{path} must be a string or null'
        elif not isinstance(value, str):
            return f'{path} must be a string'
        return None

    error = shape(settings, DEFAULT_SETTINGS)
    if error:
        return error

    def read(path):
        section, key = path.split('.')
        return settings.get(section, {}).get(key)

    for path, low, high in (
        ('location.latitude', -90, 90), ('location.longitude', -180, 180),
        ('detection.sensitivity', 0.1, 1), ('detection.cutoff', 0, 1),
        ('detection.species_filter_threshold', 0, 1),
        ('storage.trigger_percent', 0, 100), ('storage.target_percent', 0, 100),
        ('spectrogram.min_freq_khz', 0, 24), ('spectrogram.max_freq_khz', 0, 24),
        ('spectrogram.min_dbfs', -200, 0), ('spectrogram.max_dbfs', -200, 0),
    ):
        value = read(path)
        if value is not None and not low <= value <= high:
            return f'{path} must be between {low} and {high}'
    for path, options in (
        ('audio.recording_length', RECORDING_LENGTH_OPTIONS),
        ('audio.overlap', OVERLAP_OPTIONS), ('audio.recording_chunk_length', (3,)),
        ('model.type', VALID_MODEL_TYPES), ('updates.channel', UPDATE_CHANNELS),
        ('display.time_format', ('12h', '24h')),
    ):
        value = read(path)
        if value is not None and value not in options:
            return f'Invalid {path}. Expected one of: {", ".join(map(str, options))}'
    for path, minimum in (
        ('audio.next_source_id', 0), ('storage.keep_per_species', 0),
        ('storage.keep_recent_per_species', 0), ('storage.retention_days', 0),
        ('notifications.rare_threshold', 0), ('notifications.rare_window_days', 1),
    ):
        value = read(path)
        if value is not None and (type(value) is not int or value < minimum):
            return f'{path} must be an integer of at least {minimum}'
    for path in ('notifications.rate_limit_seconds', 'storage.media_budget_gb', 'storage.check_interval_minutes'):
        value = read(path)
        if value is not None and (value < 0 or (path.endswith('minutes') and value == 0)):
            return f'{path} must be {"positive" if path.endswith("minutes") else "non-negative"}'
    for section, low, high in (
        ('storage', 'target_percent', 'trigger_percent'),
        ('spectrogram', 'min_freq_khz', 'max_freq_khz'),
        ('spectrogram', 'min_dbfs', 'max_dbfs'),
    ):
        values = settings.get(section, {})
        if low in values and high in values and values[low] >= values[high]:
            return f'{section}.{low} must be less than {high}'

    location = settings.get('location', {})
    timezone = location.get('timezone')
    if timezone:
        try:
            ZoneInfo(timezone)
        except (ValueError, KeyError):
            return 'Invalid location.timezone'
    language = read('display.bird_name_language')
    if language is not None:
        from core.bird_name_utils import SUPPORTED_BIRD_NAME_LANGUAGES
        if language not in SUPPORTED_BIRD_NAME_LANGUAGES:
            return 'Invalid display.bird_name_language'
    if 'schedule' in settings and not partial:
        from core.recording_schedule import validate_schedule_settings
        error = validate_schedule_settings(settings['schedule'])
        if error:
            return error

    audio = settings.get('audio', {})
    seen, microphones = set(), 0
    for source in audio.get('sources', []):
        if not isinstance(source, dict):
            return 'Each audio source must be a JSON object'
        if set(source) - {'id', 'type', 'url', 'device', 'label', 'enabled'}:
            return 'Unknown audio source field'
        sid = source.get('id')
        if not isinstance(sid, str) or not re.fullmatch(r'source_[0-9]+', sid):
            return 'Invalid source id. Must match source_<int>'
        if sid in seen:
            return f'Duplicate source id: {sid}'
        seen.add(sid)
        if source.get('type') not in ('pulseaudio', 'rtsp'):
            return 'Invalid source type. Must be pulseaudio or rtsp'
        if 'enabled' in source and type(source['enabled']) is not bool:
            return 'Source enabled must be a boolean'
        for key in ('url', 'device', 'label'):
            if key in source and (not isinstance(source[key], str) or '\x00' in source[key]):
                return f'Source {key} must be a string without null bytes'
        if source['type'] == 'rtsp' and not source.get('url', '').startswith(('rtsp://', 'rtsps://')):
            return f'RTSP source {sid} must have a valid rtsp:// or rtsps:// URL'
        microphones += source['type'] == 'pulseaudio'
    if microphones > 1:
        return 'Only one microphone source is allowed'
    if len(seen) > 10:
        return 'At most 10 audio sources are supported'
    if seen and 'next_source_id' in audio and audio['next_source_id'] <= max(int(s.split('_')[1]) for s in seen):
        return 'next_source_id must be greater than all existing source ids'
    return None
