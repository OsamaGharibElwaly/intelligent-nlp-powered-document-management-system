"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import ux from "../components/auth/authPages.module.css";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!backendUrl) {
      setError("NEXT_PUBLIC_BACKEND_URL is not configured.");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${backendUrl}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = (await response.json().catch(() => ({}))) as { detail?: string };
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Registration failed");
        return;
      }
      router.push("/login");
      router.refresh();
    } catch {
      setError("Network error — could not reach the server.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className={ux.page} data-testid="register-page">
      <div className={ux.card}>
        <h1 className={ux.title}>Create account</h1>
        <p className={ux.sub}>Register a new user. After success you can sign in from the login page.</p>

        {error ? (
          <div className={ux.err} role="alert" data-testid="register-error">
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
              data-testid="register-email-input"
            />
          </label>
          <label className={ux.field}>
            Password
            <input
              className={ux.input}
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="register-password-input"
            />
          </label>
          <label className={ux.field}>
            Confirm password
            <input
              className={ux.input}
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              data-testid="register-confirm-input"
            />
          </label>
          <button type="submit" className={ux.btnPrimary} disabled={busy} data-testid="register-submit-button">
            {busy ? "Creating account…" : "Register"}
          </button>
        </form>

        <p className={ux.footer}>
          Already registered? <Link href="/login" data-testid="register-login-link">Login</Link>
        </p>
      </div>
    </main>
  );
}
