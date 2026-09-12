/**
 * Coalesces concurrent callers onto a single in-flight async load.
 *
 * The loader must resolve to a boolean; a falsy result is not retained, so
 * the next ensure() retries. A successful load is cached until reset().
 * Create one instance at module scope so the cached state is shared across
 * all callers of a composable.
 *
 * @returns {{
 *   ensure: (loader: () => Promise<boolean>) => Promise<boolean>,
 *   reset: () => void,
 *   markLoaded: () => void
 * }}
 */
export function createCoalescedLoader() {
  let promise = null

  return {
    /** Run `loader` once; concurrent and subsequent callers share the result. */
    ensure(loader) {
      if (!promise) {
        const pending = loader().then((ok) => {
          // reset() may have started a replacement load while this one ran.
          if (!ok && promise === pending) promise = null
          return ok
        })
        promise = pending
      }
      return promise
    },

    /** Discard the cached result so the next ensure() re-runs the loader. */
    reset() {
      promise = null
    },

    /** Mark as already loaded — a later ensure() will skip the loader. */
    markLoaded() {
      if (!promise) promise = Promise.resolve(true)
    }
  }
}
