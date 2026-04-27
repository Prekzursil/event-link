import type { ComponentType, SVGProps } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, Mail } from 'lucide-react';
import { useI18n } from '@/contexts/LanguageContext';

// Inline GitHub mark — lucide-react's Github icon is deprecated as of
// 0.x with no built-in replacement (see lucide-icons/lucide#670). Render
// the official GitHub mark inline so we don't pull in an extra brand-icon
// package just for the footer link.
function GithubIcon(props: Readonly<SVGProps<SVGSVGElement>>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      width="24"
      height="24"
      aria-hidden="true"
      {...props}
    >
      <path d="M12 .5C5.73.5.66 5.57.66 11.85c0 5.02 3.26 9.27 7.78 10.78.57.1.78-.25.78-.55v-2c-3.16.69-3.83-1.36-3.83-1.36-.52-1.32-1.27-1.67-1.27-1.67-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.68 1.24 3.34.95.1-.74.4-1.24.72-1.52-2.52-.29-5.18-1.26-5.18-5.6 0-1.24.44-2.25 1.16-3.04-.12-.29-.5-1.45.11-3.02 0 0 .96-.31 3.13 1.16a10.85 10.85 0 0 1 5.7 0c2.17-1.47 3.13-1.16 3.13-1.16.61 1.57.23 2.73.11 3.02.72.79 1.16 1.8 1.16 3.04 0 4.35-2.66 5.31-5.19 5.59.41.35.78 1.03.78 2.08v3.08c0 .3.21.65.78.55a11.36 11.36 0 0 0 7.78-10.78C23.34 5.57 18.27.5 12 .5z" />
    </svg>
  );
}

type QuickLinkItem = Readonly<{
  href: string;
  label: string;
}>;

type ContactLinkItem = Readonly<{
  href: string;
  // icon accepts both lucide-react ForwardRefExoticComponents (e.g.
  // typeof Calendar) and our inline GithubIcon component, which is a
  // plain functional component with className/SVG props.
  icon: ComponentType<{ className?: string } & SVGProps<SVGSVGElement>>;
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
    { href: 'https://github.com/Prekzursil/event-link', icon: GithubIcon, label: 'GitHub' },
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
