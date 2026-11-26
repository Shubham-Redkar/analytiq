import type { Metadata } from "next";
import { Suspense } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/context/auth-context";
import { Navbar } from "@/components/navbar";
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
  title: "AnalytIQ – Intelligent Analysis. Verified Insights.",
  description:
    "An evidence-grounded, multi-agent AI data analytics platform that combines AI-driven reasoning with deterministic data processing.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="h-full flex flex-col bg-background text-foreground overflow-hidden">
        <AuthProvider>
          <Suspense fallback={<div className="h-16 border-b border-border bg-card/95" />}>
            <Navbar />
          </Suspense>
          <div className="flex-1 min-h-0 overflow-auto">{children}</div>
        </AuthProvider>
      </body>
    </html>
  );
}
