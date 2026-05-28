import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading';
import { Calendar, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import type { PasswordRequirement } from './authShared';

/** Center auth cards inside the shared route shell. */
export function AuthPageShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12">
      {children}
    </div>
  );
}

/** Render the branded calendar icon shown at the top of an auth card. */
export function AuthBrandIcon() {
  return (
    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
      <Calendar className="h-6 w-6 text-primary" />
    </div>
  );
}

/** Render the icon and copy at the top of an auth card. */
export function AuthCardHeader({
  description,
  icon = <AuthBrandIcon />,
  title,
}: Readonly<{ description: ReactNode; icon?: ReactNode; title: string }>) {
  return (
    <CardHeader className="space-y-1 text-center">
      {icon}
      <CardTitle className="text-2xl">{title}</CardTitle>
      <CardDescription>{description}</CardDescription>
    </CardHeader>
  );
}

/** Render a full-width submit button with a loading spinner state. */
export function AuthSubmitButton({
  isLoading,
  submitLabel,
  submittingLabel,
}: Readonly<{
  isLoading: boolean;
  submitLabel: string;
  submittingLabel: string;
}>) {
  return (
    <Button type="submit" className="w-full" disabled={isLoading}>
      {isLoading ? (
        <>
          <LoadingSpinner size="sm" className="mr-2" />
          {submittingLabel}
        </>
      ) : (
        submitLabel
      )}
    </Button>
  );
}

/** Render a password input with a show/hide toggle button. */
export function AuthPasswordInput({
  disabled,
  id,
  name,
  onChange,
  onToggleShowPassword,
  showPassword,
  value,
}: Readonly<{
  disabled: boolean;
  id: string;
  name?: string;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onToggleShowPassword: () => void;
  showPassword: boolean;
  value: string;
}>) {
  return (
    <div className="relative">
      <Input
        id={id}
        name={name}
        type={showPassword ? 'text' : 'password'}
        placeholder="••••••••"
        value={value}
        onChange={onChange}
        required
        disabled={disabled}
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
        onClick={onToggleShowPassword}
      >
        {showPassword ? (
          <EyeOff className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Eye className="h-4 w-4 text-muted-foreground" />
        )}
      </Button>
    </div>
  );
}

/** Render the inline password requirement checklist. */
export function PasswordRequirementsChecklist({
  requirements,
}: Readonly<{ requirements: ReadonlyArray<PasswordRequirement> }>) {
  return (
    <div className="space-y-1 pt-2">
      {requirements.map((requirement) => (
        <div
          key={requirement.label}
          className={`flex items-center gap-2 text-xs ${
            requirement.met ? 'text-green-600' : 'text-muted-foreground'
          }`}
        >
          <CheckCircle2
            className={`h-3 w-3 ${requirement.met ? 'text-green-600' : 'text-muted-foreground'}`}
          />
          {requirement.label}
        </div>
      ))}
    </div>
  );
}
