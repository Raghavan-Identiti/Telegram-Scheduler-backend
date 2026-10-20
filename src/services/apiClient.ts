// src/services/apiClient.ts

declare global {
  interface Window {
    Clerk?: {
      session?: {
        getToken: () => Promise<string | null>;
      };
      user?: {
        primaryEmailAddress?: {
          emailAddress?: string;
        };
      };
    };
  }
}

/**
 * Retrieves the current Clerk Bearer token from the active session.
 */
export async function getClerkToken(): Promise<string | null> {
  try {
    if (window.Clerk?.session) {
      return await window.Clerk.session.getToken();
    }
  } catch (err) {
    console.warn('⚠️ Could not fetch Clerk session token:', err);
  }
  return null;
}

/**
 * Authenticated fetch helper.
 * Automatically injects Clerk Bearer token in Authorization header for protected backend APIs.
 */
export async function authenticatedFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const token = await getClerkToken();
  const headers = new Headers(init?.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Pass active email header as supplemental identification
  const userEmail = window.Clerk?.user?.primaryEmailAddress?.emailAddress;
  if (userEmail) {
    headers.set('X-User-Email', userEmail);
  }

  return fetch(input, {
    ...init,
    headers,
  });
}
