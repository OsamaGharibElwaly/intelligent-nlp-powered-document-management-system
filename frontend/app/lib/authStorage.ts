const TOKEN_KEY = "rag_auth_token";
const ROLE_KEY = "rag_auth_role";
const EMAIL_KEY = "rag_auth_email";

export type StoredAuth = {
  token: string;
  role: string;
  email: string;
};

export function readStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  try {
    const token = window.localStorage.getItem(TOKEN_KEY) ?? "";
    const role = window.localStorage.getItem(ROLE_KEY) ?? "";
    const email = window.localStorage.getItem(EMAIL_KEY) ?? "";
    if (!token.trim()) return null;
    return { token: token.trim(), role, email };
  } catch {
    return null;
  }
}

export function writeStoredAuth(auth: StoredAuth): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, auth.token);
    window.localStorage.setItem(ROLE_KEY, auth.role);
    window.localStorage.setItem(EMAIL_KEY, auth.email);
    window.dispatchEvent(new Event("rag-auth-changed"));
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearStoredAuth(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(ROLE_KEY);
    window.localStorage.removeItem(EMAIL_KEY);
    window.dispatchEvent(new Event("rag-auth-changed"));
  } catch {
    /* ignore */
  }
}

export function authHeadersFromStorage(): Record<string, string> {
  const a = readStoredAuth();
  if (!a?.token) return {};
  return { Authorization: `Bearer ${a.token}` };
}
