import { fireEvent, screen } from '@testing-library/react'

/** Select an actual themed option by its stored value. */
export function selectValue(picker: HTMLElement, value: string) {
  fireEvent.click(picker)
  const option = screen.getAllByRole('option').find((item) => item.getAttribute('data-value') === value)
  if (!option) throw new Error(`No selectable option for ${value}`)
  fireEvent.click(option)
}
