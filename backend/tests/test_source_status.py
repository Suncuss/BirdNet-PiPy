"""Per-source acknowledgements must survive changes to unrelated sources."""
import copy
from unittest.mock import Mock

import pytest


@pytest.fixture
def station():
    import core.main as main
    from config.settings import get_default_settings
    from core.recording_schedule import enabled_sources
    from core.settings_status import build_settings_status
    from core.source_config import source_revision

    saved = get_default_settings()
    saved['audio']['sources'] = [
        {'id': f'source_{i}', 'type': 'rtsp', 'url': f'rtsp://camera/{i}', 'enabled': i < 2}
        for i in range(3)
    ]

    def report(applied, *, paused=False, failed=(), starting=()):
        sources = enabled_sources(applied['audio'])
        recorders = {} if paused else {
            source['id']: Mock(
                config_revision=source_revision(source, applied['audio']['recording_length']),
                consecutive_failures=0, last_success_time=0 if source['id'] in starting else 1000,
                is_healthy=Mock(return_value=True), get_health_status=Mock(return_value={}),
            ) for source in sources if source['id'] not in failed
        }
        snapshot = main.build_recorder_status(
            'paused' if paused else 'running', recorders, sources, settings=applied,
            pause={'reason': 'quiet_hours'} if paused else None,
            failures={sid: 'Could not start recorder; retrying' for sid in failed},
        )
        snapshot['updated_at'] = 1000
        return snapshot

    def streams(applied):
        return {'updated_at': 1000, 'sources': {
            source['id']: {'config_revision': source_revision(source), 'state': 'active'}
            for source in enabled_sources(applied['audio'])
        }}

    def read(config, recorder, streaming, now=1001):
        return build_settings_status(config, recorder, streaming, {'model': {'type': 'birdnet'}}, now=now)

    return saved, report, streams, read


@pytest.mark.parametrize('paused', [False, True])
@pytest.mark.parametrize('change', ['url', 'disable', 'add', 'remove'])
def test_unrelated_sources_stay_steady_before_change_is_applied(station, paused, change):
    saved, report, streams, read = station
    recorder, streaming = report(saved, paused=paused), streams(saved)
    changed = copy.deepcopy(saved)
    sources = changed['audio']['sources']
    if change == 'url':
        sources[0]['url'] = 'rtsp://replacement/audio'
    elif change == 'disable':
        sources[0]['enabled'] = False
    elif change == 'add':
        sources.append({'id': 'new', 'type': 'pulseaudio', 'enabled': True})
    else:
        sources.pop(0)
    result = read(changed, recorder, streaming)
    assert result['recording'] == 'pending'
    assert result['sources']['source_1'] == {'recording': 'paused' if paused else 'active', 'streaming': 'active'}
    assert result['sources']['source_2'] == {'recording': 'disabled', 'streaming': 'disabled'}
    if change in {'url', 'disable', 'add'}:
        assert result['sources']['new' if change == 'add' else 'source_0']['recording'] == 'pending'


@pytest.mark.parametrize('paused', [False, True])
def test_overlapping_changes_finish_independently(station, paused):
    saved, report, streams, read = station
    first = copy.deepcopy(saved)
    first['audio']['sources'][0]['url'] = 'rtsp://first/change'
    both = copy.deepcopy(first)
    both['audio']['sources'][1]['url'] = 'rtsp://second/change'
    result = read(both, report(saved, paused=paused), streams(saved))
    assert [result['sources'][f'source_{i}']['recording'] for i in range(3)] == ['pending', 'pending', 'disabled']
    result = read(both, report(first, paused=paused), streams(first))
    assert [result['sources'][f'source_{i}']['recording'] for i in range(3)] == [
        'paused' if paused else 'active', 'pending', 'disabled',
    ]
    result = read(both, report(both, paused=paused), streams(both))
    assert result['recording'] == 'current'
    assert result['sources']['source_1']['recording'] == ('paused' if paused else 'active')


@pytest.mark.parametrize('change,paused', [('length', False), ('length', True), ('schedule', True), ('timezone', True)])
def test_shared_changes_wait_for_each_affected_source_but_not_disabled_sources(station, change, paused):
    saved, report, streams, read = station
    recorder, streaming = report(saved, paused=paused), streams(saved)
    if change == 'length':
        saved['audio']['recording_length'] = 12
    elif change == 'schedule':
        saved['schedule']['quiet_hours']['end'] = '07:00'
    else:
        saved['location']['timezone'] = 'America/New_York'
    result = read(saved, recorder, streaming)
    assert [result['sources'][f'source_{i}']['recording'] for i in range(3)] == ['pending', 'pending', 'disabled']


def test_renaming_and_editing_a_disabled_connection_do_not_change_source_state(station):
    saved, report, streams, read = station
    recorder, streaming = report(saved, paused=True), streams(saved)
    saved['audio']['sources'][0]['label'] = 'New label'
    saved['audio']['sources'][2]['url'] = 'rtsp://unused/replacement'
    result = read(saved, recorder, streaming)
    assert [result['sources'][f'source_{i}']['recording'] for i in range(3)] == ['paused', 'paused', 'disabled']


def test_enable_requires_new_acknowledgement_and_actual_capture(station):
    saved, report, streams, read = station
    recorder, streaming = report(saved, paused=True), streams(saved)
    saved['audio']['sources'][2]['enabled'] = True
    assert read(saved, recorder, streaming)['sources']['source_2']['recording'] == 'pending'
    starting = report(saved, starting=['source_2'])
    assert read(saved, starting, streams(saved))['sources']['source_2']['recording'] == 'connecting'
    active = report(saved)
    assert read(saved, active, streams(saved))['sources']['source_2']['recording'] == 'active'


def test_disabled_acknowledgement_does_not_hide_a_process_that_has_not_stopped(station):
    saved, report, streams, read = station
    previous = report(saved)['sources']['source_0']
    saved['audio']['sources'][0]['enabled'] = False
    stopped = report(saved)
    still_stopping = copy.deepcopy(stopped)
    still_stopping['sources']['source_0'] = previous
    assert read(saved, still_stopping, streams(saved))['sources']['source_0']['recording'] == 'pending'
    assert read(saved, stopped, streams(saved))['sources']['source_0']['recording'] == 'disabled'


def test_unrelated_save_does_not_hide_an_existing_reload_failure(station):
    saved, report, streams, read = station
    recorder, streaming = report(saved, failed=['source_0']), streams(saved)
    saved['audio']['sources'][1]['url'] = 'rtsp://other/change'
    result = read(saved, recorder, streaming)
    assert result['sources']['source_0']['recording'] == 'failed'
    assert result['sources']['source_1']['recording'] == 'pending'


def test_expired_acknowledgements_are_unknown_even_for_unchanged_sources(station):
    saved, report, streams, read = station
    result = read(saved, report(saved, paused=True), streams(saved), now=1021)
    assert all(value == {'recording': 'unknown', 'streaming': 'unknown'} for value in result['sources'].values())


def test_missing_per_source_acknowledgement_cannot_claim_disabled(station):
    saved, report, streams, read = station
    recorder = report(saved)
    del recorder['source_settings_revisions']['source_2']
    assert read(saved, recorder, streams(saved))['sources']['source_2']['recording'] == 'pending'
