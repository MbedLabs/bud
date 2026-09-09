import { describe, expect, it } from 'vitest'

import packageJson from '../../package.json'
import { APP_VERSION, api } from '../api/client'

describe('api client', () => {
  it('uses the default API base URL', () => {
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('exposes the packaged version, whatever it currently is', () => {
    expect(APP_VERSION).toBe(packageJson.version)
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+/)
  })
})
