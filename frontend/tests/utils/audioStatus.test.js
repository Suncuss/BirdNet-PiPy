import { describe, it, expect } from 'vitest'
import { sourceAudioStatus, sourceIsChanging, summarizeAudioStatus } from '@/utils/audioStatus'
import { clock24 } from '../helpers/clock'

const mic = { id: 'source_0', label: 'Microphone', enabled: true }
const camera = { id: 'source_1', label: 'Backyard', enabled: true }
const active = { recording: 'active', streaming: 'active' }
const disabled = { recording: 'disabled', streaming: 'disabled' }
const snapshot = (sources, rest = {}) => ({ recording: 'current', streaming: 'current', sources, ...rest })
const summary = (sources, status) => summarizeAudioStatus(sources, status, clock24)

describe('audio status summary', () => {
  it('confirms healthy audio with enabled and disabled sources', () => {
    expect(summary([mic, { ...camera, enabled: false }], snapshot({ source_0: active, source_1: disabled })))
      .toEqual({ state: 'healthy', label: 'Audio Healthy' })
  })

  it('treats legacy sources without an enabled flag as enabled', () => {
    expect(summary([{ id: 'source_0' }], snapshot({ source_0: active })).state).toBe('healthy')
  })

  it.each(['recording', 'streaming'])('names a source with a %s failure even while another connects', (kind) => {
    expect(summary([mic, camera], snapshot({
      source_0: { ...active, [kind]: 'failed' }, source_1: { ...active, streaming: 'connecting' }
    }))).toEqual({ state: 'issue', label: 'Audio Issue — Microphone' })
  })

  it('counts affected sources once when recording and streaming both fail', () => {
    expect(summary([mic, camera], snapshot({
      source_0: { recording: 'failed', streaming: 'failed' }, source_1: { ...active, streaming: 'failed' }
    })).label).toBe('Audio Issues — 2 sources')
  })

  it('does not hide supervisor errors behind publishers still using old settings', () => {
    expect(summary([mic], snapshot({ source_0: active }, { streaming_error: 'Unable to load streaming settings' })).state)
      .toBe('issue')
  })

  it.each(['pending', 'connecting'])('combines %s into updating', state => {
    expect(summary([mic], snapshot({ source_0: { ...active, streaming: state } })))
      .toEqual({ state: 'updating', label: 'Updating Status…' })
  })

  it('waits for removed sources to stop before showing sources disabled', () => {
    expect(summary([], snapshot({}, { streaming: 'pending' })).state).toBe('updating')
    expect(summary([], snapshot({}))).toEqual({ state: 'disabled', label: 'Audio Paused — sources disabled' })
  })

  it('keeps a disabled source updating until both services acknowledge stopping it', () => {
    const source = { ...mic, enabled: false }
    expect(summary([source], snapshot({ source_0: { ...disabled, recording: 'pending' } })).state).toBe('updating')
    expect(summary([source], snapshot({ source_0: disabled })).state).toBe('disabled')
  })

  it('shows quiet hours while the live stream continues, but prioritizes stream failures', () => {
    const pause = { reason: 'quiet_hours', resumes_at: '2026-09-08T06:00' }
    expect(summary([mic], snapshot({ source_0: { ...active, recording: 'paused' } }, { pause })))
      .toEqual({ state: 'paused', label: 'Paused until 06:00' })
    expect(summary([mic], snapshot({ source_0: { recording: 'paused', streaming: 'failed' } }, { pause })).state)
      .toBe('issue')
    // Pause metadata without a paused source must not label an active source paused.
    expect(summary([mic], snapshot({ source_0: active }, { pause })).state).toBe('healthy')
  })

  it.each([
    null,
    snapshot({}),
    snapshot({ source_0: { ...active, recording: 'unknown' } }),
    snapshot({ source_0: { ...active, streaming: 'unknown' } }, { streaming: 'unknown', streaming_error: 'Streaming status unavailable' }),
    snapshot({ source_0: active }, { recording: 'unknown' }),
    snapshot({ source_0: { ...active, streaming: 'unexpected' } }),
    snapshot({ source_0: disabled })
  ])('does not mistake unavailable or inconsistent health for healthy audio (%#)', status => {
    expect(summary([mic], status)).toEqual({ state: 'unknown', label: 'Audio Status Unavailable' })
  })
})

describe('source pill transitions', () => {
  it('pulses only while a source is known to be changing', () => {
    expect(sourceIsChanging({ ...active, recording: 'pending' })).toBe(true)
    expect(sourceIsChanging({ ...active, streaming: 'connecting' })).toBe(true)
    expect(sourceIsChanging({ recording: 'disabled', streaming: 'pending' })).toBe(true)
    for (const status of [active, disabled, { ...active, recording: 'paused' },
      { recording: 'failed', streaming: 'connecting' }, { recording: 'unknown', streaming: 'connecting' }]) {
      expect(sourceIsChanging(status)).toBe(false)
    }
  })

  it('uses unavailable details when a source has no status', () => {
    expect(sourceAudioStatus(null, 'source_0')).toEqual({ recording: 'unknown', streaming: 'unknown' })
  })
})
