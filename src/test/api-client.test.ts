import { describe, expect, it } from 'vitest'

import { APP_VERSION, api } from '../api/client'

describe('api client', () => {
  it('uses the default API base URL', () => {
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('exposes the app version', () => {
    expect(APP_VERSION).toBe('0.1.0')
  })
})
