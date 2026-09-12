import { ref, computed } from 'vue'
import { io } from 'socket.io-client'
import api from '@/services/api'
import { SOCKET_PATH } from '@/services/baseUrl'
import { useAuth } from './useAuth'
import { useDismissible } from './useDismissible'
import { useTimeFormat } from './useTimeFormat'
import {
  RECORDER_STATES,
  pausedLabel as formatPausedLabel,
  pausedTitle as formatPausedTitle
} from '@/utils/recorderStates'
import { RECORDER_DISMISSED_UNTIL_KEY } from '@/utils/storageKeys'

// Module-level state (shared across all components - singleton). This is the
// one owner of recorder broadcasts (the app-wide status pill) and of the
// settings-status snapshots that only the Settings page watches.
const recorderStatus = ref(null)
const settingsStatus = ref(null)
// Only the wait for a watcher's first snapshot is a loading state. A later
// disconnect or silent connection is unavailability, so it must not bring
// the skeleton back.
const settingsStatusLoading = ref(false)
// The API samples settings status only while a page asks for it, so pages
// that do not show it cost the station nothing.
let settingsWatchers = 0
// The API emits a settings-status heartbeat every five seconds. Allow missed
// beats, but never keep confirmed health indefinitely on a silent connection.
const SETTINGS_STATUS_TIMEOUT = 15000
let settingsStatusTimer = null

const clearLiveStatus = () => {
  clearTimeout(settingsStatusTimer)
  settingsStatusTimer = null
  settingsStatusLoading.value = false
  settingsStatus.value = null
  recorderStatus.value = null
  requestRevision += 1
}

const armSettingsStatusTimeout = () => {
  clearTimeout(settingsStatusTimer)
  settingsStatusTimer = setTimeout(clearLiveStatus, SETTINGS_STATUS_TIMEOUT)
}

// Recorder warning is snoozable for 24h.
const dismissal = useDismissible(RECORDER_DISMISSED_UNTIL_KEY, 24 * 60 * 60 * 1000)

// One socket for the whole app, owned here rather than by a view: the
// backend pushes recorder_status on every state change, and a page that
// happens to be mounted must not decide whether the pill stays current.
let socket = null

// Bumped by every live push. A REST reply that was already in flight when one
// landed describes an older state, and adopting it would show stale status
// until the next broadcast (up to a minute later).
let liveRevision = 0
// Orders REST refreshes against each other, and lets disconnect() invalidate a
// request that was started while the user was still authenticated.
let requestRevision = 0

const checkStatus = async () => {
  const requestId = ++requestRevision
  const requestedAt = liveRevision
  try {
    const { data } = await api.get('/recorder/status')
    if (requestId !== requestRevision || liveRevision !== requestedAt) return
    // {} until the recorder has broadcast once — keep the previous value.
    if ('state' in data) recorderStatus.value = data
  } catch {
    // Silent failure — recorder health is non-critical UI
  }
}

/** Subscribe to live status. Idempotent; owner-only (the room is auth-gated). */
const connect = () => {
  if (socket) return
  socket = io({ path: SOCKET_PATH })
  const connection = socket

  // Server-side watch membership ends with the socket, so every (re)connection
  // asks again while a page is watching.
  socket.on('connect', () => {
    if (socket === connection && settingsWatchers > 0) socket.emit('watch_settings_status')
  })

  socket.once('connect_error', (error) => {
    if (socket !== connection) return
    clearLiveStatus()
    // Behind a proxy that blocks websockets, the REST value is all there is.
    console.warn('Recorder status WebSocket connection failed:', error)
    checkStatus()
  })

  socket.on('recorder_status', (status) => {
    if (socket !== connection) return
    liveRevision += 1
    recorderStatus.value = status
  })

  socket.on('settings_status', (status) => {
    if (socket !== connection) return
    settingsStatusLoading.value = false
    // Heartbeats repeat the snapshot; a new object would re-render every consumer.
    const next = status || null
    if (JSON.stringify(next) !== JSON.stringify(settingsStatus.value)) settingsStatus.value = next
    armSettingsStatusTimeout()
  })

  socket.on('disconnect', () => {
    if (socket === connection) clearLiveStatus()
  })

  // A password change evicts every other device: the server closes the owner
  // room and says so. Reconnect rather than reload — the socket
  // re-authenticates on connect, so the owner whose own change triggered this
  // rejoins transparently while an evicted session does not.
  socket.on('session_revoked', () => {
    socket.disconnect()
    socket.connect()
  })
}

/**
 * Ask the API for settings-status snapshots while a page shows them.
 * Returns the matching unwatch; the last unwatch drops the snapshot so a
 * later visit never opens on an old one.
 */
const watchSettingsStatus = () => {
  if (settingsWatchers++ === 0) {
    // A snapshot already held is not a loading state.
    settingsStatusLoading.value = settingsStatus.value === null
    armSettingsStatusTimeout()
    if (socket?.connected) socket.emit('watch_settings_status')
  }
  let active = true
  return () => {
    if (!active) return
    active = false
    if (--settingsWatchers > 0) return
    clearTimeout(settingsStatusTimer)
    settingsStatusTimer = null
    settingsStatusLoading.value = false
    settingsStatus.value = null
    if (socket?.connected) socket.emit('unwatch_settings_status')
  }
}

/** Drop the subscription and the status it produced (logout, app teardown). */
const disconnect = () => {
  clearLiveStatus()
  if (!socket) return
  socket.disconnect()
  socket = null
}

export function useRecorderHealth() {
  const { isAuthenticated } = useAuth()
  const { formatTime } = useTimeFormat()

  const showRecorderWarning = computed(() => {
    const state = recorderStatus.value?.state
    if (state !== RECORDER_STATES.DEGRADED && state !== RECORDER_STATES.STOPPED) return false
    if (!isAuthenticated.value) return false
    return !dismissal.isDismissed()
  })

  // A scheduled pause is not a fault: it gets its own informational
  // indicator and must never raise the recorder warning (which is amber,
  // dismissible, and means something broke).
  const showPausedIndicator = computed(() => {
    if (recorderStatus.value?.state !== RECORDER_STATES.PAUSED) return false
    return !!isAuthenticated.value
  })

  // "Paused until 6:00 AM" (quiet hours) or a plain "Audio Paused", for
  // pauses with no known end. Station-local, in the user's clock format.
  const pausedLabel = computed(() =>
    formatPausedLabel(recorderStatus.value?.pause, formatTime))

  const pausedTitle = computed(() => formatPausedTitle(recorderStatus.value?.pause))

  // Which pause rule is in force (core/recording_schedule.py), so the pill can
  // pick an icon that matches — a moon means night, not "nothing is enabled".
  const pauseReason = computed(() => recorderStatus.value?.pause?.reason ?? null)

  return {
    recorderStatus,
    settingsStatus,
    settingsStatusLoading,
    showRecorderWarning,
    showPausedIndicator,
    pausedLabel,
    pausedTitle,
    pauseReason,
    dismissWarning: dismissal.dismiss,
    checkStatus,
    connect,
    disconnect,
    watchSettingsStatus
  }
}
