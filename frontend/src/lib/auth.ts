/**
 * Client-side auth utilities.
 *
 * JWT is stored in localStorage (key: lexrag_token).
 * All reads/writes are wrapped in try/catch because localStorage
 * can throw in private browsing mode.
 */

const TOKEN_KEY = "lexrag_token";
const USER_KEY = "lexrag_user";

export interface StoredUser {
  userId: string;
  email: string;
  fullName: string;
  role: "USER" | "ADMIN";
}

export function saveSession(token: string, user: StoredUser): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // Private browsing / storage blocked — session is still functional for this tab
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // ignore
  }
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
