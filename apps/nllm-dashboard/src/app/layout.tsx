     1	// Updated root layout with main layout
     2	
     3	import type { Metadata } from "next";
     4	import { Inter, JetBrains_Mono, Libre_Baskerville } from "next/font/google";
     5	import "./globals.css";
     6	import { WebSocketProvider } from "@/app/contexts/websocket";
     7	import MainLayout from "@/app/components/main-layout";
     8	
     9	const inter = Inter({ variable: "--font-inter", subsets: ["latin"], weight: ["300","400","500","600","700"] });
    10	const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], weight: ["400","500"] });
    11	const libre = Libre_Baskerville({ variable: "--font-libre", subsets: ["latin"], weight: ["400","700"], style: ["normal","italic"] });
    12	
    13	export const metadata: Metadata = {
    14	  title: "NLLM.ING Dashboard",
    15	  description: "Never-Refusing AI. Costs Pennies.",
    16	};
    17	
    18	export default function RootLayout({
    19	  children,
    20	}: Readonly<{
    21	  children: React.ReactNode;
    22	}>) {
    23	  return (
    24	    <html lang="en" className={`${inter.variable} ${jetbrains.variable} ${libre.variable}`}>
    25	      <body className="h-screen overflow-hidden bg-bg text-text font-sans antialiased">
    26	        <div className="ambient-bg" />
    27	        <WebSocketProvider>
    28	          <MainLayout>
    29	            {children}
    30	          </MainLayout>
    31	        </WebSocketProvider>
    32	      </body>
    33	    </html>
    34	  );
    35	}