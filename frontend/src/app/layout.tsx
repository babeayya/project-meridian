import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { CommandPalette } from "@/components/command-palette";
import { Navbar } from "@/components/navbar";
import { Providers } from "@/components/providers";
import { ScrollProgress } from "@/components/scroll-progress";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jbmono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jbmono" });

export const metadata: Metadata = {
  title: "Meridian — Equity Research Terminal",
  description:
    "Institutional equity research: auditable valuations, fundamentals, quant analytics and AI analysis.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jbmono.variable} font-sans min-h-screen antialiased`}>
        <Providers>
          <ScrollProgress />
          <Navbar />
          <CommandPalette />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
