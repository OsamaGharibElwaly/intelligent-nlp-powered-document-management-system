"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import ux from "../components/auth/authPages.module.css";
import { writeStoredAuth } from "../lib/authStorage";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${backendUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string;
        access_token?: string;
        role?: string;
      };
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Login failed");
        return;
      }
      const token = data.access_token ?? "";
      if (!token) {
        setError("Invalid response: missing token.");
        return;
      }
      writeStoredAuth({
        token,
        role: typeof data.role === "string" ? data.role : "",
        email: email.trim(),
      });
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Network error — could not reach the server.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className={ux.page} data-testid="login-page">
      <div className={ux.card}>
        <h1 className={ux.title}>Sign in</h1>
        <p className={ux.sub}>Use your workspace credentials. You will be redirected to the dashboard after a successful login.</p>

        {error ? (
          <div className={ux.err} role="alert" data-testid="login-error">
            {error}
          </div>
        ) : null}

        <form onSubmit={(ev) => void submit(ev)}>
          <label className={ux.field}>
            Email
            <input
              className={ux.input}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="login-email-input"
            />
          </label>
          <label className={ux.field}>
            Password
            <input
              className={ux.input}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="login-password-input"
            />
          </label>
          <button type="submit" className={ux.btnPrimary} disabled={busy} data-testid="login-submit-button">
            {busy ? "Signing in…" : "Login"}
          </button>
        </form>

        <p className={ux.footer}>
          No account? <Link href="/register" data-testid="login-register-link">Register</Link>
        </p>
      </div>
    </main>
  );
}
