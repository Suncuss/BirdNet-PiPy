import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import StreamSourceModal from '@/components/StreamSourceModal.vue'

const streamPost = vi.hoisted(() => vi.fn())
vi.mock('@/services/api', () => ({ createLongRequest: () => ({ post: streamPost }) }))
const copyText = vi.hoisted(() => vi.fn().mockResolvedValue(true))
vi.mock('@/utils/clipboard', () => ({ copyText }))
enableAutoUnmount(afterEach)
beforeEach(() => { streamPost.mockReset().mockResolvedValue({ data: { success: true } }) })
afterEach(() => { vi.clearAllMocks(); document.body.style.overflow = ''; document.body.innerHTML = '' })

const mic = { id: 'source_0', type: 'pulseaudio', label: 'Mic', enabled: true }
const mountEditor = (props = {}) => mount(StreamSourceModal, { attachTo: document.body, props: { source: mic, ...props } })
const confirmation = wrapper => wrapper.findComponent({ name: 'UnsavedChangesModal' })
const action = (wrapper, text) => wrapper.findAll('button').find(button => button.text() === text)
const clickToggle = async (wrapper) => {
  // Native activation inside a real form catches accidental submit buttons;
  // emitting update:modelValue directly cannot reproduce that browser bug.
  wrapper.get('[role="switch"]').element.click()
  await flushPromises()
}
const dismiss = async (wrapper, method = 'close') => {
  if (method === 'close') await wrapper.get('button[title="Close"]').trigger('click')
  else if (method === 'backdrop') await wrapper.get('.bg-black').trigger('click')
  else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
  await flushPromises()
}

describe('source drafts and dismissal', () => {
  it.each([true, false])('waits for Save when toggling a source initially enabled=%s', async (enabled) => {
    const source = { ...mic, enabled }
    const wrapper = mountEditor({ source })
    await clickToggle(wrapper)
    expect(wrapper.get('[role="switch"]').attributes('aria-checked')).toBe(String(!enabled))
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(source.enabled).toBe(enabled)
    action(wrapper, 'Save').element.click()
    await flushPromises()
    expect(wrapper.emitted('save')).toEqual([[{ id: mic.id, updates: { label: mic.label, enabled: !enabled } }]])
    expect(streamPost).not.toHaveBeenCalled()
  })

  it.each(['close', 'backdrop', 'escape'])('confirms unsaved toggle changes on %s; cancel keeps edits and discard closes', async (method) => {
    const wrapper = mountEditor()
    await clickToggle(wrapper)
    await dismiss(wrapper, method)
    expect(confirmation(wrapper).exists()).toBe(true)
    expect(wrapper.emitted('close')).toBeUndefined()

    // Escape dismisses only the top confirmation, preserving the editor.
    await dismiss(confirmation(wrapper), 'escape')
    expect(confirmation(wrapper).exists()).toBe(false)
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(wrapper.vm.enabled).toBe(false)
    expect(document.body.style.overflow).toBe('hidden')

    await dismiss(wrapper, method)
    await action(confirmation(wrapper), 'Discard').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(mic.enabled).toBe(true)
  })

  it.each([false, true])('closes without confirmation when no changes remain (toggle reverted: %s)', async (reverted) => {
    const wrapper = mountEditor()
    if (reverted) {
      await clickToggle(wrapper)
      await clickToggle(wrapper)
    }
    await dismiss(wrapper)
    expect(confirmation(wrapper).exists()).toBe(false)
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  it.each(['label', 'url', 'type'])('also protects unsaved %s edits', async (field) => {
    const wrapper = mountEditor({ source: field === 'type' ? null : {
      id: 'source_1', type: 'rtsp', label: 'Camera', url: 'rtsp://old/audio', enabled: true
    } })
    if (field === 'type') await action(wrapper, 'Microphone').trigger('click')
    else await wrapper.get(`#stream-${field}`).setValue(field === 'label' ? 'Renamed' : 'rtsp://new/audio')
    await dismiss(wrapper)
    expect(confirmation(wrapper).exists()).toBe(true)
  })

  it('uses the same Save path from the confirmation and waits for the parent to close after persistence', async () => {
    const wrapper = mountEditor()
    await clickToggle(wrapper)
    await dismiss(wrapper)
    await action(confirmation(wrapper), 'Save').trigger('click')
    expect(confirmation(wrapper).exists()).toBe(false)
    expect(wrapper.emitted('save')).toEqual([[{ id: mic.id, updates: { label: mic.label, enabled: false } }]])
    expect(wrapper.emitted('close')).toBeUndefined()
    await wrapper.setProps({ saving: true })
    await dismiss(wrapper, 'escape')
    await dismiss(wrapper, 'backdrop')
    expect(confirmation(wrapper).exists()).toBe(false)
    expect(wrapper.get('fieldset').element.disabled).toBe(true)
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('returns to validation errors when Save is chosen from the confirmation', async () => {
    const wrapper = mountEditor({ source: { id: 'camera', type: 'rtsp', url: 'rtsp://old/audio', label: 'Camera' } })
    await wrapper.get('#stream-url').setValue('http://invalid/audio')
    await dismiss(wrapper)
    await action(confirmation(wrapper), 'Save').trigger('click')
    expect(confirmation(wrapper).exists()).toBe(false)
    expect(wrapper.text()).toContain('Must start with rtsp:// or rtsps://')
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(streamPost).not.toHaveBeenCalled()
  })

  it('keeps the normal probe and Save anyway flow after confirmation without duplicate submissions', async () => {
    const wrapper = mountEditor({ source: { id: 'camera', type: 'rtsp', url: 'rtsp://old/audio', label: 'Camera', enabled: true } })
    let finishProbe
    streamPost.mockImplementation(() => new Promise(resolve => { finishProbe = resolve }))
    await wrapper.get('#stream-url').setValue('rtsp://new/audio')
    await dismiss(wrapper)
    await action(confirmation(wrapper), 'Save').trigger('click')
    expect(wrapper.get('fieldset').element.disabled).toBe(true)
    await wrapper.get('form').trigger('submit')
    await dismiss(wrapper, 'escape')
    expect(streamPost).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(confirmation(wrapper).exists()).toBe(false)
    finishProbe({ data: { success: false, message: 'Camera offline' } })
    await flushPromises()
    expect(wrapper.text()).toContain('Camera offline')
    expect(wrapper.get('fieldset').element.disabled).toBe(false)
    await action(wrapper, 'Save anyway').trigger('click')
    expect(wrapper.emitted('save')).toEqual([[{
      id: 'camera', updates: { label: 'Camera', url: 'rtsp://new/audio', enabled: true }
    }]])
  })
})

describe('source audio details', () => {
  it('shows separate live status without changing the editing draft', async () => {
    const wrapper = mountEditor({ audioStatus: { recording: 'active', streaming: 'connecting' } })
    await wrapper.find('#stream-label').setValue('New label')
    await wrapper.findComponent({ name: 'ToggleSwitch' }).vm.$emit('update:modelValue', false)
    await wrapper.setProps({ audioStatus: { recording: 'active', streaming: 'failed' } })

    expect(wrapper.findAll('[data-testid="source-audio-details"] dd').map(row => row.text()))

      .toEqual(['Active', 'Failed'])
    expect(wrapper.find('#stream-label').element.value).toBe('New label')
    expect(wrapper.vm.enabled).toBe(false)
    expect(wrapper.text()).not.toContain('This source is being recorded')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('save')[0]).toEqual([{ id: mic.id, updates: { label: 'New label', enabled: false } }])
  })

  it('shows unavailable status explicitly rather than inferring health from enabled', () => {
    const wrapper = mountEditor()
    expect(wrapper.findAll('dd').map(node => node.text())).toEqual(['Status unavailable', 'Status unavailable'])
  })

  it('uses placeholders while initial status loads without blocking source edits', async () => {
    const wrapper = mountEditor({ statusLoading: true })
    expect(wrapper.get('dl').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('[data-testid="source-audio-details"]').text()).not.toContain('Status unavailable')
    expect(wrapper.get('fieldset').element.disabled).toBe(false)
    await wrapper.find('#stream-label').setValue('Edited while loading')
    await wrapper.setProps({ statusLoading: false, audioStatus: { recording: 'active', streaming: 'failed' } })
    expect(wrapper.findAll('dd').map(node => node.text())).toEqual(['Active', 'Failed'])
    expect(wrapper.find('#stream-label').element.value).toBe('Edited while loading')
  })

  it('keeps error details and copying available in the editor', async () => {
    const wrapper = mountEditor({
      audioStatus: { recording: 'failed', streaming: 'failed' },
      recordingError: 'Device not found', streamingError: 'Unable to load streaming settings'
    })
    expect(wrapper.get('details').text()).toContain('Recording: Device not found')
    expect(wrapper.get('details').text()).toContain('Live stream: Unable to load streaming settings')
    await wrapper.get('details button').trigger('click')
    expect(copyText).toHaveBeenCalledWith('Recording: Device not found\nLive stream: Unable to load streaming settings')
    expect(wrapper.get('details button').text()).toBe('Copied')
  })

  it('does not show runtime details for a source that has not been added', () => {
    const wrapper = mount(StreamSourceModal)
    expect(wrapper.find('[data-testid="source-audio-details"]').exists()).toBe(false)
  })
})
