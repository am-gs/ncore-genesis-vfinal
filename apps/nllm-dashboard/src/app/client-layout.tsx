"use client";

import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { WebSocketProvider } from "@/app/contexts/websocket";
import MainLayout from "@/app/components/main-layout";

export default function ClientLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isFullPage = pathname === "/mami-card";

  if (isFullPage) {
    return (
      <WebSocketProvider>
        <div className="w-full h-full">{children}</div>
      </WebSocketProvider>
    );
  }

  return (
    <WebSocketProvider>
      <MainLayout>{children}</MainLayout>
    </WebSocketProvider>
  );
}
