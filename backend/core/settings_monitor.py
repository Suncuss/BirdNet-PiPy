"""One settings-health sampler for the sockets watching the Settings page."""
import threading
import time

from core.logging_config import get_logger

logger = get_logger(__name__)


class SettingsStatusMonitor:
    SAMPLE_INTERVAL = 1
    MODEL_INTERVAL = 5
    MODEL_MAX_AGE = 15
    HEARTBEAT_INTERVAL = 5

    def __init__(self, socketio, room, read_snapshot, read_model):
        self.socketio = socketio
        self.room = room
        self.read_snapshot = read_snapshot
        self.read_model = read_model
        self._lock = threading.Lock()  # hub-only: socket handlers and SocketIO task, never the DB lane
        self._started = False
        # Watch requests are counted, not flagged: one that lands between a
        # sample's emit and its bookkeeping still gets the next sample.
        self._requested = 0
        self._served = 0
        self._snapshot = None
        self._model = None
        self._model_inflight = False
        self._model_started_at = 0
        self._next_model_check = 0
        self._last_emit = 0

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
            self.socketio.start_background_task(self.run)

    def subscribe(self):
        # Queue a freshly sampled snapshot for a new or reconnected watcher,
        # including when nothing has changed since its disconnection. Never
        # replay an old healthy cache.
        with self._lock:
            self._requested += 1
        self.start()

    def _refresh_model(self, started_at):
        try:
            model = self.read_model()
        except Exception:
            logger.warning('Unable to sample model status; retrying', exc_info=True)
            model = {}
        with self._lock:
            # Age from request start: a very late response cannot revive old
            # health. Only one request may be in flight for the entire worker.
            self._model = (started_at, model)
            self._next_model_check = time.monotonic() + self.MODEL_INTERVAL
            self._model_inflight = False

    def _model_snapshot(self):
        now = time.monotonic()
        with self._lock:
            start = not self._model_inflight and now >= self._next_model_check
            if start:
                self._model_inflight = True
                self._model_started_at = now
        if start:
            try:
                self.socketio.start_background_task(self._refresh_model, now)
            except Exception:
                logger.warning('Unable to start model status check; retrying', exc_info=True)
                with self._lock:
                    self._model_inflight = False
                    self._model = (now, {})
                    self._next_model_check = now + self.MODEL_INTERVAL
        with self._lock:
            now = time.monotonic()
            if self._model is not None:
                sampled_at, model = self._model
                if now - sampled_at < self.MODEL_MAX_AGE:
                    return model
            # Never sampled, or expired while owners were away: a young request
            # is still loading, not unknown, so the UI does not report a gap.
            if self._model_inflight and now - self._model_started_at < self.MODEL_MAX_AGE:
                return {'status': 'loading'}
            return {}

    def poll(self):
        try:
            # Audio and saved revisions never wait for model HTTP. A cached
            # model result has its own expiry even while audio keeps arriving.
            snapshot = self.read_snapshot(self._model_snapshot())
        except Exception:
            logger.warning('Unable to sample settings status', exc_info=True)
            snapshot = None

        now = time.monotonic()
        with self._lock:
            requested = self._requested
        if requested != self._served or snapshot != self._snapshot or now - self._last_emit >= self.HEARTBEAT_INTERVAL:
            # Every watcher is in the room, so one emit serves changes,
            # heartbeats and fresh snapshots alike. A failed emit raises before
            # the bookkeeping, so the request is retried on the next sample.
            self.socketio.emit('settings_status', snapshot, room=self.room)
            self._served = requested
            self._last_emit = now
        self._snapshot = snapshot

    def run(self):
        while True:
            try:
                # No model requests or file reads while nobody watches.
                if tuple(self.socketio.server.manager.get_participants('/', self.room)):
                    self.poll()
            except Exception:
                logger.warning('Settings status delivery failed; retrying', exc_info=True)
            self.socketio.sleep(self.SAMPLE_INTERVAL)
