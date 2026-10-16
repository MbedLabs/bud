// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AccessModal } from '../components/AccessTable'

afterEach(cleanup)

it('closes an Access dialog once when Escape is pressed on a child control', () => {
  const onClose = vi.fn()
  render(<AccessModal title="View policy" onClose={onClose}><input aria-label="Policy name" /></AccessModal>)
  fireEvent.keyDown(screen.getByLabelText('Policy name'), { key: 'Escape' })
  expect(onClose).toHaveBeenCalledTimes(1)
})

it('keeps an Access dialog open for other keys and clicks inside it', () => {
  const onClose = vi.fn()
  render(<AccessModal title="View policy" onClose={onClose}><input aria-label="Policy name" /></AccessModal>)
  fireEvent.keyDown(screen.getByLabelText('Policy name'), { key: 'Enter' })
  fireEvent.click(screen.getByLabelText('Policy name'))
  expect(onClose).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Close View policy backdrop' }))
  expect(onClose).toHaveBeenCalledTimes(1)
})
