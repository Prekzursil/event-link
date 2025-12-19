import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { useI18n } from '@/contexts/LanguageContext';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Calendar,
  Check,
  Heart,
  Home,
  LogOut,
  Languages,
  Menu,
  Monitor,
  Moon,
  Plus,
  Settings,
  Shield,
  Sun,
  User,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import authService from '@/services/auth.service';
import { useToast } from '@/hooks/use-toast';
import type { LanguagePreference, ThemePreference } from '@/types';

export function Navbar() {
  const { user, isAuthenticated, isOrganizer, isAdmin, logout, refreshUser } = useAuth();
  const { preference: themePreference, resolvedTheme, setPreference: setThemePreference } = useTheme();
  const { preference: languagePreference, language, setPreference: setLanguagePreference, t } = useI18n();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { toast } = useToast();
  const [isSavingTheme, setIsSavingTheme] = useState(false);
  const [isSavingLanguage, setIsSavingLanguage] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const getInitials = (name?: string | null, email?: string) => {
    if (name) {
      return name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    }
    return email?.slice(0, 2).toUpperCase() || 'U';
  };

  const navLinks = [
    { href: '/', label: t.nav.events, icon: Home },
    ...(isAuthenticated
      ? [
          { href: '/my-events', label: t.nav.myEvents, icon: Calendar },
          { href: '/favorites', label: t.nav.favorites, icon: Heart },
        ]
      : []),
    ...(isOrganizer
      ? [{ href: '/organizer', label: t.nav.dashboard, icon: Settings }]
      : []),
    ...(isAdmin ? [{ href: '/admin', label: t.nav.admin, icon: Shield }] : []),
  ];

  const handleThemeChange = async (nextPreference: ThemePreference) => {
    const prev = themePreference;
    setThemePreference(nextPreference);
    if (!isAuthenticated) return;

    setIsSavingTheme(true);
    try {
      await authService.updateThemePreference(nextPreference);
      await refreshUser();
    } catch {
      setThemePreference(prev);
      toast({
        title: t.theme.saveErrorTitle,
        description: t.theme.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingTheme(false);
    }
  };

  const handleLanguageChange = async (nextPreference: LanguagePreference) => {
    const prev = languagePreference;
    setLanguagePreference(nextPreference);
    if (!isAuthenticated) return;

    setIsSavingLanguage(true);
    try {
      await authService.updateLanguagePreference(nextPreference);
      await refreshUser();
      toast({
        title: t.language.savedTitle,
        description: t.language.savedDescription,
      });
    } catch {
      setLanguagePreference(prev);
      toast({
        title: t.language.saveErrorTitle,
        description: t.language.saveErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsSavingLanguage(false);
    }
  };

  return (
    <nav className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <Calendar className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold">{t.common.appName}</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden items-center gap-6 md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className="flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          ))}
        </div>

        {/* Auth Section */}
        <div className="hidden items-center gap-4 md:flex">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={t.theme.label} disabled={isSavingTheme}>
                {resolvedTheme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{t.theme.label}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => handleThemeChange('system')} disabled={isSavingTheme}>
                <Monitor className="mr-2 h-4 w-4" />
                {t.theme.system}
                {themePreference === 'system' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleThemeChange('light')} disabled={isSavingTheme}>
                <Sun className="mr-2 h-4 w-4" />
                {t.theme.light}
                {themePreference === 'light' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleThemeChange('dark')} disabled={isSavingTheme}>
                <Moon className="mr-2 h-4 w-4" />
                {t.theme.dark}
                {themePreference === 'dark' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={t.language.label} disabled={isSavingLanguage}>
                <Languages className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{t.language.label}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => handleLanguageChange('system')} disabled={isSavingLanguage}>
                <Monitor className="mr-2 h-4 w-4" />
                {t.language.system}
                {languagePreference === 'system' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleLanguageChange('ro')} disabled={isSavingLanguage}>
                {t.language.ro}
                {languagePreference === 'ro' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleLanguageChange('en')} disabled={isSavingLanguage}>
                {t.language.en}
                {languagePreference === 'en' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
                {language.toUpperCase()}
              </DropdownMenuLabel>
            </DropdownMenuContent>
          </DropdownMenu>
          {isAuthenticated ? (
            <>
              {isOrganizer && (
                <Button asChild size="sm">
                  <Link to="/organizer/events/new">
                    <Plus className="mr-2 h-4 w-4" />
                    {t.nav.newEvent}
                  </Link>
                </Button>
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="relative h-9 w-9 rounded-full">
                    <Avatar className="h-9 w-9">
                      <AvatarFallback className="bg-primary text-primary-foreground">
                        {getInitials(user?.full_name, user?.email)}
                      </AvatarFallback>
                    </Avatar>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56" align="end" forceMount>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium leading-none">
                        {user?.full_name || t.nav.userFallback}
                      </p>
                      <p className="text-xs leading-none text-muted-foreground">
                        {user?.email}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link to="/my-events">
                      <Calendar className="mr-2 h-4 w-4" />
                      {t.nav.myEvents}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/favorites">
                      <Heart className="mr-2 h-4 w-4" />
                      {t.nav.favorites}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/profile">
                      <User className="mr-2 h-4 w-4" />
                      {t.nav.profile}
                    </Link>
                  </DropdownMenuItem>
                  {isAdmin && (
                    <DropdownMenuItem asChild>
                      <Link to="/admin">
                        <Shield className="mr-2 h-4 w-4" />
                        {t.nav.admin}
                      </Link>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout}>
                    <LogOut className="mr-2 h-4 w-4" />
                    {t.nav.logout}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="ghost" asChild>
                <Link to="/login">{t.nav.login}</Link>
              </Button>
              <Button asChild>
                <Link to="/register">{t.nav.register}</Link>
              </Button>
            </div>
          )}
        </div>

        {/* Mobile Menu Button */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </Button>
      </div>

      {/* Mobile Menu */}
      <div
        className={cn(
          'absolute left-0 right-0 top-16 border-b bg-background md:hidden',
          mobileMenuOpen ? 'block' : 'hidden'
        )}
      >
        <div className="container mx-auto space-y-2 px-4 py-4">
          <div className="flex items-center justify-between gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="flex-1" disabled={isSavingTheme}>
                  {t.theme.label}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onSelect={() => handleThemeChange('system')} disabled={isSavingTheme}>
                  <Monitor className="mr-2 h-4 w-4" />
                  {t.theme.system}
                  {themePreference === 'system' && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleThemeChange('light')} disabled={isSavingTheme}>
                  <Sun className="mr-2 h-4 w-4" />
                  {t.theme.light}
                  {themePreference === 'light' && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleThemeChange('dark')} disabled={isSavingTheme}>
                  <Moon className="mr-2 h-4 w-4" />
                  {t.theme.dark}
                  {themePreference === 'dark' && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="flex-1" disabled={isSavingLanguage}>
                  {t.language.label}: {language.toUpperCase()}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => handleLanguageChange('system')} disabled={isSavingLanguage}>
                  <Monitor className="mr-2 h-4 w-4" />
                  {t.language.system}
                  {languagePreference === 'system' && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleLanguageChange('ro')} disabled={isSavingLanguage}>
                  {t.language.ro}
                  {languagePreference === 'ro' && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => handleLanguageChange('en')} disabled={isSavingLanguage}>
                  {t.language.en}
                  {languagePreference === 'en' && <Check className="ml-auto h-4 w-4" />}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {navLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-accent"
              onClick={() => setMobileMenuOpen(false)}
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          ))}
          <div className="border-t pt-2">
            {isAuthenticated ? (
              <>
                {isOrganizer && (
                  <Link
                    to="/organizer/events/new"
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-primary hover:bg-accent"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <Plus className="h-4 w-4" />
                    {t.nav.newEvent}
                  </Link>
                )}
                <button
                  onClick={() => {
                    handleLogout();
                    setMobileMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-destructive hover:bg-accent"
                >
                  <LogOut className="h-4 w-4" />
                  {t.nav.logout}
                </button>
              </>
            ) : (
              <div className="flex flex-col gap-2">
                <Button variant="outline" asChild className="w-full">
                  <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                    {t.nav.login}
                  </Link>
                </Button>
                <Button asChild className="w-full">
                  <Link to="/register" onClick={() => setMobileMenuOpen(false)}>
                    {t.nav.register}
                  </Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
