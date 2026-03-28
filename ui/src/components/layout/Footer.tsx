import { Link } from 'react-router-dom';
import { Calendar, Github, Mail } from 'lucide-react';
import { useI18n } from '@/contexts/LanguageContext';

type FooterLinkItem = Readonly<{
  href: string;
  icon?: typeof Calendar;
  label: string;
  external?: boolean;
}>;

type FooterSectionProps = Readonly<{
  items: FooterLinkItem[];
  title: string;
}>;

/** Render a simple list section inside the shared footer shell. */
function FooterSection({ items, title }: FooterSectionProps) {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">{title}</h3>
      <ul className="space-y-2 text-sm">
        {items.map((item) => {
          const Icon = item.icon;
          const className = Icon
            ? 'flex items-center gap-2 text-muted-foreground hover:text-foreground'
            : 'text-muted-foreground hover:text-foreground';

          return (
            <li key={`${item.href}-${item.label}`}>
              {item.external ? (
                <a href={item.href} target="_blank" rel="noopener noreferrer" className={className}>
                  {Icon ? <Icon className="h-4 w-4" /> : null}
                  {item.label}
                </a>
              ) : (
                <Link to={item.href} className={className}>
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Render the application footer. */
export function Footer() {
  const { t } = useI18n();
  const quickLinks: FooterLinkItem[] = [
    { href: '/', label: t.nav.events },
    { href: '/login', label: t.nav.login },
    { href: '/register', label: t.nav.register },
  ];
  const contactLinks: FooterLinkItem[] = [
    { href: 'mailto:contact@eventlink.ro', icon: Mail, label: 'contact@eventlink.ro', external: true },
    { href: 'https://github.com/Prekzursil/event-link', icon: Github, label: 'GitHub', external: true },
  ];

  return (
    <footer className="border-t bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="grid gap-8 md:grid-cols-3">
          <div className="space-y-4">
            <Link to="/" className="flex items-center gap-2">
              <Calendar className="h-6 w-6 text-primary" />
              <span className="text-xl font-bold">{t.common.appName}</span>
            </Link>
            <p className="text-sm text-muted-foreground">{t.footer.description}</p>
          </div>
          <FooterSection items={quickLinks} title={t.footer.quickLinks} />
          <FooterSection items={contactLinks} title={t.footer.contact} />
        </div>

        <div className="mt-8 border-t pt-8 text-center text-sm text-muted-foreground">
          <p>© {new Date().getFullYear()} {t.common.appName}. {t.footer.allRightsReserved}</p>
        </div>
      </div>
    </footer>
  );
}
