import type { Metadata } from "next";
import "@/styles/globals.css";
import { AuthGuard } from "@/components/AuthGuard";
import { AppShell } from "@/components/layout/AppShell";
import { DevToolbar } from "@/components/DevToolbar";

export const metadata: Metadata = {
  title: "Vaani — FNOL Operations",
  description: "Multilingual voice agent operations dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Sans+Condensed:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </head>
      <body
        className="min-h-screen bg-[#0A0A0A] text-[#FAFAFA]"
      >
        <AuthGuard>
          <AppShell>
            {children}
          </AppShell>
          <DevToolbar />
        </AuthGuard>
      </body>
    </html>
  );
}
