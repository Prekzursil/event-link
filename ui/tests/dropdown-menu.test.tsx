import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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

describe('dropdown-menu primitives', () => {
  it('renders and exercises core dropdown branches', () => {
    const onSelect = vi.fn();

    const radioGroup = (
      <DropdownMenuRadioGroup value="one">
        <DropdownMenuRadioItem value="one">One</DropdownMenuRadioItem>
        <DropdownMenuRadioItem value="two">Two</DropdownMenuRadioItem>
      </DropdownMenuRadioGroup>
    );

    const subMenu = (
      <DropdownMenuSub>
        <DropdownMenuSubTrigger inset>More</DropdownMenuSubTrigger>
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <DropdownMenuItem>Sub Item</DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
    );

    const group = (
      <DropdownMenuGroup>
        <DropdownMenuItem inset onSelect={onSelect}>
          Item
        </DropdownMenuItem>
        <DropdownMenuCheckboxItem checked>Checked</DropdownMenuCheckboxItem>
        {radioGroup}
        {subMenu}
      </DropdownMenuGroup>
    );

    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel inset>Menu</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {group}
          <DropdownMenuShortcut data-testid="shortcut">Ctrl+K</DropdownMenuShortcut>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    expect(screen.getByText('Menu')).toBeInTheDocument();
    expect(screen.getByText('Checked')).toBeInTheDocument();
    expect(screen.getByText('One')).toBeInTheDocument();
    expect(screen.getByText('More')).toBeInTheDocument();
    expect(screen.getByTestId('shortcut')).toHaveTextContent('Ctrl+K');

    fireEvent.click(screen.getByText('Item'));
    expect(onSelect).toHaveBeenCalled();
  });
});
