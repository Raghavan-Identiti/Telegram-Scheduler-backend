// src/services/authConfig.ts

export const CLERK_PUBLISHABLE_KEY =
  (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined)?.trim() || '';

// Primary authorized user requested
export const PRIMARY_ADMIN_EMAIL = 'raghavan@identitidesign.com';

// Allowed organizational domain
export const ALLOWED_DOMAIN = 'identitidesign.com';

// Additional allowed emails from environment or fallback
const ENV_ALLOWED_EMAILS = (import.meta.env.VITE_ALLOWED_EMAILS as string | undefined)
  ?.split(',')
  .map(e => e.trim().toLowerCase())
  .filter(Boolean) || [];

export const ALLOWED_EMAILS = Array.from(
  new Set([PRIMARY_ADMIN_EMAIL.toLowerCase(), ...ENV_ALLOWED_EMAILS])
);

export type UserRole = 'Admin' | 'Operator' | 'Unauthorized';

/**
 * Validates whether an email address is authorized to access TeleQueue.
 * Allows raghavan@identitidesign.com explicitly, and any verified user
 * from the @identitidesign.com domain if configured.
 */
export function isEmailAuthorized(email: string | null | undefined): boolean {
  if (!email) return false;
  const cleanEmail = email.trim().toLowerCase();

  // 1. Direct allowed emails match
  if (ALLOWED_EMAILS.includes(cleanEmail)) {
    return true;
  }

  // 2. Allowed domain match (@identitidesign.com)
  const allowDomain = import.meta.env.VITE_ALLOW_DOMAIN_LOGIN !== 'false';
  if (allowDomain && cleanEmail.endsWith(`@${ALLOWED_DOMAIN.toLowerCase()}`)) {
    return true;
  }

  return false;
}

/**
 * Returns the user role based on email.
 * raghavan@identitidesign.com is granted 'Admin'.
 * Other @identitidesign.com users are granted 'Operator'.
 */
export function getUserRole(email: string | null | undefined): UserRole {
  if (!email) return 'Unauthorized';
  const cleanEmail = email.trim().toLowerCase();

  if (cleanEmail === PRIMARY_ADMIN_EMAIL.toLowerCase()) {
    return 'Admin';
  }

  if (isEmailAuthorized(cleanEmail)) {
    return 'Operator';
  }

  return 'Unauthorized';
}
