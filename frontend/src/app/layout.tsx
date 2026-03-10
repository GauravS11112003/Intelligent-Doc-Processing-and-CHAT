import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "IDP Platform — Intelligent Document Processing",
  description:
    "Upload PDFs, chat with them via RAG, and extract structured data with AI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {/* Top navigation bar */}
        <header className="h-14 border-b bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60 flex items-center px-5 sticky top-0 z-50">
          <div className="flex items-center gap-3">
            <div className="size-8 rounded-lg bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center shadow-sm">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-primary-foreground">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>
                <path d="M14 2v6h6"/>
                <path d="M9 15h6"/>
                <path d="M9 11h6"/>
              </svg>
            </div>
            <div className="flex items-baseline gap-2">
              <h1 className="text-sm font-semibold tracking-tight">
                IDP Platform
              </h1>
              <div className="hidden sm:flex items-center gap-1.5">
                <div className="w-px h-3.5 bg-border" />
                <span className="text-[11px] text-muted-foreground font-medium">
                  Intelligent Document Processing
                </span>
              </div>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <div className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="hidden sm:inline">System Online</span>
            </div>
          </div>
        </header>

        <main>{children}</main>
      </body>
    </html>
  );
}
