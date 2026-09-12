import { pausedLabel } from './recorderStates'

// Matches recording_schedule.enabled_sources(): a source saved before the
// toggle existed has no `enabled` key and is recorded. Reading this as
// truthiness would show "recording is paused" for a station that is in fact
// recording.
export const isSourceEnabled = (source) => source?.enabled !== false

const SOURCE_LABELS = {
  active: 'Active', disabled: 'Disabled', pending: 'Applying changes…',
  connecting: 'Connecting…', paused: 'Paused', failed: 'Failed', unknown: 'Status unavailable'
}

const knownState = (state) => Object.prototype.hasOwnProperty.call(SOURCE_LABELS, state) ? state : 'unknown'

export function sourceAudioStatus(status, id) {
  const source = status?.sources?.[id]
  return { recording: knownState(source?.recording), streaming: knownState(source?.streaming) }
}

export function sourceIsChanging(status) {
  const states = [status.recording, status.streaming]
  return !states.includes('failed') && !states.includes('unknown') &&
    states.some(state => state === 'pending' || state === 'connecting')
}

export function sourceStatusLabel(state) {
  return SOURCE_LABELS[knownState(state)]
}

/** A supervisor error only counts while its heartbeat is fresh; a missing heartbeat is unavailability. */
export function streamingError(status) {
  return status?.streaming === 'unknown' ? '' : (status?.streaming_error || '')
}

/** Summarize an acknowledged settings snapshot; a save alone proves no health. */
export function summarizeAudioStatus(sources, status, formatTime) {
  const unavailable = { state: 'unknown', label: 'Audio Status Unavailable' }
  if (!status) return unavailable

  const rows = sources.map(source => ({ source, ...sourceAudioStatus(status, source.id) }))
  const failed = rows.filter(row => row.recording === 'failed' || row.streaming === 'failed')
  // A fresh supervisor error also matters when publishers retained an older
  // configuration.
  if (failed.length || streamingError(status)) {
    const affected = failed.length ? failed : rows.filter(row => isSourceEnabled(row.source))
    const label = affected.length > 1 ? `Audio Issues — ${affected.length} sources`
      : affected.length ? `Audio Issue — ${affected[0].source.label || affected[0].source.id}` : 'Audio Issue'
    return { state: 'issue', label }
  }

  if (![status.recording, status.streaming].every(state => state === 'current' || state === 'pending') ||
      rows.some(row => row.recording === 'unknown' || row.streaming === 'unknown')) return unavailable

  // These aggregate flags include removed sources which no longer have pills.
  if (status.recording === 'pending' || status.streaming === 'pending' || rows.some(sourceIsChanging)) {
    return { state: 'updating', label: 'Updating Status…' }
  }

  const enabled = rows.filter(row => isSourceEnabled(row.source))
  if (!rows.every(row => isSourceEnabled(row.source)
    ? ['active', 'paused'].includes(row.recording) && row.streaming === 'active'
    : row.recording === 'disabled' && row.streaming === 'disabled')) return unavailable

  if (!enabled.length) return { state: 'disabled', label: 'Audio Paused — sources disabled' }
  if (enabled.some(row => row.recording === 'paused')) {
    return { state: 'paused', label: pausedLabel(status.pause, formatTime) }
  }
  return { state: 'healthy', label: 'Audio Healthy' }
}
