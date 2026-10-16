import { Children, Fragment, isValidElement, useId, useRef, useState, type ReactNode, type SelectHTMLAttributes } from 'react'
import Select from './Select'

/** Text displayed by an option, including nested fragments. */
function optionText(node: ReactNode): string {
  return Children.toArray(node).map((child) => isValidElement<{ children?: ReactNode }>(child) ? optionText(child.props.children) : String(child)).join('')
}

/** Single-value options and disabled states from a select's children. */
function selectOptions(children: ReactNode, disabled = false): Array<{ value: string; label: string; disabled: boolean }> {
  return Children.toArray(children).flatMap((child) => {
    if (!isValidElement<{ children?: ReactNode; value?: string | number; disabled?: boolean; label?: string }>(child)) return []
    if (child.type === Fragment || child.type === 'optgroup') return selectOptions(child.props.children, disabled || !!child.props.disabled)
    if (child.type !== 'option') return []
    const text = optionText(child.props.children).replace(/\s+/g, ' ').trim()
    return [{ value: String(child.props.value ?? text), label: child.props.label ?? text, disabled: disabled || !!child.props.disabled }]
  })
}

/** A themed single selector with native change events and form validation. */
export default function SelectField({ children, value, defaultValue, id, title, className = '', disabled, required, autoFocus, 'aria-label': label, 'aria-labelledby': labelledBy, ...props }: Readonly<SelectHTMLAttributes<HTMLSelectElement>>) {
  const native = useRef<HTMLSelectElement>(null)
  const errorId = useId()
  const [validationError, setValidationError] = useState('')
  const options = selectOptions(children)
  const [uncontrolled, setUncontrolled] = useState(String(defaultValue ?? options[0]?.value ?? ''))
  const selected = String(value ?? uncontrolled)
  const layout = className.split(' ').filter((part) => /^(?:w-|min-w-|max-w-|flex-1$|shrink-|m[trblxy]?-|block$)/.test(part))
  const buttonClass = className.split(' ').filter((part) => !layout.includes(part)).join(' ')
  return <div className={`min-w-0 ${layout.join(' ')}`}>
    <Select id={id} label={label ?? title} labelledBy={labelledBy} title={title} value={selected} options={options} disabled={disabled} required={required} autoFocus={autoFocus} className={buttonClass} invalid={!!validationError} describedBy={validationError ? errorId : props['aria-describedby']}
      onChange={(next) => {
        setValidationError('')
        setUncontrolled(next)
        if (native.current) {
          native.current.value = next
          native.current.dispatchEvent(new Event('change', { bubbles: true }))
        }
      }} />
    <select {...props} ref={native} hidden aria-hidden="true" tabIndex={-1} value={selected} onChange={props.onChange ?? (() => undefined)} disabled={disabled} required={required}
      onInvalid={(event) => { event.preventDefault(); setValidationError(event.currentTarget.validationMessage); event.currentTarget.parentElement?.querySelector('button')?.focus() }}>
      {children}
    </select>
    {validationError && <p id={errorId} role="alert" className="mt-1 text-xs text-destructive">{validationError}</p>}
  </div>
}
