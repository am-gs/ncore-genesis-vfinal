import { create } from 'zustand';

interface AppState {
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  activeLog: string;
  toggleSidebar: () => void;
  setCommandOpen: (v: boolean) => void;
  setActiveLog: (v: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  commandOpen: false,
  activeLog: 'watchdog',
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setCommandOpen: (v) => set({ commandOpen: v }),
  setActiveLog: (v) => set({ activeLog: v }),
}));
