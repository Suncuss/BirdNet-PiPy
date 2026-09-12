"""Shared status delivery, freshness and recovery without browser polling."""
import copy
from unittest.mock import Mock

import pytest


@pytest.fixture
def monitor(monkeypatch):
    from core.settings_monitor import SettingsStatusMonitor

    clock = [100.0]
    monkeypatch.setattr('core.settings_monitor.time.monotonic', lambda: clock[0])
    socketio = Mock()
    snapshot = {'revision': '"saved"', 'recording': 'current', 'streaming': 'current'}
    result = SettingsStatusMonitor(socketio, 'watchers', Mock(return_value=snapshot), Mock(return_value={'status': 'ok'}))
    # Deterministic completion for ordinary tests. Blocking-request tests leave
    # the task queued; the runtime suite exercises real threads and greenlets.
    socketio.start_background_task.side_effect = lambda target, *args: (
        None if target == result.run else target(*args))
    return result, clock


def test_emits_changes_and_heartbeats_with_one_shared_model_check(monitor):
    status, clock = monitor
    status.subscribe()
    status.subscribe()
    status.socketio.start_background_task.assert_called_once()
    status.poll()
    status.socketio.emit.assert_called_once_with('settings_status', status.read_snapshot.return_value, room='watchers')
    status.socketio.emit.reset_mock()
    for now in [101, 102, 103, 104]:
        clock[0] = now
        status.poll()
    status.socketio.emit.assert_not_called()
    status.read_model.assert_called_once()

    clock[0] = 105
    status.poll()
    status.socketio.emit.assert_called_once()
    assert status.read_model.call_count == 2
    status.socketio.emit.reset_mock()
    status.read_snapshot.return_value = {'revision': '"saved"', 'streaming': 'unknown'}
    clock[0] = 106
    status.poll()
    status.socketio.emit.assert_called_once_with('settings_status', status.read_snapshot.return_value, room='watchers')


def test_reconnect_gets_fresh_snapshot_even_without_a_state_change(monitor):
    status, clock = monitor
    status.poll()
    status.socketio.emit.reset_mock()
    status.subscribe()
    status.socketio.emit.assert_not_called()  # no stale cache replay
    clock[0] += 1
    status.poll()
    status.socketio.emit.assert_called_once_with('settings_status', status.read_snapshot.return_value, room='watchers')


def test_failed_sampling_clears_status_and_recovers(monitor):
    status, clock = monitor
    status.poll()
    status.read_snapshot.side_effect = ValueError('invalid saved configuration')
    clock[0] += 1
    status.poll()
    status.socketio.emit.assert_called_with('settings_status', None, room='watchers')
    status.read_snapshot.side_effect = None
    clock[0] += 1
    status.poll()
    status.socketio.emit.assert_called_with('settings_status', status.read_snapshot.return_value, room='watchers')


def test_samples_current_revision_while_model_request_is_pending_and_after_completion(monitor):
    status, clock = monitor
    saved = {'revision': '"before"'}
    status.socketio.start_background_task.side_effect = None
    status.read_snapshot.side_effect = lambda model: {**saved, 'model_service': model}
    status.poll()
    status.socketio.emit.assert_called_with('settings_status', {
        'revision': '"before"', 'model_service': {'status': 'loading'},
    }, room='watchers')
    saved['revision'] = '"after"'
    clock[0] += 1
    status.poll()
    status.socketio.emit.assert_called_with('settings_status', {
        'revision': '"after"', 'model_service': {'status': 'loading'},
    }, room='watchers')
    status.socketio.start_background_task.assert_called_once()
    target, *args = status.socketio.start_background_task.call_args.args
    target(*args)
    status.poll()
    status.socketio.emit.assert_called_with('settings_status', {
        'revision': '"after"', 'model_service': {'status': 'ok'},
    }, room='watchers')


def test_audio_heartbeats_cannot_keep_a_stalled_model_check_healthy(monitor):
    status, clock = monitor
    status.read_snapshot.side_effect = lambda model: {'recording': 'current', 'model_service': model}
    status.poll()
    status.socketio.start_background_task.reset_mock()
    status.socketio.start_background_task.side_effect = None
    for now in [105, 110, 115, 120]:
        clock[0] = now
        status.poll()
    status.socketio.start_background_task.assert_called_once()  # no overlapping requests
    assert status.socketio.emit.call_args.args[1] == {'recording': 'current', 'model_service': {}}
    target, *args = status.socketio.start_background_task.call_args.args
    target(*args)  # late "healthy" response describes a request from fifteen seconds ago
    status.poll()
    assert status.read_snapshot.call_args.args[0] == {}
    status.socketio.start_background_task.side_effect = lambda target, *args: target(*args)
    clock[0] = 125
    status.poll()
    assert status.socketio.emit.call_args.args[1]['model_service'] == {'status': 'ok'}


def test_initial_model_loading_expires_while_audio_continues(monitor):
    status, clock = monitor
    status.socketio.start_background_task.side_effect = None
    status.poll()
    status.read_snapshot.assert_called_with({'status': 'loading'})
    clock[0] += status.MODEL_MAX_AGE
    status.poll()
    status.read_snapshot.assert_called_with({})
    status.socketio.start_background_task.assert_called_once()


def test_expired_model_result_reloads_instead_of_reporting_a_gap(monitor):
    status, clock = monitor
    status.poll()
    status.read_snapshot.assert_called_with({'status': 'ok'})
    # Owners were away longer than the result lives; the reconnect sample must
    # not claim the model is unknown while its fresh check is under way.
    clock[0] += status.MODEL_MAX_AGE + 10
    status.socketio.start_background_task.side_effect = None
    status.poll()
    status.read_snapshot.assert_called_with({'status': 'loading'})
    target, *args = status.socketio.start_background_task.call_args.args
    target(*args)
    status.poll()
    status.read_snapshot.assert_called_with({'status': 'ok'})


@pytest.mark.parametrize('failure', ['request', 'task_start'])
def test_model_check_failures_do_not_clear_audio_and_retry(monitor, failure):
    status, clock = monitor
    status.poll()
    clock[0] += status.MODEL_INTERVAL
    if failure == 'request':
        status.read_model.side_effect = RuntimeError('model unavailable')
    else:
        status.socketio.start_background_task.side_effect = RuntimeError('task could not start')
    status.poll()
    status.read_snapshot.assert_called_with({})
    status.socketio.emit.assert_called_with('settings_status', status.read_snapshot.return_value, room='watchers')
    status.read_model.side_effect = None
    status.socketio.start_background_task.side_effect = lambda target, *args: target(*args)
    clock[0] += status.MODEL_INTERVAL
    status.poll()
    status.read_snapshot.assert_called_with({'status': 'ok'})


def test_failed_reconnect_delivery_retries_without_waiting_for_heartbeat(monitor):
    status, clock = monitor
    status.poll()
    status.subscribe()
    status.socketio.emit.side_effect = RuntimeError('temporary delivery failure')
    clock[0] += 1
    with pytest.raises(RuntimeError):
        status.poll()
    status.socketio.emit.side_effect = None
    clock[0] += 1
    status.poll()
    status.socketio.emit.assert_called_with('settings_status', status.read_snapshot.return_value, room='watchers')


def test_idle_monitor_does_not_read_services(monitor):
    status, _ = monitor
    status.socketio.server.manager.get_participants.return_value = []
    status.socketio.sleep.side_effect = InterruptedError
    with pytest.raises(InterruptedError):
        status.run()
    status.read_snapshot.assert_not_called()
    status.read_model.assert_not_called()


def test_delivery_failure_does_not_stop_monitor(monitor):
    status, _ = monitor
    status.socketio.server.manager.get_participants.return_value = [('owner', 'connection')]
    status.socketio.emit.side_effect = [RuntimeError('temporary delivery failure'), None]
    status.socketio.sleep.side_effect = [None, InterruptedError]
    with pytest.raises(InterruptedError):
        status.run()
    assert status.socketio.emit.call_count == 2
    status.read_model.assert_called_once()


def test_service_silence_is_reported_without_an_event_and_recovers(monitor):
    from config.settings import get_default_settings
    from core.settings_status import build_settings_status
    from core.source_config import recorder_source_revision, source_revision

    status, clock = monitor
    saved = get_default_settings()
    source = {'id': 'mic', 'type': 'pulseaudio', 'enabled': True}
    saved['audio']['sources'] = [source]
    recorder = {
        'updated_at': 100, 'model_type': 'birdnet',
        'source_settings_revisions': {'mic': recorder_source_revision(source, saved)},
        'sources': {'mic': {'config_revision': source_revision(source, saved['audio']['recording_length']),
                            'application_state': 'active'}},
    }
    stream = {'updated_at': 100, 'sources': {'mic': {'config_revision': source_revision(source), 'state': 'active'}}}
    status.read_model.return_value = {'model': {'type': 'birdnet'}, 'location_filter': {'state': 'active'}}
    status.read_snapshot.side_effect = lambda model: build_settings_status(saved, recorder, stream, model, now=clock[0])
    status.poll()
    initial = copy.deepcopy(status.socketio.emit.call_args.args[1])
    assert initial['sources']['mic'] == {'recording': 'active', 'streaming': 'active'}
    clock[0] = 121
    status.poll()
    assert status.socketio.emit.call_args.args[1]['sources']['mic'] == {'recording': 'unknown', 'streaming': 'unknown'}
    recorder['updated_at'] = stream['updated_at'] = 121
    status.poll()
    assert status.socketio.emit.call_args.args[1] == initial
