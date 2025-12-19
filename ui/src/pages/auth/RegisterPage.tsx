import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { LoadingSpinner } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { Calendar, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import type { AxiosError } from 'axios';
import { useI18n } from '@/contexts/LanguageContext';

interface ApiError {
  detail?: string;
  error?: {
    message?: string;
  };
}

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

  const passwordRequirements = [
    { label: t.auth.register.passwordRequirementMin, met: formData.password.length >= 8 },
    { label: t.auth.register.passwordRequirementLetters, met: /[a-zA-Z]/.test(formData.password) },
    { label: t.auth.register.passwordRequirementNumbers, met: /\d/.test(formData.password) },
  ];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.password !== formData.confirmPassword) {
      toast({
        title: t.auth.register.passwordMismatchTitle,
        description: t.auth.register.passwordMismatchDescription,
        variant: 'destructive',
      });
      return;
    }

    if (!passwordRequirements.every((req) => req.met)) {
      toast({
        title: t.auth.register.passwordInvalidTitle,
        description: t.auth.register.passwordInvalidDescription,
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
        formData.fullName || undefined
      );
      toast({
        title: t.auth.register.successTitle,
        description: t.auth.register.successDescription,
        variant: 'success' as const,
      });
      navigate('/');
    } catch (error) {
      const axiosError = error as AxiosError<ApiError>;
      toast({
        title: t.auth.register.errorTitle,
        description:
          axiosError.response?.data?.detail ||
          axiosError.response?.data?.error?.message ||
          t.auth.register.errorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Calendar className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">{t.auth.register.title}</CardTitle>
          <CardDescription>
            {t.auth.register.description}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="fullName">{t.auth.register.fullNameLabel}</Label>
              <Input
                id="fullName"
                name="fullName"
                type="text"
                placeholder={t.auth.register.fullNamePlaceholder}
                value={formData.fullName}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">{t.auth.register.emailLabel}</Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder={t.auth.register.emailPlaceholder}
                value={formData.email}
                onChange={handleChange}
                required
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t.auth.register.passwordLabel}</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  disabled={isLoading}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <Eye className="h-4 w-4 text-muted-foreground" />
                  )}
                </Button>
              </div>
              {/* Password Requirements */}
              <div className="space-y-1 pt-2">
                {passwordRequirements.map((req, index) => (
                  <div
                    key={index}
                    className={`flex items-center gap-2 text-xs ${
                      req.met ? 'text-green-600' : 'text-muted-foreground'
                    }`}
                  >
                    <CheckCircle2
                      className={`h-3 w-3 ${req.met ? 'text-green-600' : 'text-muted-foreground'}`}
                    />
                    {req.label}
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">{t.auth.register.confirmPasswordLabel}</Label>
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
                <p className="text-xs text-destructive">{t.auth.register.passwordMismatchInline}</p>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4">
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  {t.auth.register.submitting}
                </>
              ) : (
                t.auth.register.submit
              )}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              {t.auth.register.haveAccount}{' '}
              <Link to="/login" className="text-primary hover:underline">
                {t.auth.register.loginLink}
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
