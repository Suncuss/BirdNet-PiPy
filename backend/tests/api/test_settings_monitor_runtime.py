"""Exercise monitor startup in both supported Socket.IO execution modes."""
import subprocess
import sys

import pytest


@pytest.mark.parametrize('mode', ['threading', 'gevent'])
def test_shared_monitor_runs_in_api_execution_mode(mode):
    # gevent must patch before any API imports, just as wsgi.py does. A child
    # process also disposes the real background task after the test app exits.
    result = subprocess.run([sys.executable, '-c', '''
import sys
if sys.argv[1] == 'gevent':
    from gevent import monkey
    monkey.patch_all()
import time
import threading
from unittest.mock import Mock
from tests.api.conftest import sandboxed_auth_env

with sandboxed_auth_env(mock_socketio=False) as (api, _):
    app, socketio = api.create_app(async_mode=sys.argv[1])
    monitor = app.extensions['settings_status_monitor']
    monitor.SAMPLE_INTERVAL = 0.01
    release_model = threading.Event()
    def read_model():
        assert release_model.wait(3), 'audio delivery was blocked behind model HTTP'
        return {'status': 'ok'}
    monitor.read_model = Mock(side_effect=read_model)
    snapshot = {'revision': '"saved"', 'recording': 'current', 'streaming': 'current'}
    monitor.read_snapshot = Mock(side_effect=lambda model: {**snapshot, 'model_service': model})
    clients = [socketio.test_client(app), socketio.test_client(app)]
    for client in clients:
        client.emit('watch_settings_status')

    def receive(expected):
        waiting = set(range(len(clients)))
        deadline = time.monotonic() + 3
        while waiting and time.monotonic() < deadline:
            for i in list(waiting):
                if any(e['name'] == 'settings_status' and e['args'][0] == expected
                       for e in clients[i].get_received()):
                    waiting.remove(i)
            socketio.sleep(0.01)
        assert not waiting, 'missing pushed snapshot'

    receive({**snapshot, 'model_service': {'status': 'loading'}})
    snapshot['streaming'] = 'unknown'
    snapshot['revision'] = '"newly saved"'
    receive({**snapshot, 'model_service': {'status': 'loading'}})
    release_model.set()
    receive({**snapshot, 'model_service': {'status': 'ok'}})
    monitor.read_model.assert_called_once()
    for client in clients:
        client.disconnect()
    socketio.sleep(0.03)
    calls = monitor.read_snapshot.call_count
    socketio.sleep(0.03)
    assert monitor.read_snapshot.call_count == calls, 'sampling continued without owners'
''', mode], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
