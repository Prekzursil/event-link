import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Calendar,
  Check,
  Heart,
  Home,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Plus,
  Settings,
  Sun,
  User,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import authService from '@/services/auth.service';
import { useToast } from '@/hooks/use-toast';
import type { ThemePreference } from '@/types';

export function Navbar() {
  const { user, isAuthenticated, isOrganizer, logout, refreshUser } = useAuth();
  const { preference, resolvedTheme, setPreference } = useTheme();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { toast } = useToast();
  const [organizerUpgradeOpen, setOrganizerUpgradeOpen] = useState(false);
  const [organizerInviteCode, setOrganizerInviteCode] = useState('');
  const [isUpgradingOrganizer, setIsUpgradingOrganizer] = useState(false);
  const [isSavingTheme, setIsSavingTheme] = useState(false);

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
    { href: '/', label: 'Evenimente', icon: Home },
    ...(isAuthenticated
      ? [
          { href: '/my-events', label: 'Evenimentele Mele', icon: Calendar },
          { href: '/favorites', label: 'Favorite', icon: Heart },
        ]
      : []),
    ...(isOrganizer
      ? [{ href: '/organizer', label: 'Dashboard', icon: Settings }]
      : []),
  ];

  const handleOrganizerUpgrade = async () => {
    const inviteCode = organizerInviteCode.trim();
    if (!inviteCode) {
      toast({
        title: 'Cod lipsă',
        description: 'Introdu codul de invitație pentru a deveni organizator.',
        variant: 'destructive',
      });
      return;
    }

    setIsUpgradingOrganizer(true);
    try {
      const response = await authService.upgradeToOrganizer(inviteCode);
      await refreshUser();

      if (response.status === 'already_organizer') {
        toast({
          title: 'Ești deja organizator',
          description: 'Contul tău are deja rol de organizator.',
        });
      } else {
        toast({
          title: 'Upgrade reușit',
          description: 'Contul tău a fost actualizat la organizator.',
          variant: 'success' as const,
        });
      }

      setOrganizerUpgradeOpen(false);
      setOrganizerInviteCode('');
      setMobileMenuOpen(false);
      navigate('/organizer');
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string; error?: { message?: string } } } };
      toast({
        title: 'Eroare',
        description:
          axiosError.response?.data?.detail ||
          axiosError.response?.data?.error?.message ||
          'Nu am putut face upgrade la organizator.',
        variant: 'destructive',
      });
    } finally {
      setIsUpgradingOrganizer(false);
    }
  };

  const handleThemeChange = async (nextPreference: ThemePreference) => {
    const prev = preference;
    setPreference(nextPreference);
    if (!isAuthenticated) return;

    setIsSavingTheme(true);
    try {
      await authService.updateThemePreference(nextPreference);
      await refreshUser();
    } catch {
      setPreference(prev);
      toast({
        title: 'Eroare',
        description: 'Nu am putut salva preferința de temă.',
        variant: 'destructive',
      });
    } finally {
      setIsSavingTheme(false);
    }
  };

  return (
    <nav className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <Calendar className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold">EventLink</span>
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
              <Button variant="ghost" size="icon" aria-label="Alege tema" disabled={isSavingTheme}>
                {resolvedTheme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Tema</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => handleThemeChange('system')} disabled={isSavingTheme}>
                <Monitor className="mr-2 h-4 w-4" />
                Sistem
                {preference === 'system' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleThemeChange('light')} disabled={isSavingTheme}>
                <Sun className="mr-2 h-4 w-4" />
                Luminos
                {preference === 'light' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleThemeChange('dark')} disabled={isSavingTheme}>
                <Moon className="mr-2 h-4 w-4" />
                Întunecat
                {preference === 'dark' && <Check className="ml-auto h-4 w-4" />}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {isAuthenticated ? (
            <>
              {isOrganizer && (
                <Button asChild size="sm">
                  <Link to="/organizer/events/new">
                    <Plus className="mr-2 h-4 w-4" />
                    Eveniment Nou
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
                        {user?.full_name || 'Utilizator'}
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
                      Evenimentele Mele
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/favorites">
                      <Heart className="mr-2 h-4 w-4" />
                      Favorite
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/profile">
                      <User className="mr-2 h-4 w-4" />
                      Profil
                    </Link>
                  </DropdownMenuItem>
                  {!isOrganizer && (
                    <DropdownMenuItem
                      onSelect={(e) => {
                        e.preventDefault();
                        setOrganizerUpgradeOpen(true);
                      }}
                    >
                      <Settings className="mr-2 h-4 w-4" />
                      Devino organizator
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout}>
                    <LogOut className="mr-2 h-4 w-4" />
                    Deconectare
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="ghost" asChild>
                <Link to="/login">Autentificare</Link>
              </Button>
              <Button asChild>
                <Link to="/register">Înregistrare</Link>
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
                    Eveniment Nou
                  </Link>
                )}
                {!isOrganizer && (
                  <button
                    onClick={() => {
                      setOrganizerUpgradeOpen(true);
                      setMobileMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-accent"
                  >
                    <Settings className="h-4 w-4" />
                    Devino organizator
                  </button>
                )}
                <button
                  onClick={() => {
                    handleLogout();
                    setMobileMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-destructive hover:bg-accent"
                >
                  <LogOut className="h-4 w-4" />
                  Deconectare
                </button>
              </>
            ) : (
              <div className="flex flex-col gap-2">
                <Button variant="outline" asChild className="w-full">
                  <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                    Autentificare
                  </Link>
                </Button>
                <Button asChild className="w-full">
                  <Link to="/register" onClick={() => setMobileMenuOpen(false)}>
                    Înregistrare
                  </Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      <Dialog open={organizerUpgradeOpen} onOpenChange={setOrganizerUpgradeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Devino organizator</DialogTitle>
            <DialogDescription>
              Introdu codul de invitație primit pentru a activa funcțiile de organizator.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="organizerInviteCode">Cod invitație</Label>
            <Input
              id="organizerInviteCode"
              value={organizerInviteCode}
              onChange={(e) => setOrganizerInviteCode(e.target.value)}
              placeholder="ex: ABCD-1234"
              disabled={isUpgradingOrganizer}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setOrganizerUpgradeOpen(false)}
              disabled={isUpgradingOrganizer}
            >
              Anulează
            </Button>
            <Button onClick={handleOrganizerUpgrade} disabled={isUpgradingOrganizer}>
              {isUpgradingOrganizer ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Se procesează...
                </>
              ) : (
                'Activează'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </nav>
  );
}
