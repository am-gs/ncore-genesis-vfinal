'use client';

import { useState, useRef, useEffect } from 'react';
import { useWebSocket } from '@/app/contexts/websocket';
import { Button } from '@/app/components/ui/button';
import { Input } from '@/app/components/ui/input';
import { ScrollArea } from '@/app/components/ui/scroll-area';
import { Badge } from '@/app/components/ui/badge';
import {
  Play, Square, Circle, CheckCircle, AlertCircle, Clock,
  Send, Zap, Pause
} from 'lucide-react';
import { Session } from '@/app/types';

export function ChatPanel({
  sessions,
  activeSessionId,
  onSelectSession,
  onRunTask,
  onStopTask,
  onPauseTask,
}: {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onRunTask: (task: string) => void;
  onStopTask: () => void;
  onPauseTask: () => void;
}) {
  const { isConnected } = useWebSocket();
  const [taskInput, setTaskInput] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const isSessionActive = activeSession?.status === 'active';

  const handleRun = () => {
    if (!taskInput.trim()) return;
    setIsRunning(true);
    onRunTask(taskInput.trim());
    setTaskInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (isSessionActive) {
        onStopTask();
      } else {
        handleRun();
      }
    }
  };

  useEffect(() => {
    if (activeSession && activeSession.status !== 'active') {
      setIsRunning(false);
    }
  }, [activeSession]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <Circle className="h-3 w-3 text-accent animate-pulse" />;
      case 'completed': return <CheckCircle className="h-3 w-3 text-ok" />;
      case 'error': return <AlertCircle className="h-3 w-3 text-bad" />;
      case 'paused': return <Pause className="h-3 w-3 text-warn" />;
      default: return <Clock className="h-3 w-3 text-text-tertiary" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-panel border-r border-line">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-accent" />
          <h2 className="font-semibold text-sm">NLLM.ING</h2>
        </div>
        <Badge
          variant={isConnected ? 'default' : 'destructive'}
          className="text-[10px] px-1.5 py-0"
        >
          {isConnected ? 'Live' : 'Offline'}
        </Badge>
      </div>

      {/* Task Input */}
      <div className="p-3 border-b border-line space-y-2">
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your task..."
            className="w-full h-24 rounded-lg border border-line bg-bg-2 px-3 py-2 text-sm
                       placeholder:text-text-tertiary resize-none focus:outline-none
                       focus:ring-1 focus:ring-accent transition-all"
          />
          <div className="absolute bottom-2 right-2 text-[10px] text-text-tertiary">
            {taskInput.length} chars
          </div>
        </div>
        <div className="flex gap-2">
          {isSessionActive ? (
            <>
              <Button
                onClick={onPauseTask}
                variant="outline"
                size="sm"
                className="flex-1"
              >
                <Pause className="h-3.5 w-3.5 mr-1" />
                Pause
              </Button>
              <Button
                onClick={onStopTask}
                variant="destructive"
                size="sm"
                className="flex-1"
              >
                <Square className="h-3.5 w-3.5 mr-1" />
                Stop
              </Button>
            </>
          ) : (
            <Button
              onClick={handleRun}
              disabled={!taskInput.trim() || !isConnected}
              size="sm"
              className="flex-1 bg-ok hover:bg-ok/90 text-white"
            >
              <Send className="h-3.5 w-3.5 mr-1" />
              Run Task
            </Button>
          )}
        </div>
      </div>

      {/* Session History */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="p-2">
            <h3 className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium px-2 mb-1">
              Sessions
            </h3>
            <div className="space-y-0.5">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => onSelectSession(session.id)}
                  className={`flex items-center gap-2 px-2 py-2 rounded-md cursor-pointer
                    transition-colors text-sm
                    ${activeSessionId === session.id
                      ? 'bg-accent/10 border border-accent/20'
                      : 'hover:bg-bg-2 border border-transparent'
                    }`}
                >
                  {getStatusIcon(session.status)}
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-xs font-medium">{session.title}</p>
                    <p className="text-[10px] text-text-tertiary">
                      {new Date(session.createdAt).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              ))}
              {sessions.length === 0 && (
                <div className="px-2 py-4 text-center text-xs text-text-tertiary">
                  No sessions yet. Enter a task above.
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
