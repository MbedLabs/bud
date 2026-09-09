// @vitest-environment jsdom
/** The "..." menu that carries a row's actions. */
import { Pencil, Trash2 } from 'lucide-react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import RowMenu from '../components/RowMenu'

function renderMenu(onRename = vi.fn(), onRemove = vi.fn()) {
  render(
    <RowMenu
      label="Actions for bench-a"
      actions={[
        { label: 'Rename', icon: Pencil, onSelect: onRename },
        { label: 'Remove', icon: Trash2, onSelect: onRemove, destructive: true },
      ]}
    />,
  )
  return { onRename, onRemove }
}

afterEach(cleanup)

describe('a row menu', () => {
  it('keeps its actions closed until asked', () => {
    renderMenu()

    expect(screen.queryByRole('menu')).toBeNull()
    expect(screen.getByRole('button', { name: 'Actions for bench-a' }).getAttribute('aria-expanded')).toBe('false')
  })

  it('opens on the trigger and runs the action chosen', () => {
    const { onRename, onRemove } = renderMenu()

    fireEvent.click(screen.getByRole('button', { name: 'Actions for bench-a' }))
    expect(screen.getByRole('menu')).toBeTruthy()

    fireEvent.click(screen.getByRole('menuitem', { name: 'Rename' }))

    expect(onRename).toHaveBeenCalledOnce()
    expect(onRemove).not.toHaveBeenCalled()
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('closes on Escape without running anything', async () => {
    const { onRename, onRemove } = renderMenu()
    fireEvent.click(screen.getByRole('button', { name: 'Actions for bench-a' }))

    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
    expect(onRename).not.toHaveBeenCalled()
    expect(onRemove).not.toHaveBeenCalled()
  })

  it('closes when the click lands outside it', async () => {
    renderMenu()
    fireEvent.click(screen.getByRole('button', { name: 'Actions for bench-a' }))

    fireEvent.mouseDown(document.body)

    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })

  it('does not navigate the card it sits on', () => {
    const onNavigate = vi.fn()
    render(
      <a href="/runs" onClick={onNavigate}>
        <RowMenu
          label="Actions for bench-b"
          actions={[{ label: 'Remove', icon: Trash2, onSelect: vi.fn(), destructive: true }]}
        />
      </a>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Actions for bench-b' }))

    expect(onNavigate).not.toHaveBeenCalled()
    expect(screen.getByRole('menu')).toBeTruthy()
  })
})
