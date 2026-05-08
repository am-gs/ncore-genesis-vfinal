'use client';

import { useState } from 'react';
import { TerminalView } from './terminal-view';
import { BrowserView } from './browser-view';
import { FileExplorer } from './file-explorer';
import { CodeViewer } from './code-viewer';
import { PlanViewer } from './plan-viewer';
import {
  Terminal, Globe, FolderTree, Code, FileText,
  X
} from 'lucide-react';

type TabId = 'terminal' | 'browser' | 'files' | 'code' | 'plan';

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'terminal', label: 'Terminal', icon: Terminal },
  { id: 'browser', label: 'Browser', icon: Globe },
  { id: 'files', label: 'Files', icon: FolderTree },
  { id: 'code', label: 'Code', icon: Code },
  { id: 'plan', label: 'Plan', icon: FileText },
];

export function WorkspacePanel({
  terminalOutput,
  browserUrl,
  files,
  codeContent,
  codeLanguage,
  plan,
}: {
  terminalOutput: { output: string; is_stderr: boolean }[];
  browserUrl: string;
  files: import('@/app/types').FileNode[];
  codeContent: string;
  codeLanguage: string;
  plan: import('@/app/types').TaskPlan | null;
}) {
  const [activeTab, setActiveTab] = useState<TabId>('terminal');

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* Tab Bar */}
      <div className="flex items-center border-b border-line bg-panel px-1">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium
                border-b-2 transition-colors
                ${activeTab === tab.id
                  ? 'border-accent text-accent'
                  : 'border-transparent text-text-secondary hover:text-text'
                }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'terminal' && (
          <TerminalView output={terminalOutput} />
        )}
        {activeTab === 'browser' && (
          <BrowserView url={browserUrl} />
        )}
        {activeTab === 'files' && (
          <FileExplorer files={files} />
        )}
        {activeTab === 'code' && (
          <CodeViewer content={codeContent} language={codeLanguage} />
        )}
        {activeTab === 'plan' && (
          <PlanViewer plan={plan} />
        )}
      </div>
    </div>
  );
}
