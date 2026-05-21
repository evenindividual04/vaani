"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getAuthToken } from "@/lib/api";

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  useEffect(() => {
    const token = getAuthToken();
    if (!token && !isLoginPage) {
      router.replace("/login");
      return;
    }
    if (token && isLoginPage) {
      router.replace("/");
    }
  }, [isLoginPage, router]);

  if (isLoginPage) {
    return <>{children}</>;
  }

  const token = getAuthToken();
  if (!token) return null;

  return <>{children}</>;
}
