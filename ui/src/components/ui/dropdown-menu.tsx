/**
 * Thin wrappers around the Radix UI primitives used across the app.
 * Each named export re-exposes the underlying primitive with project styling.
 */
import React from "react"
import {
  Root,
  Trigger,
  Group,
  Portal,
  Sub,
  RadioGroup,
  SubTrigger,
  SubContent,
  Content as DmContent,
  Item as DmItem,
  CheckboxItem,
  RadioItem,
  Label as DmLabel,
  Separator as DmSeparator,
  ItemIndicator,
} from "@radix-ui/react-dropdown-menu"
import { Check, ChevronRight, Circle } from "lucide-react"

import { cn } from "@/lib/utils"

const DropdownMenu = Root

const DropdownMenuTrigger = Trigger

const DropdownMenuGroup = Group

const DropdownMenuPortal = Portal

const DropdownMenuSub = Sub

const DropdownMenuRadioGroup = RadioGroup

/** Sub-menu trigger with a chevron affordance. */
const DropdownMenuSubTrigger = React.forwardRef<
  React.ElementRef<typeof SubTrigger>,
  React.ComponentPropsWithoutRef<typeof SubTrigger> & {
    inset?: boolean
  }
>(({ className, inset, children, ...props }, ref) => (
  <SubTrigger
    ref={ref}
    className={cn(
      "flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent data-[state=open]:bg-accent [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
      inset && "pl-8",
      className
    )}
    {...props}
  >
    {children}
    <ChevronRight className="ml-auto" />
  </SubTrigger>
))
DropdownMenuSubTrigger.displayName =
  SubTrigger.displayName

/** Sub-menu panel for nested menus. */
const DropdownMenuSubContent = React.forwardRef<
  React.ElementRef<typeof SubContent>,
  React.ComponentPropsWithoutRef<typeof SubContent>
>(({ className, ...props }, ref) => (
  <SubContent
    ref={ref}
    className={cn(
      "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
      className
    )}
    {...props}
  />
))
DropdownMenuSubContent.displayName =
  SubContent.displayName

/** Top-level dropdown-menu panel. */
const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DmContent>,
  React.ComponentPropsWithoutRef<typeof DmContent>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <Portal>
    <DmContent
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className
      )}
      {...props}
    />
  </Portal>
))
DropdownMenuContent.displayName = DmContent.displayName

/** Interactive dropdown-menu row. */
const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DmItem>,
  React.ComponentPropsWithoutRef<typeof DmItem> & {
    inset?: boolean
  }
>(({ className, inset, ...props }, ref) => (
  <DmItem
    ref={ref}
    className={cn(
      "relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&>svg]:size-4 [&>svg]:shrink-0",
      inset && "pl-8",
      className
    )}
    {...props}
  />
))
DropdownMenuItem.displayName = DmItem.displayName

/** Checkbox-state dropdown-menu row. */
const DropdownMenuCheckboxItem = React.forwardRef<
  React.ElementRef<typeof CheckboxItem>,
  React.ComponentPropsWithoutRef<typeof CheckboxItem>
>(({ className, children, checked, ...props }, ref) => (
  <CheckboxItem
    ref={ref}
    className={cn(
      "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    checked={checked}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <ItemIndicator>
        <Check className="h-4 w-4" />
      </ItemIndicator>
    </span>
    {children}
  </CheckboxItem>
))
DropdownMenuCheckboxItem.displayName =
  CheckboxItem.displayName

/** Radio-group dropdown-menu row. */
const DropdownMenuRadioItem = React.forwardRef<
  React.ElementRef<typeof RadioItem>,
  React.ComponentPropsWithoutRef<typeof RadioItem>
>(({ className, children, ...props }, ref) => (
  <RadioItem
    ref={ref}
    className={cn(
      "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <ItemIndicator>
        <Circle className="h-2 w-2 fill-current" />
      </ItemIndicator>
    </span>
    {children}
  </RadioItem>
))
DropdownMenuRadioItem.displayName = RadioItem.displayName

/** Non-interactive dropdown-menu section label. */
const DropdownMenuLabel = React.forwardRef<
  React.ElementRef<typeof DmLabel>,
  React.ComponentPropsWithoutRef<typeof DmLabel> & {
    inset?: boolean
  }
>(({ className, inset, ...props }, ref) => (
  <DmLabel
    ref={ref}
    className={cn(
      "px-2 py-1.5 text-sm font-semibold",
      inset && "pl-8",
      className
    )}
    {...props}
  />
))
DropdownMenuLabel.displayName = DmLabel.displayName

/** Horizontal divider for dropdown-menu groups. */
const DropdownMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DmSeparator>,
  React.ComponentPropsWithoutRef<typeof DmSeparator>
>(({ className, ...props }, ref) => (
  <DmSeparator
    ref={ref}
    className={cn("-mx-1 my-1 h-px bg-muted", className)}
    {...props}
  />
))
DropdownMenuSeparator.displayName = DmSeparator.displayName

/** Right-aligned keyboard-hint text shown at the end of a menu row. */
const DropdownMenuShortcut = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) => {
  return (
    <span
      className={cn("ml-auto text-xs tracking-widest opacity-60", className)}
      {...props}
    />
  )
}
DropdownMenuShortcut.displayName = "DropdownMenuShortcut"

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
}
