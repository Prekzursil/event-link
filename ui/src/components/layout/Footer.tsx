import { Link } from 'react-router-dom';
import { Calendar, Github, Mail } from 'lucide-react';
import { useI18n } from '@/contexts/LanguageContext';

type QuickLinkItem = Readonly<{
  href: string;
  label: string;
}>;

type ContactLinkItem = Readonly<{
  href: string;
  icon: typeof Calendar;
  label: string;
}>;

type FooterBrandProps = Readonly<{
  appName: string;
  description: string;
}>;

type QuickLinksSectionProps = Readonly<{
  items: QuickLinkItem[];
  title: string;
}>;

type ContactLinksSectionProps = Readonly<{
  items: ContactLinkItem[];
  title: string;
}>;

type FooterCopyrightProps = Readonly<{
  appName: string;
  copyrightLabel: string;
}>;

/** Render the shared brand block in the footer grid. */
/**
 * Test helper: footer brand.
 */
function FooterBrand({ appName, description }: FooterBrandProps) {
  return (
    <div className="space-y-4">
      <Link to="/" className="flex items-center gap-2">
        <Calendar className="h-6 w-6 text-primary" />
        <span className="text-xl font-bold">{appName}</span>
      </Link>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

/** Render the internal navigation links in the footer. */
function QuickLinksSection({ items, title }: QuickLinksSectionProps) {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">{title}</h3>
      <ul className="space-y-2 text-sm">
        {items.map((item) => (
          <li key={`${item.href}-${item.label}`}>
            <Link to={item.href} className="text-muted-foreground hover:text-foreground">
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Render the external contact links in the footer. */
function ContactLinksSection({ items, title }: ContactLinksSectionProps) {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold">{title}</h3>
      <ul className="space-y-2 text-sm">
        {items.map(({ href, icon: Icon, label }) => (
          <li key={`${href}-${label}`}>
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
            >
              <Icon className="h-4 w-4" />
              {label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Render the copyright strip at the bottom of the footer. */
function FooterCopyright({ appName, copyrightLabel }: FooterCopyrightProps) {
  return (
    <div className="mt-8 border-t pt-8 text-center text-sm text-muted-foreground">
      <p>© {new Date().getFullYear()} {appName}. {copyrightLabel}</p>
    </div>
  );
}

/** Render the application footer. */
export function Footer() {
  const { t } = useI18n();
  const quickLinks: QuickLinkItem[] = [
    { href: '/', label: t.nav.events },
    { href: '/login', label: t.nav.login },
    { href: '/register', label: t.nav.register },
  ];
  const contactLinks: ContactLinkItem[] = [
    { href: 'mailto:contact@eventlink.ro', icon: Mail, label: 'contact@eventlink.ro' },
    { href: 'https://github.com/Prekzursil/event-link', icon: Github, label: 'GitHub' },
  ];

  return (
    <footer className="border-t bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="grid gap-8 md:grid-cols-3">
          <FooterBrand appName={t.common.appName} description={t.footer.description} />
          <QuickLinksSection items={quickLinks} title={t.footer.quickLinks} />
          <ContactLinksSection items={contactLinks} title={t.footer.contact} />
        </div>
        <FooterCopyright appName={t.common.appName} copyrightLabel={t.footer.allRightsReserved} />
      </div>
    </footer>
  );
}
