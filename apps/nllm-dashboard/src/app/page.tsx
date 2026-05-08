'use client';

import { useState, useCallback } from 'react';
import { ChatPanel } from '@/app/components/chat-panel';
import { WorkspacePanel } from '@/app/components/workspace-panel';
import { StatusPanel } from '@/app/components/status-panel';
import { useWebSocket } from '@/app/contexts/websocket';
import { Session, AgentStatus, TaskResult, FileNode, BudgetInfo, TaskPlan } from '@/app/types';

const DEFAULT_BUDGET: BudgetInfo = {
  daily: 0.12,
  daily_limit: 2.0,
  monthly: 1.84,
  monthly_limit: 50.0,
  cache_hit_rate: 0.34,
};

const INITIAL_SESSIONS: Session[] = [
  {
    id: '1',
    title: 'Website Redesign Analysis',
    status: 'completed',
    createdAt: Date.now() - 3600000,
    updatedAt: Date.now() - 3500000,
  },
  {
    id: '2',
    title: 'Market Research Report',
    status: 'completed',
    createdAt: Date.now() - 7200000,
    updatedAt: Date.now() - 6900000,
  },
  {
    id: '3',
    title: 'Content Generation Pipeline',
    status: 'error',
    createdAt: Date.now() - 10800000,
    updatedAt: Date.now() - 10750000,
  },
];

const DEMO_AGENT_STATUSES: AgentStatus[] = [
  {
    role: 'Research Analyst',
    status: 'completed',
    tokens_in: 1200,
    tokens_out: 3400,
    latency: 2.4,
    cost_usd: 0.0012,
    progress: 100,
  },
  {
    role: 'Code Writer',
    status: 'completed',
    tokens_in: 800,
    tokens_out: 2100,
    latency: 1.8,
    cost_usd: 0.0008,
    progress: 100,
  },
  {
    role: 'Browser Agent',
    status: 'completed',
    tokens_in: 400,
    tokens_out: 600,
    latency: 8.2,
    cost_usd: 0.0004,
    progress: 100,
  },
];

export default function DashboardPage() {
  const { sendTask, stopTask } = useWebSocket();
  const [sessions, setSessions] = useState<Session[]>(INITIAL_SESSIONS);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentStatus[]>(DEMO_AGENT_STATUSES);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [terminalOutput, setTerminalOutput] = useState<{ output: string; is_stderr: boolean }[]>([
    { output: '> Initializing NLLM.ING agent environment...', is_stderr: false },
    { output: '> Connecting to Bifrost gateway...', is_stderr: false },
    { output: '> Bifrost: healthy, budget: $1.88/2.00 daily, cache: 34%', is_stderr: false },
    { output: '> Ready. Enter a task to begin.', is_stderr: false },
  ]);
  const [browserUrl, setBrowserUrl] = useState('');
  const [files, setFiles] = useState<FileNode[]>([]);
  const [codeContent, setCodeContent] = useState('');
  const [codeLanguage, setCodeLanguage] = useState('python');
  const [plan, setPlan] = useState<TaskPlan | null>(null);

  const handleRunTask = useCallback(
    (task: string) => {
      const newSession: Session = {
        id: Date.now().toString(),
        title: task,
        status: 'active',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        task,
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      setTerminalOutput((prev) => [
        ...prev,
        { output: `\n> Task: ${task}`, is_stderr: false },
        { output: '> Planner decomposing...', is_stderr: false },
        { output: '> Bifrost routing through semantic cache...', is_stderr: false },
        { output: '> Agents dispatched. Waiting for execution...', is_stderr: false },
      ]);
      sendTask(task);
    },
    [sendTask]
  );

  const handleStopTask = useCallback(() => {
    stopTask();
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId ? { ...s, status: 'idle' } : s
      )
    );
    setTerminalOutput((prev) => [
      ...prev,
      { output: '\n> Task stopped by user.', is_stderr: false },
    ]);
  }, [stopTask, activeSessionId]);

  const handlePauseTask = useCallback(() => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId ? { ...s, status: 'paused' } : s
      )
    );
    setTerminalOutput((prev) => [
      ...prev,
      { output: '\n> Task paused.', is_stderr: false },
    ]);
  }, [activeSessionId]);

  return (
    <div className="flex h-screen w-full">
      {/* Panel 1: Chat / Task Input */}
      <div className="w-72 flex-shrink-0 h-full">
        <ChatPanel
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId}
          onRunTask={handleRunTask}
          onStopTask={handleStopTask}
          onPauseTask={handlePauseTask}
        />
      </div>

      {/* Panel 2: Workspace (tabs) */}
      <div className="flex-1 h-full min-w-0">
        <WorkspacePanel
          terminalOutput={terminalOutput}
          browserUrl={browserUrl}
          files={files}
          codeContent={codeContent}
          codeLanguage={codeLanguage}
          plan={plan}
        />
      </div>

      {/* Panel 3: Status / Analytics */}
      <div className="w-72 flex-shrink-0 h-full">
        <StatusPanel
          sessions={sessions}
          activeSessionId={activeSessionId}
          agents={agents}
          result={result}
          budget={DEFAULT_BUDGET}
        />
      </div>
    </div>
  );
}
