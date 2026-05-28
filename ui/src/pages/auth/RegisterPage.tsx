import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import {
  AuthCardHeader,
  AuthPageShell,
  AuthPasswordInput,
  AuthSubmitButton,
  PasswordRequirementsChecklist,
} from './authComponents';
import { describeApiError } from './authShared';

type RegisterTexts = ReturnType<typeof useI18n>['t']['auth']['register'];

type PasswordRequirementState = Readonly<{
  hasLetters: boolean;
  hasMinimumLength: boolean;
  hasNumbers: boolean;
}>;

type RegisterAccessCodeFieldsProps = Readonly<{
  formData: {
    confirmPassword: string;
    password: string;
  };
  handleChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  isLoading: boolean;
  passwordRequirements: ReadonlyArray<{
    label: string;
    met: boolean;
  }>;
  showPassword: boolean;
  texts: RegisterTexts;
  toggleShowPassword: () => void;
}>;

type RegisterFormCardProps = Readonly<{
  formData: {
    confirmPassword: string;
    email: string;
    fullName: string;
    password: string;
  };
  handleChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  passwordRequirements: ReadonlyArray<{
    label: string;
    met: boolean;
  }>;
  showPassword: boolean;
  texts: RegisterTexts;
  toggleShowPassword: () => void;
}>;

/** Build the derived access-code requirement state for the registration form. */
/**
 * Test helper: build password requirement state.
 */
function buildPasswordRequirementState(password: string): PasswordRequirementState {
  return {
    hasLetters: /[a-zA-Z]/.test(password),
    hasMinimumLength: password.length >= 8,
    hasNumbers: /\d/.test(password),
  };
}

/** Render the access-code fields and password requirements on the register page. */
function RegisterAccessCodeFields({
  formData,
  handleChange,
  isLoading,
  passwordRequirements,
  showPassword,
  texts,
  toggleShowPassword,
}: RegisterAccessCodeFieldsProps) {
  // skipcq: JS-0415 - the access-code field groups matching validation hints in one block.
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="password">{texts.accessCodeLabel}</Label>
        <AuthPasswordInput
          disabled={isLoading}
          id="password"
          name="password"
          onChange={handleChange}
          onToggleShowPassword={toggleShowPassword}
          showPassword={showPassword}
          value={formData.password}
        />
        <PasswordRequirementsChecklist requirements={passwordRequirements} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="confirmPassword">{texts.confirmAccessCodeLabel}</Label>
        <Input
          id="confirmPassword"
          name="confirmPassword"
          type={showPassword ? 'text' : 'password'}
          placeholder="••••••••"
          value={formData.confirmPassword}
          onChange={handleChange}
          required
          disabled={isLoading}
        />
        {formData.confirmPassword && formData.password !== formData.confirmPassword && (
          <p className="text-xs text-destructive">{texts.accessCodeMismatchInline}</p>
        )}
      </div>
    </>
  );
}

/** Render the footer prompt that sends existing users back to login. */
function RegisterFooterHint({
  label,
  linkLabel,
}: Readonly<{
  label: string;
  linkLabel: string;
}>) {
  return (
    <p className="text-center text-sm text-muted-foreground">
      {label}{' '}
      <Link to="/login" className="text-primary hover:underline">
        {linkLabel}
      </Link>
    </p>
  );
}

/** Render the profile identity fields at the top of the registration form. */
function RegisterIdentityFields({
  formData,
  handleChange,
  isLoading,
  texts,
}: Readonly<{
  formData: RegisterFormCardProps['formData'];
  handleChange: RegisterFormCardProps['handleChange'];
  isLoading: boolean;
  texts: RegisterTexts;
}>) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="fullName">{texts.fullNameLabel}</Label>
        <Input
          id="fullName"
          name="fullName"
          type="text"
          placeholder={texts.fullNamePlaceholder}
          value={formData.fullName}
          onChange={handleChange}
          disabled={isLoading}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">{texts.emailLabel}</Label>
        <Input
          id="email"
          name="email"
          type="email"
          placeholder={texts.emailPlaceholder}
          value={formData.email}
          onChange={handleChange}
          required
          disabled={isLoading}
        />
      </div>
    </>
  );
}

/** Render the footer actions shown at the bottom of the registration form. */
function RegisterFormFooter({
  isLoading,
  texts,
}: Readonly<{
  isLoading: boolean;
  texts: RegisterTexts;
}>) {
  return (
    <CardFooter className="flex flex-col gap-4">
      <AuthSubmitButton
        isLoading={isLoading}
        submitLabel={texts.submit}
        submittingLabel={texts.submitting}
      />
      <RegisterFooterHint label={texts.haveAccount} linkLabel={texts.loginLink} />
    </CardFooter>
  );
}

/** Render the full registration card while keeping the page shell shallow. */
function RegisterFormCard({
  formData,
  handleChange,
  handleSubmit,
  isLoading,
  passwordRequirements,
  showPassword,
  texts,
  toggleShowPassword,
}: RegisterFormCardProps) {
  return (
    <Card className="w-full max-w-md">
      <AuthCardHeader title={texts.title} description={texts.description} />
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          <RegisterIdentityFields
            formData={formData}
            handleChange={handleChange}
            isLoading={isLoading}
            texts={texts}
          />
          <RegisterAccessCodeFields
            formData={formData}
            handleChange={handleChange}
            isLoading={isLoading}
            passwordRequirements={passwordRequirements}
            showPassword={showPassword}
            texts={texts}
            toggleShowPassword={toggleShowPassword}
          />
        </CardContent>
        <RegisterFormFooter isLoading={isLoading} texts={texts} />
      </form>
    </Card>
  );
}

/** Render the registration form and create a student account. */
export function RegisterPage() {
  const { t } = useI18n();
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const passwordState = buildPasswordRequirementState(formData.password);
  const passwordRequirements = [
    { label: t.auth.register.accessCodeRequirementMin, met: passwordState.hasMinimumLength },
    { label: t.auth.register.accessCodeRequirementLetters, met: passwordState.hasLetters },
    { label: t.auth.register.accessCodeRequirementNumbers, met: passwordState.hasNumbers },
  ];

  /** Update a single field in the registration form state. */
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  /** Validate and submit the registration form. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.password !== formData.confirmPassword) {
      toast({
        title: t.auth.register.accessCodeMismatchTitle,
        description: t.auth.register.accessCodeMismatchDescription,
        variant: 'destructive',
      });
      return;
    }

    if (!passwordRequirements.every((req) => req.met)) {
      toast({
        title: t.auth.register.accessCodeInvalidTitle,
        description: t.auth.register.accessCodeInvalidDescription,
        variant: 'destructive',
      });
      return;
    }

    setIsLoading(true);

    try {
      await register(
        formData.email,
        formData.password,
        formData.confirmPassword,
        formData.fullName || undefined,
      );
      toast({
        title: t.auth.register.successTitle,
        description: t.auth.register.successDescription,
        variant: 'success' as const,
      });
      navigate('/');
    } catch (error) {
      toast({
        title: t.auth.register.errorTitle,
        description: describeApiError(error, t.auth.register.errorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthPageShell>
      <RegisterFormCard
        formData={formData}
        handleChange={handleChange}
        handleSubmit={handleSubmit}
        isLoading={isLoading}
        passwordRequirements={passwordRequirements}
        showPassword={showPassword}
        texts={t.auth.register}
        toggleShowPassword={() => setShowPassword(!showPassword)}
      />
    </AuthPageShell>
  );
}
