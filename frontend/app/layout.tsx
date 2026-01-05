import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolyEdge - Polymarket Insider Detection",
  description: "Real-time insider detection dashboard for Polymarket trading activity",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
