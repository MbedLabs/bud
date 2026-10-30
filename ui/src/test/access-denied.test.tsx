// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

const AccessDenied = (await import('../components/AccessDenied')).default
const { isAccessDenied, isNotFound } = await import('../lib/accessDenied')

afterEach(cleanup)

describe('Access denied page', () => {
  it('names the resource and offers no request', () => {
    render(<AccessDenied what="this test run" />)
    expect(screen.getByText("You don't have access to this test run")).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('treats only 403 as access denied and only 404 as not found', () => {
    const axiosError = (status: number) => ({ isAxiosError: true, response: { status } })
    expect(isAccessDenied(axiosError(403))).toBe(true)
    expect(isAccessDenied(axiosError(404))).toBe(false)
    expect(isAccessDenied(axiosError(500))).toBe(false)
    expect(isAccessDenied(new Error('x'))).toBe(false)
    expect(isNotFound(axiosError(404))).toBe(true)
    expect(isNotFound(axiosError(403))).toBe(false)
    expect(isNotFound(new Error('x'))).toBe(false)
  })
})
