import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
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
} from './authComponents';
import { describeApiError } from './authShared';

type LoginTexts = ReturnType<typeof useI18n>['t']['auth']['login'];

type LoginAccessCodeFieldProps = Readonly<{
  isLoading: boolean;
  password: string;
  setPassword: (value: string) => void;
  showPassword: boolean;
  texts: LoginTexts;
  toggleShowPassword: () => void;
}>;

type LoginFormCardProps = Readonly<{
  email: string;
  isLoading: boolean;
  onEmailChange: (value: string) => void;
  onSubmit: (event: React.FormEvent) => void;
  password: string;
  setPassword: (value: string) => void;
  showPassword: boolean;
  texts: LoginTexts;
  toggleShowPassword: () => void;
}>;

/** Render the access-code field used on the login screen. */
function LoginAccessCodeField({
  isLoading,
  password,
  setPassword,
  showPassword,
  texts,
  toggleShowPassword,
}: LoginAccessCodeFieldProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label htmlFor="password">{texts.accessCodeLabel}</Label>
        <Link to="/forgot-password" className="text-sm text-primary hover:underline">
          {texts.forgotAccessCode}
        </Link>
      </div>
      <AuthPasswordInput
        disabled={isLoading}
        id="password"
        onChange={(e) => setPassword(e.target.value)}
        onToggleShowPassword={toggleShowPassword}
        showPassword={showPassword}
        value={password}
      />
    </div>
  );
}

/** Render the footer prompt that links new users to registration. */
function LoginFooterHint({
  label,
  linkLabel,
}: Readonly<{
  label: string;
  linkLabel: string;
}>) {
  return (
    <p className="text-center text-sm text-muted-foreground">
      {label}{' '}
      <Link to="/register" className="text-primary hover:underline">
        {linkLabel}
      </Link>
    </p>
  );
}

/** Render the email field shown at the top of the login form. */
function LoginEmailField({
  email,
  isLoading,
  onEmailChange,
  texts,
}: Readonly<{
  email: string;
  isLoading: boolean;
  onEmailChange: (value: string) => void;
  texts: LoginTexts;
}>) {
  return (
    <div className="space-y-2">
      <Label htmlFor="email">{texts.emailLabel}</Label>
      <Input
        id="email"
        type="email"
        placeholder={texts.emailPlaceholder}
        value={email}
        onChange={(event) => onEmailChange(event.target.value)}
        required
        disabled={isLoading}
      />
    </div>
  );
}

/** Render the footer section for the login form. */
function LoginFormFooter({
  isLoading,
  texts,
}: Readonly<{
  isLoading: boolean;
  texts: LoginTexts;
}>) {
  return (
    <CardFooter className="flex flex-col gap-4">
      <AuthSubmitButton
        isLoading={isLoading}
        submitLabel={texts.submit}
        submittingLabel={texts.submitting}
      />
      <LoginFooterHint label={texts.noAccount} linkLabel={texts.registerLink} />
    </CardFooter>
  );
}

/** Render the full login card while keeping the page shell shallow. */
function LoginFormCard({
  email,
  isLoading,
  onEmailChange,
  onSubmit,
  password,
  setPassword,
  showPassword,
  texts,
  toggleShowPassword,
}: LoginFormCardProps) {
  return (
    <Card className="w-full max-w-md">
      <AuthCardHeader title={texts.title} description={texts.description} />
      <form onSubmit={onSubmit}>
        <CardContent className="space-y-4">
          <LoginEmailField
            email={email}
            isLoading={isLoading}
            onEmailChange={onEmailChange}
            texts={texts}
          />
          <LoginAccessCodeField
            isLoading={isLoading}
            password={password}
            setPassword={setPassword}
            showPassword={showPassword}
            texts={texts}
            toggleShowPassword={toggleShowPassword}
          />
        </CardContent>
        <LoginFormFooter isLoading={isLoading} texts={texts} />
      </form>
    </Card>
  );
}

/** Render the login form and handle auth submission side effects. */
export function LoginPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  /** Submit the login credentials and route the user back to the requested page. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await login(email, password);
      toast({
        title: t.auth.login.successTitle,
        description: t.auth.login.successDescription,
        variant: 'success' as const,
      });
      navigate(from, { replace: true });
    } catch (error) {
      toast({
        title: t.auth.login.errorTitle,
        description: describeApiError(error, t.auth.login.errorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthPageShell>
      <LoginFormCard
        email={email}
        isLoading={isLoading}
        onEmailChange={setEmail}
        onSubmit={handleSubmit}
        password={password}
        setPassword={setPassword}
        showPassword={showPassword}
        texts={t.auth.login}
        toggleShowPassword={() => setShowPassword(!showPassword)}
      />
    </AuthPageShell>
  );
}
