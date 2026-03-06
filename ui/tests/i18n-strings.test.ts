import { describe, expect, it } from 'vitest';

import { RO_STRINGS } from '@/i18n/strings';

describe('romanian auth strings', () => {
  it('keeps the rewritten access-code copy grammatically correct', () => {
    expect(RO_STRINGS.auth.login.errorFallback).toBe('Email sau cod de acces incorect');
    expect(RO_STRINGS.auth.resetAccessCode.newAccessCodeLabel).toBe('Cod de acces nou');
    expect(RO_STRINGS.auth.register.accessCodeInvalidDescription).toBe(
      'Codul de acces nu îndeplinește cerințele',
    );
    expect(RO_STRINGS.auth.resetAccessCode.accessCodeInvalidDescription).toBe(
      'Codul de acces nu îndeplinește cerințele',
    );
  });
});
