'use client';

import { ReactNode } from 'react';
import { Navigation } from './navigation';

export default function MainLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen bg-bg text-text">
      {/* Sidebar Navigation */}
      <aside className="w-16 flex-shrink-0 border-r border-line bg-panel flex flex-col items-center py-3 gap-1">
        <Navigation />
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
    </div>
  );
}
