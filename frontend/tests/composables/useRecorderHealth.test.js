import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useRecorderHealth } from '@/composables/useRecorderHealth'
import { RECORDER_DISMISSED_UNTIL_KEY } from '@/utils/storageKeys'

// Mock the api service
const mockApi = vi.hoisted(() => ({
  get: vi.fn()
}))

vi.mock('@/services/api', () => ({
  default: mockApi
}))

// Mock socket.io — the composable owns the app-wide recorder_status socket
const socketHandlers = vi.hoisted(() => ({}))
const socketMock = vi.hoisted(() => ({
  on: vi.fn((event, handler) => { socketHandlers[event] = handler }),
  once: vi.fn((event, handler) => { socketHandlers[event] = handler }),
  emit: vi.fn(),
  connected: true,
  connect: vi.fn(),
  disconnect: vi.fn()
}))
const ioMock = vi.hoisted(() => vi.fn(() => socketMock))

vi.mock('socket.io-client', () => ({ io: ioMock }))

// Mock useAuth
const mockIsAuthenticated = vi.hoisted(() => ({ value: true }))

vi.mock('@/composables/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: mockIsAuthenticated
  })
}))

// Mock localStorage
const mockStorage = {}
vi.stubGlobal('localStorage', {
  getItem: vi.fn((key) => mockStorage[key] ?? null),
  setItem: vi.fn((key, val) => { mockStorage[key] = val }),
  removeItem: vi.fn((key) => { delete mockStorage[key] })
})

// Reset module-level singleton between tests by re-importing
// We use a helper that sets status to a known "running" state (no warning shown)
async function resetRecorderState() {
  mockApi.get.mockResolvedValueOnce({ data: { state: 'running' } })
  const { checkStatus } = useRecorderHealth()
  await checkStatus()
}

describe('useRecorderHealth', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    mockIsAuthenticated.value = true

    await resetRecorderState()

    // Clear storage mock
    for (const key of Object.keys(mockStorage)) {
      delete mockStorage[key]
    }
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('checkStatus', () => {
    it('calls /recorder/status endpoint', async () => {
      mockApi.get.mockResolvedValue({ data: {} })
      const { checkStatus } = useRecorderHealth()

      await checkStatus()

      expect(mockApi.get).toHaveBeenCalledWith('/recorder/status')
    })

    it('does not call /stream/config', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'running' } })
      const { checkStatus } = useRecorderHealth()

      await checkStatus()

      expect(mockApi.get).not.toHaveBeenCalledWith('/stream/config')
    })

    it('updates status when response has state field', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'degraded', message: 'Source failed' } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(true)
    })

    it('does not update status when response has no state field', async () => {
      mockApi.get.mockResolvedValue({ data: {} })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(false)
    })

    it('handles repeated calls with same state without error', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'degraded' } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()
      await checkStatus()
      expect(showRecorderWarning.value).toBe(true)
    })

    it('silently handles errors without throwing', async () => {
      mockApi.get.mockRejectedValue(new Error('Network error'))
      const { checkStatus } = useRecorderHealth()

      // Should not throw
      await expect(checkStatus()).resolves.toBeUndefined()
    })

    it('ignores an older refresh that finishes after a newer one', async () => {
      let resolveOlder
      let resolveNewer
      mockApi.get
        .mockImplementationOnce(() => new Promise(resolve => { resolveOlder = resolve }))
        .mockImplementationOnce(() => new Promise(resolve => { resolveNewer = resolve }))
      const { checkStatus, recorderStatus } = useRecorderHealth()

      const older = checkStatus()
      const newer = checkStatus()
      resolveNewer({ data: { state: 'running' } })
      await newer
      resolveOlder({ data: { state: 'degraded' } })
      await older

      expect(recorderStatus.value.state).toBe('running')
    })

    it('does not restore status from a refresh that finishes after disconnect', async () => {
      let resolveRequest
      mockApi.get.mockImplementationOnce(() => new Promise(resolve => { resolveRequest = resolve }))
      const { checkStatus, disconnect, recorderStatus } = useRecorderHealth()

      const pending = checkStatus()
      disconnect()
      resolveRequest({ data: { state: 'degraded' } })
      await pending

      expect(recorderStatus.value).toBeNull()
    })
  })

  describe('showRecorderWarning', () => {
    it('shows warning when state is degraded and user is authenticated', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'degraded' } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(true)
    })

    it('shows warning when state is stopped and user is authenticated', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'stopped' } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(true)
    })

    it('does not show warning when state is paused by the schedule (not a fault)', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'paused', pause: { reason: 'quiet_hours', resumes_at: '2026-08-25T06:00' } } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(false)
    })

    it('does not show warning when state is running', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'running' } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(false)
    })

    it('does not show warning when user is not authenticated', async () => {
      mockIsAuthenticated.value = false
      mockApi.get.mockResolvedValue({ data: { state: 'degraded' } })
      const { checkStatus, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showRecorderWarning.value).toBe(false)
    })
  })

  describe('showPausedIndicator', () => {
    const pausedStatus = (resumesAt = '2026-08-25T06:00') => ({
      data: { state: 'paused', pause: { reason: 'quiet_hours', resumes_at: resumesAt } }
    })

    it('shows while the schedule has the station paused', async () => {
      mockApi.get.mockResolvedValue(pausedStatus())
      const { checkStatus, showPausedIndicator, showRecorderWarning } = useRecorderHealth()

      await checkStatus()

      expect(showPausedIndicator.value).toBe(true)
      // Never both: a pause is not a fault
      expect(showRecorderWarning.value).toBe(false)
    })

    it('labels the resume time from the pause payload', async () => {
      mockApi.get.mockResolvedValue(pausedStatus())
      const { checkStatus, pausedLabel } = useRecorderHealth()

      await checkStatus()

      expect(pausedLabel.value).toMatch(/^Paused until /)
      expect(pausedLabel.value).toContain('6:00')
    })

    it('falls back to a plain label when the pause carries no resume time', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'paused', pause: null } })
      const { checkStatus, pausedLabel } = useRecorderHealth()

      await checkStatus()

      expect(pausedLabel.value).toBe('Audio Paused')
    })

    it('labels a sourceless pause plainly, with the reason in the title', async () => {
      mockApi.get.mockResolvedValue({
        data: { state: 'paused', pause: { reason: 'no_sources', resumes_at: null } }
      })
      const { checkStatus, showPausedIndicator, showRecorderWarning,
              pausedLabel, pausedTitle, pauseReason } = useRecorderHealth()

      await checkStatus()

      expect(showPausedIndicator.value).toBe(true)
      expect(showRecorderWarning.value).toBe(false)
      expect(pausedLabel.value).toBe('Audio Paused')
      expect(pausedTitle.value).toBe('Recording is paused — no audio source is active')
      expect(pauseReason.value).toBe('no_sources')
    })

    it('refreshes the label when the window end moves while still paused', async () => {
      const { checkStatus, pausedLabel } = useRecorderHealth()

      mockApi.get.mockResolvedValue(pausedStatus('2026-08-25T06:00'))
      await checkStatus()
      const before = pausedLabel.value

      // Same aggregate state, new resume time — must not be ignored as churn
      mockApi.get.mockResolvedValue(pausedStatus('2026-08-25T07:00'))
      await checkStatus()

      expect(pausedLabel.value).not.toBe(before)
      expect(pausedLabel.value).toContain('7:00')
    })

    it.each([['running'], ['degraded'], ['stopped']])('stays hidden when state is %s', async (state) => {
      mockApi.get.mockResolvedValue({ data: { state } })
      const { checkStatus, showPausedIndicator } = useRecorderHealth()

      await checkStatus()

      expect(showPausedIndicator.value).toBe(false)
    })

    it('stays hidden for an anonymous viewer', async () => {
      mockIsAuthenticated.value = false
      mockApi.get.mockResolvedValue(pausedStatus())
      const { checkStatus, showPausedIndicator } = useRecorderHealth()

      await checkStatus()

      expect(showPausedIndicator.value).toBe(false)
    })
  })

  describe('dismissWarning', () => {
    it('hides warning after dismiss', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'degraded' } })
      const { checkStatus, showRecorderWarning, dismissWarning } = useRecorderHealth()

      await checkStatus()
      expect(showRecorderWarning.value).toBe(true)

      dismissWarning()
      expect(showRecorderWarning.value).toBe(false)
    })

    it('persists dismissal to localStorage', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'degraded' } })
      const { checkStatus, dismissWarning } = useRecorderHealth()

      await checkStatus()
      dismissWarning()

      expect(localStorage.setItem).toHaveBeenCalledWith(
        RECORDER_DISMISSED_UNTIL_KEY,
        expect.any(String)
      )
    })
  })

  describe('live updates', () => {
    beforeEach(() => {
      useRecorderHealth().disconnect()
      Object.keys(socketHandlers).forEach((key) => delete socketHandlers[key])
      ioMock.mockClear()
      socketMock.emit.mockClear()
      socketMock.connect.mockClear()
      socketMock.disconnect.mockClear()
    })

    // Watches outlive a socket on purpose (a page stays mounted across a
    // re-login), so tests release theirs explicitly.
    const watches = []
    const watch = (health) => {
      const stop = health.watchSettingsStatus()
      watches.push(stop)
      return stop
    }

    afterEach(() => {
      watches.splice(0).forEach(stop => stop())
      useRecorderHealth().disconnect()
    })

    it('opens one socket on the base-path-aware path, however often it is asked', () => {
      const { connect } = useRecorderHealth()

      connect()
      connect()

      expect(ioMock).toHaveBeenCalledTimes(1)
      expect(ioMock).toHaveBeenCalledWith({ path: '/socket.io' })
    })

    it('adopts a pushed status without a refetch, so the badge follows the station', () => {
      const { connect, recorderStatus, showPausedIndicator } = useRecorderHealth()
      connect()
      mockApi.get.mockClear()

      socketHandlers.recorder_status({
        state: 'paused',
        pause: { reason: 'no_sources', resumes_at: null }
      })

      expect(recorderStatus.value.state).toBe('paused')
      expect(showPausedIndicator.value).toBe(true)
      expect(mockApi.get).not.toHaveBeenCalled()
    })

    it('falls back to the REST value when the handshake fails', async () => {
      mockApi.get.mockResolvedValue({ data: { state: 'running' } })
      const { connect } = useRecorderHealth()
      connect()
      mockApi.get.mockClear()

      socketHandlers.connect_error(new Error('origin mismatch'))

      await vi.waitFor(() =>
        expect(mockApi.get).toHaveBeenCalledWith('/recorder/status'))
    })

    it('reconnects when the server evicts the session', () => {
      const { connect } = useRecorderHealth()
      connect()

      socketHandlers.session_revoked()

      expect(socketMock.disconnect).toHaveBeenCalled()
      expect(socketMock.connect).toHaveBeenCalled()
    })

    it('shares settings snapshots without issuing status requests', () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      mockApi.get.mockClear()
      const status = { revision: '"saved"', sources: { mic: { recording: 'active', streaming: 'failed' } } }
      socketHandlers.settings_status(status)
      expect(useRecorderHealth().settingsStatus.value).toEqual(status)
      expect(mockApi.get).not.toHaveBeenCalled()
    })

    it('loads only until the first snapshot and does not reset when reused', () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      expect(health.settingsStatusLoading.value).toBe(true)
      socketHandlers.settings_status({ revision: '"saved"' })
      health.connect()
      watch(health)
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(health.settingsStatus.value.revision).toBe('"saved"')
      expect(ioMock).toHaveBeenCalledTimes(1)
    })

    it('bounds the initial wait even when no snapshot ever arrives', async () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      await vi.advanceTimersByTimeAsync(14999)
      expect(health.settingsStatusLoading.value).toBe(true)
      await vi.advanceTimersByTimeAsync(1)
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(health.settingsStatus.value).toBeNull()
      expect(vi.getTimerCount()).toBe(0)
    })

    it.each(['connect_error', 'disconnect', 'settings_status'])('ends initial loading on %s failure', (event) => {
      const health = useRecorderHealth()
      mockApi.get.mockResolvedValue({ data: {} })
      health.connect()
      watch(health)
      socketHandlers[event](event === 'connect_error' ? new Error('unreachable') : null)
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(health.settingsStatus.value).toBeNull()
      socketHandlers.settings_status({ revision: '"recovered"' })
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(health.settingsStatus.value.revision).toBe('"recovered"')
    })

    it('expires silent status, extends it on heartbeats, and recovers on a fresh snapshot', async () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      const status = { revision: '"saved"', recording: 'current', streaming: 'current' }
      socketHandlers.settings_status(status)
      await vi.advanceTimersByTimeAsync(10000)
      socketHandlers.settings_status(status)
      await vi.advanceTimersByTimeAsync(10000)
      expect(health.settingsStatus.value).toEqual(status)
      await vi.advanceTimersByTimeAsync(5000)
      expect(health.settingsStatus.value).toBeNull()
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(health.recorderStatus.value).toBeNull()
      socketHandlers.settings_status(status)
      expect(health.settingsStatus.value).toEqual(status)
    })

    it('clears both statuses on disconnect and accepts the reconnect snapshot', () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      socketHandlers.recorder_status({ state: 'running' })
      socketHandlers.settings_status({ revision: '"old"' })
      socketHandlers.disconnect()
      expect(health.settingsStatus.value).toBeNull()
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(health.recorderStatus.value).toBeNull()
      socketHandlers.settings_status({ revision: '"new"' })
      expect(health.settingsStatus.value.revision).toBe('"new"')
    })

    it('cannot restore owner status from a socket discarded at logout', () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      const lateSettings = socketHandlers.settings_status
      const lateRecorder = socketHandlers.recorder_status
      health.disconnect()
      lateSettings({ revision: '"old"' })
      lateRecorder({ state: 'running' })
      expect(health.settingsStatus.value).toBeNull()
      expect(health.recorderStatus.value).toBeNull()
      expect(vi.getTimerCount()).toBe(0)
    })

    it('ignores a discarded socket failure during a new login', async () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      const oldError = socketHandlers.connect_error
      health.disconnect()
      ioMock.mockReturnValueOnce({ ...socketMock })
      health.connect()
      mockApi.get.mockClear()
      oldError(new Error('old connection'))
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(mockApi.get).not.toHaveBeenCalled()
    })

    it('asks the API for settings status only while a page watches, and again on every connection', () => {
      const health = useRecorderHealth()
      health.connect()
      expect(socketMock.emit).not.toHaveBeenCalled()
      const unwatch = watch(health)
      const unwatchSecond = watch(health)
      expect(socketMock.emit.mock.calls).toEqual([['watch_settings_status']])
      socketHandlers.connect()
      expect(socketMock.emit.mock.calls).toEqual([['watch_settings_status'], ['watch_settings_status']])
      socketHandlers.settings_status({ revision: '"saved"' })
      unwatchSecond()
      expect(health.settingsStatus.value.revision).toBe('"saved"')
      unwatch()
      unwatch()
      expect(socketMock.emit).toHaveBeenLastCalledWith('unwatch_settings_status')
      expect(socketMock.emit).toHaveBeenCalledTimes(3)
      expect(health.settingsStatus.value).toBeNull()
      expect(health.settingsStatusLoading.value).toBe(false)
      expect(vi.getTimerCount()).toBe(0)
      socketHandlers.connect()
      expect(socketMock.emit).toHaveBeenCalledTimes(3)
    })

    it('keeps the same snapshot object across identical heartbeats', () => {
      const health = useRecorderHealth()
      health.connect()
      watch(health)
      socketHandlers.settings_status({ revision: '"saved"', sources: { mic: { recording: 'active' } } })
      const first = health.settingsStatus.value
      socketHandlers.settings_status({ revision: '"saved"', sources: { mic: { recording: 'active' } } })
      expect(health.settingsStatus.value).toBe(first)
      socketHandlers.settings_status({ revision: '"saved"', sources: { mic: { recording: 'failed' } } })
      expect(health.settingsStatus.value).not.toBe(first)
    })
  })
})
