import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import TokenRefresh from "@/components/TokenRefresh";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FIA Data Viewer",
  description: "Data and plot viewer for FIA",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <TokenRefresh />
        {children}
      </body>
    </html>
  );
}
