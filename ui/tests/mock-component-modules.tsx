import React from 'react'

type SelectContextValue = {
  onValueChange?: (value: string) => void
  disabled?: boolean
}

type SelectProps = {
  children: React.ReactNode
  onValueChange?: (value: string) => void
  disabled?: boolean
}

type SelectValueProps = {
  placeholder?: string
}

type SelectContentProps = {
  children: React.ReactNode
}

type SelectItemProps = {
  value: string
  children: React.ReactNode
}

type DropdownMenuItemProps = {
  children: React.ReactNode
  onClick?: () => void
  onSelect?: () => void
  disabled?: boolean
}

type CheckboxProps = {
  checked?: boolean
  disabled?: boolean
  onCheckedChange?: (value: boolean) => void
}

type CalendarRange = {
  from?: Date
  to?: Date
}

type CalendarProps = {
  onSelect?: (range: CalendarRange) => void
}

/**
 * Create test doubles for the select primitives used across page-level tests.
 *
 * @returns The mocked select primitives wired for interactive page-level tests.
 */
export function createSelectMockModule() {
  const SelectContext = React.createContext<SelectContextValue>({})

  /** Provide select context state to descendant mock controls. */
  function Select({ children, onValueChange, disabled }: SelectProps) {
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
  function SelectValue({ placeholder }: SelectValueProps) {
    return <span>{placeholder ?? 'value'}</span>
  }

  /** Render the option list container for the select mock. */
  function SelectContent({ children }: SelectContentProps) {
    return <div>{children}</div>
  }

  /** Render one selectable option in the select mock. */
  function SelectItem({ value, children }: SelectItemProps) {
    const context = React.useContext(SelectContext)
    return (
      <button type="button" disabled={context.disabled} onClick={() => context.onValueChange?.(value)}>
        {children}
      </button>
    )
  }

  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem }
}

/** Render the dropdown-menu container used across page-level tests. */
function DropdownMenuMock({ children }: SelectContentProps) {
  return <div>{children}</div>
}

/** Render the dropdown trigger used across page-level tests. */
function DropdownMenuTriggerMock({ children }: SelectContentProps) {
  return React.isValidElement(children) ? children : <span>{children}</span>
}

/** Render the dropdown content wrapper used across page-level tests. */
function DropdownMenuContentMock({ children }: SelectContentProps) {
  return <div>{children}</div>
}

/** Render one actionable dropdown menu item for page-level tests. */
function DropdownMenuItemMock({
  children,
  onClick,
  onSelect,
  disabled,
}: DropdownMenuItemProps) {
  return (
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
  )
}

/** Render a dropdown label container for page-level tests. */
function DropdownMenuLabelMock({ children }: SelectContentProps) {
  return <div>{children}</div>
}

/** Render a dropdown separator for page-level tests. */
function DropdownMenuSeparatorMock() {
  return <hr />
}

/**
 * Create test doubles for the dropdown-menu primitives used in page tests.
 *
 * @returns The mocked dropdown-menu primitives used by page-level tests.
 */
export function createDropdownMenuMockModule() {
  return {
    DropdownMenu: DropdownMenuMock,
    DropdownMenuTrigger: DropdownMenuTriggerMock,
    DropdownMenuContent: DropdownMenuContentMock,
    DropdownMenuItem: DropdownMenuItemMock,
    DropdownMenuLabel: DropdownMenuLabelMock,
    DropdownMenuSeparator: DropdownMenuSeparatorMock,
  }
}

/** Render a checkbox primitive that toggles boolean state in tests. */
function CheckboxMock({
  checked,
  disabled,
  onCheckedChange,
  ...rest
}: CheckboxProps & Omit<React.ComponentProps<'input'>, keyof CheckboxProps>) {
  return (
    <input
      type="checkbox"
      checked={Boolean(checked)}
      disabled={disabled}
      onChange={() => onCheckedChange?.(!checked)}
      {...rest}
    />
  )
}

/**
 * Create a checkbox primitive that toggles boolean state in tests.
 *
 * @returns The mocked checkbox primitive used by page-level tests.
 */
export function createCheckboxMockModule() {
  return {
    Checkbox: CheckboxMock,
  }
}

/** Render a calendar primitive that emits a fixed date range in tests. */
function CalendarMock({ onSelect }: CalendarProps) {
  return (
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
  )
}

/**
 * Create a calendar primitive that emits a fixed date range in tests.
 *
 * @returns The mocked calendar primitive used by page-level tests.
 */
export function createCalendarMockModule() {
  return {
    Calendar: CalendarMock,
  }
}
