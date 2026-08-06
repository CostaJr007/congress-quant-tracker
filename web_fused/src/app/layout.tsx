import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/sidebar";
import TopBar from "@/components/top-bar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "CongressInvests — Congressional Trading Intelligence",
  description: "Track every congressional trade. Real-time Senate and House financial disclosure monitoring.",
  openGraph: {
    title: "CongressInvests — Congressional Trading Intelligence",
    description: "Track every congressional trade. Real-time monitoring.",
    siteName: "CongressInvests",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body className="h-screen antialiased flex overflow-hidden bg-background text-fg" style={{ fontFamily: "var(--font-inter), system-ui, sans-serif" }}>
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar />
          <main className="flex-1 overflow-y-auto overflow-x-clip scroll-smooth">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}