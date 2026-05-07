import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Libre_Baskerville } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], weight: ["300","400","500","600","700"] });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], weight: ["400","500"] });
const libre = Libre_Baskerville({ variable: "--font-libre", subsets: ["latin"], weight: ["400","700"], style: ["normal","italic"] });

export const metadata: Metadata = {
  title: "Sovereign Mission Control",
  description: "Local high-compliance agentic stack",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable} ${libre.variable} dark`}>
      <body className="h-screen overflow-hidden bg-bg text-text font-sans">{children}</body>
    </html>
  );
}
