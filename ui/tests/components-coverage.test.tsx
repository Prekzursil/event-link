import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';
import { EventCard } from '@/components/events/EventCard';
import { Calendar } from '@/components/ui/calendar';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { LoadingOverlay, LoadingPage, LoadingSpinner } from '@/components/ui/loading';

function renderWithLanguage(node: React.ReactElement) {
  return render(<LanguageProvider>{node}</LanguageProvider>);
}

function makeEvent(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 101,
    title: 'Event title',
    description: 'Event description',
    category: 'Technical',
    start_time: new Date(Date.now() + 3600000).toISOString(),
    end_time: new Date(Date.now() + 7200000).toISOString(),
    city: 'Cluj',
    location: 'Main hall',
    max_seats: 10,
    seats_taken: 2,
    tags: [
      { id: 1, name: 'Tag 1' },
      { id: 2, name: 'Tag 2' },
      { id: 3, name: 'Tag 3' },
      { id: 4, name: 'Tag 4' },
    ],
    owner_id: 9,
    owner_name: 'Owner',
    status: 'published',
    cover_url: '',
    recommendation_reason: 'Recommended for you',
    ...overrides,
  };
}

describe('shared component coverage matrix', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.setItem('language_preference', 'en');

    Object.defineProperty(globalThis, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    });
  });

  it('covers EventCard image/favorite/recommendation/edit/past/full branches', async () => {
    const onFavoriteToggle = vi.fn();
    const onEventClick = vi.fn();

    render(
      <MemoryRouter>
        <LanguageProvider>
          <EventCard
            event={makeEvent({
              status: 'draft',
              seats_taken: 10,
              max_seats: 10,
              cover_url: 'https://example.invalid/image.jpg',
            })}
            onFavoriteToggle={onFavoriteToggle}
            isFavorite
            showRecommendation
            isPast
            showEditButton
            onEventClick={onEventClick}
          />
        </LanguageProvider>
      </MemoryRouter>,
    );

    const image = screen.getByRole('img', { name: /Event title/i });
    fireEvent.error(image);
    expect(image).toHaveAttribute('src', expect.stringContaining('images.unsplash.com'));

    const favoriteButton = screen.getAllByRole('button')[0];
    fireEvent.click(favoriteButton);
    expect(onFavoriteToggle).toHaveBeenCalledWith(101, false);

    const link = screen.getByRole('link');
    fireEvent.click(link);
    expect(onEventClick).toHaveBeenCalledWith(101);

    const editButton = screen.getAllByRole('button')[1];
    fireEvent.click(editButton);

    expect(screen.getByText(/Draft/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Ended/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Recommended for you/i)).toBeInTheDocument();
    expect(screen.getByText('+1')).toBeInTheDocument();
  });

  it('covers EventCard fallback cover and location/seats omissions', () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <EventCard
            event={makeEvent({
              cover_url: '',
              city: '',
              location: '',
              max_seats: undefined,
              tags: [],
            })}
          />
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getAllByText(/Event title/i).length).toBeGreaterThan(0);
  });

  it('covers Calendar custom props and chevron rendering', () => {
    const onSelect = vi.fn();
    renderWithLanguage(
      <Calendar
        showOutsideDays={false}
        className="calendar-custom"
        classNames={{ day: 'day-custom' }}
        mode="single"
        selected={new Date()}
        onSelect={onSelect}
      />, 
    );

    expect(document.querySelector('.calendar-custom')).toBeInTheDocument();
    expect(document.querySelector('.day-custom')).toBeInTheDocument();
  });

  it('covers dropdown menu primitive wrappers without runtime errors', () => {
    const onCheckedChange = vi.fn();
    const onValueChange = vi.fn();

    render(
      <DropdownMenu open>
        <DropdownMenuTrigger asChild>
          <button type="button">Open menu</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel inset>Menu label</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem inset>
              Menu item
              <DropdownMenuShortcut>⌘K</DropdownMenuShortcut>
            </DropdownMenuItem>
            <DropdownMenuCheckboxItem checked onCheckedChange={onCheckedChange}>
              Checkbox item
            </DropdownMenuCheckboxItem>
          </DropdownMenuGroup>
          <DropdownMenuRadioGroup value="one" onValueChange={onValueChange}>
            <DropdownMenuRadioItem value="one">Radio one</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="two">Radio two</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
          <DropdownMenuSub open>
            <DropdownMenuSubTrigger inset>More</DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent>
                <DropdownMenuItem>Nested item</DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuPortal>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    expect(screen.getByText(/Open menu/i)).toBeInTheDocument();
  });

  it('covers select and table wrappers including label/separator/footer/caption', () => {
    render(
      <div>
        <Select value="one" onValueChange={() => undefined}>
          <SelectTrigger aria-label="coverage-select">
            <SelectValue placeholder="Choose one" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel>Group Label</SelectLabel>
              <SelectItem value="one">One</SelectItem>
              <SelectSeparator />
              <SelectItem value="two">Two</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>

        <Table>
          <TableCaption>Coverage caption</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Header</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>Value</TableCell>
            </TableRow>
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell>Footer</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>,
    );

    expect(screen.getByLabelText('coverage-select')).toBeInTheDocument();
    expect(screen.getByText('Coverage caption')).toBeInTheDocument();
    expect(screen.getByText('Footer')).toBeInTheDocument();
  });

  it('covers loading spinner/page/overlay branches', () => {
    renderWithLanguage(
      <div>
        <LoadingSpinner size="sm" className="spinner-custom" />
        <LoadingSpinner size="lg" />
        <LoadingPage />
        <LoadingPage message="Custom loading message" />
        <LoadingOverlay />
        <LoadingOverlay message="Overlay message" />
      </div>,
    );

    expect(document.querySelector('.spinner-custom')).toBeInTheDocument();
    expect(screen.getByText(/Custom loading message/i)).toBeInTheDocument();
    expect(screen.getByText(/Overlay message/i)).toBeInTheDocument();
  });
});






