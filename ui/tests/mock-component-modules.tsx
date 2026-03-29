import React from 'react'

type SelectContextValue = {
  onValueChange?: (value: string) => void
  disabled?: boolean
}

/** Create test doubles for the select primitives used across page-level tests. */
export function createSelectMockModule() {
  const SelectContext = React.createContext<SelectContextValue>({})

  /** Provide select context state to descendant mock controls. */
  function Select({
    children,
    onValueChange,
    disabled,
  }: {
    children: React.ReactNode
    onValueChange?: (value: string) => void
    disabled?: boolean
  }) => {
    const selectContextValue = React.useMemo(
      () => ({ onValueChange, disabled }),
      [disabled, onValueChange],
    )

    return <SelectContext.Provider value={selectContextValue}>{children}</SelectContext.Provider>
  }

  /** Render the interactive trigger button for the select mock. */
  function SelectTrigger({ children, ...props }: React.ComponentProps<'button'>) {
    return (
      <button type="button" {...props}>
        {children}
      </button>
    )
  }

  /** Render the current value or placeholder for the select mock. */
  function SelectValue({ placeholder }: { placeholder?: string }) {
    return <span>{placeholder ?? 'value'}</span>
  }

  /** Render the option list container for the select mock. */
  function SelectContent({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>
  }

  /** Render one selectable option in the select mock. */
  function SelectItem({ value, children }: { value: string; children: React.ReactNode }) {
    const context = React.useContext(SelectContext)
    return (
      <button type="button" disabled={context.disabled} onClick={() => context.onValueChange?.(value)}>
        {children}
      </button>
    )
  }

  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem }
}

/** Create test doubles for the dropdown-menu primitives used in page tests. */
export function createDropdownMenuMockModule() {
  return {
    DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => children,
    DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({
      children,
      onClick,
      onSelect,
      disabled,
    }: {
      children: React.ReactNode
      onClick?: () => void
      onSelect?: () => void
      disabled?: boolean
    }) => (
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          onSelect?.()
          onClick?.()
        }}
      >
        {children}
      </button>
    ),
    DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DropdownMenuSeparator: () => <hr />,
  }
}

/** Create a checkbox primitive that toggles boolean state in tests. */
export function createCheckboxMockModule() {
  return {
    Checkbox: ({
      checked,
      disabled,
      onCheckedChange,
      ...rest
    }: {
      checked?: boolean
      disabled?: boolean
      onCheckedChange?: (value: boolean) => void
    }) => (
      <input
        type="checkbox"
        checked={Boolean(checked)}
        disabled={disabled}
        onChange={() => onCheckedChange?.(!checked)}
        {...rest}
      />
    ),
  }
}

/** Create a calendar primitive that emits a fixed date range in tests. */
export function createCalendarMockModule() {
  return {
    Calendar: ({ onSelect }: { onSelect?: (range: { from?: Date; to?: Date }) => void }) => (
      <div>
        <button
          type="button"
          onClick={() =>
            onSelect?.({
              from: new Date('2026-03-10T00:00:00Z'),
              to: new Date('2026-03-11T00:00:00Z'),
            })
          }
        >
          Pick range
        </button>
        <button type="button" onClick={() => onSelect?.({})}>
          Clear range
        </button>
      </div>
    ),
  }
}
