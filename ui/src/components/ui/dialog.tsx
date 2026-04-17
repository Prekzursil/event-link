/**
 * Thin wrappers around the Radix UI primitives used across the app.
 * Each named export re-exposes the underlying primitive with project styling.
 */
import React from "react"
import {
  Root,
  Trigger,
  Portal,
  Close,
  Overlay,
  Content as DialogPrimitiveContent,
  Title as DialogPrimitiveTitle,
  Description as DialogPrimitiveDescription,
} from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

const Dialog = Root

const DialogTrigger = Trigger

const DialogPortal = Portal

const DialogClose = Close

/** Dimmed backdrop rendered behind the dialog surface. */
const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof Overlay>,
  React.ComponentPropsWithoutRef<typeof Overlay>
>(({ className, ...props }, ref) => (
  <Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
))
DialogOverlay.displayName = Overlay.displayName

/** Modal content surface with the built-in close button. */
const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitiveContent>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitiveContent>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitiveContent
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        className
      )}
      {...props}
    >
      {children}
      <Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </Close>
    </DialogPrimitiveContent>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitiveContent.displayName

const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col space-y-1.5 text-center sm:text-left",
      className
    )}
    {...props}
  />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
      className
    )}
    {...props}
  />
)
DialogFooter.displayName = "DialogFooter"

/** Accessible dialog heading. */
const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitiveTitle>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitiveTitle>
>(({ className, ...props }, ref) => (
  <DialogPrimitiveTitle
    ref={ref}
    className={cn(
      "text-lg font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
DialogTitle.displayName = DialogPrimitiveTitle.displayName

/** Accessible dialog description. */
const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitiveDescription>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitiveDescription>
>(({ className, ...props }, ref) => (
  <DialogPrimitiveDescription
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
DialogDescription.displayName = DialogPrimitiveDescription.displayName

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
