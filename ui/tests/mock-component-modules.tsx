import React from 'react'

type SelectContextValue = {
  onValueChange?: (value: string) => void
  disabled?: boolean
}

export function createSelectMockModule() {
  const SelectContext = React.createContext<SelectContextValue>({})

  const Select = ({
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

  const SelectTrigger = ({ children, ...props }: React.ComponentProps<'button'>) => (
    <button type="button" {...props}>
      {children}
    </button>
  )

  const SelectValue = ({ placeholder }: { placeholder?: string }) => <span>{placeholder ?? 'value'}</span>

  const SelectContent = ({ children }: { children: React.ReactNode }) => <div>{children}</div>

  const SelectItem = ({ value, children }: { value: string; children: React.ReactNode }) => {
    const context = React.useContext(SelectContext)
    return (
      <button type="button" disabled={context.disabled} onClick={() => context.onValueChange?.(value)}>
        {children}
      </button>
    )
  }

  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem }
}

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
