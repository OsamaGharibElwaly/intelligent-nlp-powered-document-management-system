export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export type FetchWithRetryOptions = {
  retries?: number;
  timeoutMs?: number;
  onRetry?: (attemptIndex: number) => void;
};

/**
 * Browser-side resilience: timeouts, limited retries with exponential backoff
 * for flaky networks and transient 5xx / 429 responses.
 */
export async function fetchWithRetry(url: string, init: RequestInit, opts: FetchWithRetryOptions = {}): Promise<Response> {
  const retries = opts.retries ?? 2;
  const timeoutMs = opts.timeoutMs ?? 90_000;
  let lastErr: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      if (attempt > 0) opts.onRetry?.(attempt);
      const res = await fetch(url, { ...init, signal: ctrl.signal });
      window.clearTimeout(tid);
      if (res.ok) return res;
      const retryable = res.status === 429 || res.status >= 500;
      if (retryable && attempt < retries) {
        await sleep(380 * 2 ** attempt);
        continue;
      }
      return res;
    } catch (e) {
      window.clearTimeout(tid);
      lastErr = e;
      const canRetry =
        attempt < retries && (e instanceof TypeError || (e instanceof DOMException && e.name === "AbortError"));
      if (canRetry) {
        await sleep(380 * 2 ** attempt);
        continue;
      }
      throw e instanceof Error ? e : new Error(String(e));
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("Request failed");
}
