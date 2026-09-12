"""Run the recorder loop through transitions that leave aggregate health unchanged."""
import copy
from datetime import datetime
from unittest.mock import Mock

import pytest


@pytest.fixture
def recording_loop(monkeypatch):
    import core.main as main
    from config.settings import get_default_settings

    settings = get_default_settings()
    settings['audio']['sources'] = [
        {'id': f'source_{i}', 'type': 'pulseaudio', 'device': f'mic-{i}', 'enabled': True}
        for i in range(2)
    ]
    recorders = {
        source['id']: Mock(consecutive_failures=0, last_success_time=0, last_error_time=0,
                           last_error_message='', is_healthy=Mock(return_value=True))
        for source in settings['audio']['sources']
    }
    for recorder in recorders.values():
        recorder.get_health_status.side_effect = lambda healthy, rec=recorder: {
            'is_healthy': healthy, 'last_success_time': rec.last_success_time,
            'last_error_time': rec.last_error_time, 'last_error_message': rec.last_error_message,
            'consecutive_failures': rec.consecutive_failures,
        }
    monkeypatch.setattr(main, 'setup_recorder', lambda source, *_: recorders[source['id']])
    monkeypatch.setattr(main, 'get_runtime_settings', lambda: copy.deepcopy(settings))
    monkeypatch.setattr(main, 'local_now', lambda: datetime(2026, 9, 9, 12))
    monkeypatch.setattr(main, '_maybe_notify_audio_status', Mock())
    monkeypatch.setattr(main, 'get_or_create_internal_secret', lambda: 'test-secret')
    post = Mock(return_value=Mock())
    monkeypatch.setattr(main.requests, 'post', post)

    def run(steps):
        tick = [0]
        monkeypatch.setattr(main.time, 'time', lambda: 1000 + 2 * tick[0])
        monkeypatch.setattr(main.time, 'monotonic', lambda: 1000 + 2 * tick[0])
        monkeypatch.setattr(main, 'stop_flag', Mock(is_set=lambda: tick[0] >= len(steps)))

        def advance(_):
            tick[0] += 1
            if tick[0] < len(steps):
                steps[tick[0]]()

        monkeypatch.setattr(main.time, 'sleep', advance)
        steps[0]()
        main.continuous_audio_recording(Mock())
        return [call.kwargs['json'] for call in post.call_args_list]

    return settings, recorders, post, run


def test_first_capture_is_broadcast_on_next_pass_for_each_source(recording_loop):
    _, recorders, _, run = recording_loop
    sent = run([
        lambda: None,
        lambda: setattr(recorders['source_0'], 'last_success_time', 1001),
        lambda: setattr(recorders['source_1'], 'last_success_time', 1003),
    ])
    assert [s['updated_at'] for s in sent] == [1000, 1002, 1004]
    assert [s['state'] for s in sent] == ['running'] * 3
    assert [[v['application_state'] for v in s['sources'].values()] for s in sent] == [
        ['connecting', 'connecting'], ['active', 'connecting'], ['active', 'active'],
    ]


def test_single_source_failure_and_recovery_do_not_wait_for_aggregate_degradation(recording_loop):
    _, recorders, _, run = recording_loop
    for recorder in recorders.values():
        recorder.last_success_time = 999
    sent = run([
        lambda: None,
        lambda: setattr(recorders['source_0'], 'consecutive_failures', 1),
        lambda: setattr(recorders['source_0'], 'consecutive_failures', 0),
    ])
    assert [s['state'] for s in sent] == ['running'] * 3
    assert [s['sources']['source_0']['application_state'] for s in sent] == ['active', 'failed', 'active']
    assert all(s['sources']['source_1']['application_state'] == 'active' for s in sent)


def test_new_error_details_are_broadcast_even_if_failure_state_is_unchanged(recording_loop):
    _, recorders, _, run = recording_loop
    recorder = recorders['source_0']
    recorder.consecutive_failures = 1
    recorder.last_error_message = 'Device unavailable'
    sent = run([lambda: None, lambda: setattr(recorder, 'last_error_message', 'Permission denied')])
    assert [s['sources']['source_0']['last_error_message'] for s in sent] == ['Device unavailable', 'Permission denied']


def test_settings_acknowledgement_is_broadcast_while_another_source_keeps_running(recording_loop):
    settings, _, _, run = recording_loop
    sent = run([
        lambda: None,
        lambda: settings['audio']['sources'][0].update(enabled=False),
        lambda: settings['audio']['sources'][0].update(enabled=True),
    ])
    assert [s['state'] for s in sent] == ['running'] * 3
    assert [set(s['sources']) for s in sent] == [{'source_0', 'source_1'}, {'source_1'}, {'source_0', 'source_1'}]
    assert sent[0]['source_settings_revisions']['source_0'] != sent[1]['source_settings_revisions']['source_0']
    assert sent[1]['source_settings_revisions']['source_1'] == sent[0]['source_settings_revisions']['source_1']


def test_success_timestamps_wait_for_heartbeat_without_hiding_the_latest_metrics(recording_loop):
    _, recorders, _, run = recording_loop
    steps = [lambda now=now: setattr(recorders['source_0'], 'last_success_time', now) for now in range(1000, 1007, 2)]
    sent = run(steps)
    assert [s['updated_at'] for s in sent] == [1000, 1006]
    assert sent[-1]['sources']['source_0']['last_success_time'] == 1006


@pytest.mark.parametrize('failed_attempt', [0, 1])
def test_failed_delivery_retries_on_next_pass_without_losing_the_transition(recording_loop, failed_attempt):
    _, recorders, post, run = recording_loop
    responses = [Mock() for _ in range(3)]
    responses[failed_attempt].raise_for_status.side_effect = RuntimeError('API unavailable')
    post.side_effect = responses
    sent = run([
        lambda: None,
        lambda: setattr(recorders['source_0'], 'last_success_time', 1001),
        lambda: None,
    ])
    assert [s['updated_at'] for s in sent] == ([1000, 1002] if failed_attempt == 0 else [1000, 1002, 1004])
    assert sent[-1]['sources']['source_0']['application_state'] == 'active'


def test_pause_clears_start_failures_from_before_it(recording_loop, monkeypatch):
    import core.main as main
    settings, _, _, run = recording_loop
    monkeypatch.setattr(main, 'setup_recorder', Mock(side_effect=OSError('device missing')))
    sent = run([
        lambda: None,
        lambda: settings['schedule'].update(quiet_hours={'enabled': True, 'start': '11:00', 'end': '13:00'}),
    ])
    assert [s['state'] for s in sent] == ['stopped', 'paused']
    assert all('reload_error' in v for v in sent[0]['sources'].values())
    # Nothing is being started while paused, so an old start failure is not a fault of the pause.
    assert not any('reload_error' in v for v in sent[1]['sources'].values())
