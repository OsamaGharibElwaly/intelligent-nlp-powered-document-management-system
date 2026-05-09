"use client";

import type { ReactNode } from "react";

import { AuthTopNav } from "./AuthTopNav";

export function AppChrome({ children }: { children: ReactNode }) {
  return (
    <>
      <AuthTopNav />
      <div style={{ paddingTop: "3.35rem" }} data-testid="app-chrome-body">
        {children}
      </div>
    </>
  );
}
