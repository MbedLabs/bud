// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import PoweredByEmbedLabs from '../components/PoweredByEmbedLabs'

afterEach(cleanup)

describe('sidebar attribution', () => {
  it('stays within the expanded sidebar and shows the app version', () => {
    render(<PoweredByEmbedLabs collapsed={false} version="1.0.0" />)

    const container = screen.getByTestId('sidebar-attribution')
    expect(container).toHaveAttribute('data-state', 'expanded')
    expect(container).toHaveClass('w-full', 'max-w-full', 'overflow-hidden')
    expect(container).not.toHaveClass('fixed')
    const link = screen.getByRole('link', { name: 'Powered by EmbedLabs' })
    expect(link).toHaveAttribute('href', 'https://www.embedlabs.net')
    expect(link).toHaveClass('text-lime-200/50')
    expect(screen.getByText('v1.0.0')).toHaveClass('text-lime-200/30')
    expect(screen.queryByText('© 2026')).not.toBeInTheDocument()
  })

  it('places the collapsed copyright attribution outside the sidebar rail', () => {
    render(<PoweredByEmbedLabs collapsed version="1.0.0" />)

    const container = screen.getByTestId('sidebar-attribution')
    expect(container).toHaveAttribute('data-state', 'collapsed')
    expect(container).toHaveClass(
      'fixed',
      'bottom-3',
      'left-[4.25rem]',
      'whitespace-nowrap',
      'text-gray-500',
      'dark:text-white',
    )
    expect(container).not.toHaveClass('w-14')
    expect(
      screen.getByRole('link', { name: 'Powered by EmbedLabs © 2026' }),
    ).toBeInTheDocument()
    expect(container).toHaveTextContent('Powered by EmbedLabs © 2026')
    expect(screen.queryByText('v1.0.0')).not.toBeInTheDocument()
  })
})
