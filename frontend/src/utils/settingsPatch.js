const object = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)
export const cloneSettings = (v) => JSON.parse(JSON.stringify(v))

export function changedSettings(base, draft) {
  const patch = {}
  for (const [key, value] of Object.entries(draft)) {
    if (object(value) && object(base?.[key])) {
      const nested = changedSettings(base[key], value)
      if (Object.keys(nested).length) patch[key] = nested
    } else if (JSON.stringify(value) !== JSON.stringify(base?.[key])) {
      patch[key] = cloneSettings(value)
    }
  }
  return patch
}

export function mergeSettings(target, patch) {
  for (const [key, value] of Object.entries(patch)) {
    if (object(value) && object(target[key])) mergeSettings(target[key], value)
    else target[key] = cloneSettings(value)
  }
  return target
}

export function settingsConflict(base, current, patch) {
  return Object.entries(patch).some(([key, value]) => object(value)
    ? settingsConflict(base?.[key], current?.[key], value)
    : JSON.stringify(base?.[key]) !== JSON.stringify(current?.[key]))
}

// A save acknowledges the submitted values; edits made while it was in flight
// remain drafts. Use only the submitted paths, never an entire form response.
export function acknowledgeSettings(draft, baseline, submitted, saved) {
  for (const [key, value] of Object.entries(submitted)) {
    if (object(value)) {
      draft[key] ||= {}
      baseline[key] ||= {}
      acknowledgeSettings(draft[key], baseline[key], value, saved?.[key] || value)
    } else {
      const confirmed = saved?.[key] ?? value
      if (JSON.stringify(draft[key]) === JSON.stringify(value)) draft[key] = cloneSettings(confirmed)
      baseline[key] = cloneSettings(confirmed)
    }
  }
}
