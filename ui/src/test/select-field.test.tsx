// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState, type ChangeEvent } from 'react'
import SelectField from '../components/SelectField'

afterEach(cleanup)

function FormPicker() {
  const [value, setValue] = useState('')
  return <form aria-label="Example form"><label>Project<SelectField name="project_id" value={value} onChange={(event) => setValue(event.target.value)} required>
    <option value="">Select project</option><option value={42}>Example project</option>
  </SelectField></label></form>
}

describe('themed field selectors', () => {
  it('preserves numeric option values, native callbacks and required form validation', () => {
    render(<FormPicker />)
    const form = screen.getByRole('form') as HTMLFormElement
    const picker = screen.getByRole('combobox', { name: 'Project' })
    act(() => { expect(form.checkValidity()).toBe(false) })
    expect(picker).toHaveFocus()
    expect(picker).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).not.toHaveTextContent(/^$/)
    fireEvent.click(picker)
    fireEvent.click(screen.getByRole('option', { name: 'Example project' }))
    expect(picker).toHaveTextContent('Example project')
    expect(form.checkValidity()).toBe(true)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(new FormData(form).get('project_id')).toBe('42')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('uses a single named combobox and preselects the current option', () => {
    render(<label htmlFor="events">Events</label>)
    render(<SelectField id="events" aria-label="Events" value="auth." onChange={() => undefined}>
      <option value="">All events</option><option value="auth.">Authentication</option>
    </SelectField>)
    expect(screen.getAllByLabelText('Events')).toHaveLength(1)
    fireEvent.click(screen.getByRole('combobox', { name: 'Events' }))
    expect(screen.getByRole('option', { name: 'Authentication' })).toHaveAttribute('aria-selected', 'true')
  })

  it('skips disabled options with keyboard navigation and closes without changes on Escape', () => {
    const change = vi.fn((event: ChangeEvent<HTMLSelectElement>) => event.target.value)
    render(<SelectField aria-label="Choice" value="first" onChange={change}>
      <option value="first">First</option><option value="blocked" disabled>Blocked</option><option value="last">Last</option>
    </SelectField>)
    const picker = screen.getByRole('combobox', { name: 'Choice' })
    fireEvent.keyDown(picker, { key: 'ArrowDown' })
    fireEvent.keyDown(picker, { key: 'Enter' })
    expect(change).toHaveBeenCalledTimes(1)
    expect(change.mock.results[0].value).toBe('last')
    fireEvent.click(picker)
    fireEvent.keyDown(picker, { key: 'Escape' })
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(change).toHaveBeenCalledTimes(1)
  })

  it('supports implicit values, fragments, uncontrolled selection and type-ahead', () => {
    render(<SelectField aria-label="Kind" defaultValue="Release"><><option>Milestone</option><option>Release</option></><option>Review</option></SelectField>)
    const picker = screen.getByRole('combobox', { name: 'Kind' })
    expect(picker).toHaveTextContent('Release')
    fireEvent.keyDown(picker, { key: 'm' })
    fireEvent.keyDown(picker, { key: 'Enter' })
    expect(picker).toHaveTextContent('Milestone')
    fireEvent.keyDown(picker, { key: 'End' })
    fireEvent.keyDown(picker, { key: 'Enter' })
    expect(picker).toHaveTextContent('Review')
  })

  it('keeps menus outside clipping containers and within a narrow viewport', () => {
    const width = window.innerWidth
    const height = window.innerHeight
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 320 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 500 })
    render(<div style={{ overflow: 'hidden' }}><SelectField aria-label="Suite" value="long"><option value="long">A long suite name that must remain fully readable</option></SelectField></div>)
    const picker = screen.getByRole('combobox', { name: 'Suite' })
    vi.spyOn(picker, 'getBoundingClientRect').mockReturnValue({ left: 250, right: 310, top: 450, bottom: 490, width: 60, height: 40, x: 250, y: 450, toJSON: () => ({}) })
    fireEvent.click(picker)
    const menu = screen.getByRole('listbox')
    expect(menu.parentElement).toBe(document.body)
    expect(parseFloat(menu.style.left) + parseFloat(menu.style.width)).toBeLessThanOrEqual(312)
    expect(parseFloat(menu.style.bottom)).toBe(54)
    expect(screen.getByRole('option')).toHaveTextContent('A long suite name that must remain fully readable')
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: height })
  })

  it('does not open disabled or empty selectors', () => {
    render(<><SelectField aria-label="Disabled" disabled><option value="one">One</option></SelectField><SelectField aria-label="Empty" /></>)
    fireEvent.click(screen.getByRole('combobox', { name: 'Disabled' }))
    fireEvent.keyDown(screen.getByRole('combobox', { name: 'Empty' }), { key: 'ArrowDown' })
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})
