import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/dashboard") {
    return NextResponse.rewrite(new URL("/", request.url));
  }

  if (pathname === "/documents") {
    const u = request.nextUrl.clone();
    u.pathname = "/";
    u.searchParams.set("panel", "documents");
    return NextResponse.rewrite(u);
  }

  if (pathname === "/query") {
    const u = request.nextUrl.clone();
    u.pathname = "/";
    u.searchParams.set("panel", "query");
    return NextResponse.rewrite(u);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard", "/documents", "/query"],
};
