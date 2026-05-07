import Sidebar from '@/components/shell/Sidebar';
import TopBar from '@/components/shell/TopBar';
import CommandPalette from '@/components/shell/CommandPalette';

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden relative">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
      <CommandPalette />
    </div>
  );
}
