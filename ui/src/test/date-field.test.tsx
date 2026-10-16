// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import DateField from '../components/DateField'

afterEach(cleanup)

function dayName(year: number, month: number, day: number) {
  return new Intl.DateTimeFormat(navigator.language, { dateStyle: 'full', calendar: 'gregory' }).format(new Date(year, month - 1, day))
}

function Field({ initial = '2024-02-28', min, max, change = () => undefined }: { initial?: string; min?: string; max?: string; change?: (value: string) => void }) {
  const [value, setValue] = useState(initial)
  return <DateField label="From" value={value} min={min} max={max} onChange={next => { setValue(next); change(next) }} />
}

describe('themed date filter', () => {
  it('selects a leap day as the unchanged ISO date and clears it', () => {
    const change = vi.fn()
    render(<Field change={change} />)
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    fireEvent.click(screen.getByRole('button', { name: dayName(2024, 2, 29) }))
    expect(change).toHaveBeenLastCalledWith('2024-02-29')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('From')).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    expect(change).toHaveBeenLastCalledWith('')
    expect(screen.getByLabelText('From')).toHaveValue('')
  })

  it('keeps date typing and rejects impossible dates without changing the filter', () => {
    const change = vi.fn()
    render(<Field change={change} />)
    const input = screen.getByLabelText('From')
    fireEvent.change(input, { target: { value: '2023-02-29' } })
    fireEvent.blur(input)
    expect(change).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    fireEvent.change(input, { target: { value: '2026-10-14' } })
    expect(change).toHaveBeenLastCalledWith('2026-10-14')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    const formatted = new Intl.DateTimeFormat(navigator.language, { year: 'numeric', month: '2-digit', day: '2-digit', calendar: 'gregory', numberingSystem: 'latn' }).format(new Date(2026, 9, 15))
    fireEvent.change(input, { target: { value: formatted } })
    expect(change).toHaveBeenLastCalledWith('2026-10-15')
  })

  it('moves across a month with the keyboard and closes on Escape without selecting', () => {
    const change = vi.fn()
    render(<Field initial="2024-02-29" change={change} />)
    fireEvent.keyDown(screen.getByLabelText('From'), { key: 'ArrowDown' })
    fireEvent.keyDown(screen.getByRole('button', { name: dayName(2024, 2, 29) }), { key: 'ArrowRight' })
    expect(screen.getByRole('button', { name: dayName(2024, 3, 1) })).toHaveFocus()
    fireEvent.keyDown(screen.getByRole('button', { name: dayName(2024, 3, 1) }), { key: 'Escape' })
    expect(change).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the popup outside clipping containers and disables out-of-range dates', () => {
    const change = vi.fn()
    render(<div style={{ overflow: 'hidden' }}><Field min="2024-02-27" max="2024-02-29" change={change} /></div>)
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    const dialog = screen.getByRole('dialog', { name: 'From calendar' })
    expect(dialog.parentElement).toBe(document.body)
    expect(dialog).toHaveClass('themed-scrollbar')
    expect(screen.getByRole('button', { name: dayName(2024, 2, 26) })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next month' })).toBeDisabled()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(change).not.toHaveBeenCalled()
  })

  it('navigates into a partially allowed month without selecting an out-of-range day', () => {
    const change = vi.fn()
    render(<Field initial="2024-03-05" min="2024-02-27" change={change} />)
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    fireEvent.click(screen.getByRole('button', { name: 'Previous month' }))
    expect(screen.getByRole('button', { name: dayName(2024, 2, 27) })).toHaveFocus()
    expect(screen.getByRole('button', { name: dayName(2024, 2, 26) })).toBeDisabled()
    expect(change).not.toHaveBeenCalled()
    fireEvent.keyDown(screen.getByRole('button', { name: dayName(2024, 2, 27) }), { key: 'Escape' })
    fireEvent.click(screen.getByRole('button', { name: 'Choose date for From' }))
    fireEvent.keyDown(screen.getByRole('button', { name: dayName(2024, 3, 5) }), { key: 'PageUp' })
    expect(screen.getByRole('button', { name: dayName(2024, 2, 27) })).toHaveFocus()
    fireEvent.click(screen.getByRole('button', { name: dayName(2024, 2, 27) }))
    expect(change).toHaveBeenLastCalledWith('2024-02-27')
  })
})
