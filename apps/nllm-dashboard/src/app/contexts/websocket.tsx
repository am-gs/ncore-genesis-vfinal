'use client';

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react';
import { TaskPlan, AgentResult, TaskResult, AgentStatus, WSMessage } from '@/app/types';

interface WebSocketContextType {
  isConnected: boolean;
  plan: TaskPlan | null;
  results: AgentResult[];
  taskResult: TaskResult | null;
  agentStatuses: AgentStatus[];
  sendTask: (task: string) => void;
  stopTask: () => void;
  pauseTask: () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:3001/ws';
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnected] = useState(false);
  const [plan, setPlan] = useState<TaskPlan | null>(null);
  const [results, setResults] = useState<AgentResult[]>([]);
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  useEffect(() => {
    const websocket = new WebSocket(WS_URL);

    websocket.onopen = () => {
      setIsConnected(true);
    };

    websocket.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);

        switch (data.type) {
          case 'task_start':
            setPlan(data.plan);
            setResults([]);
            setTaskResult(null);
            setAgentStatuses([]);
            setCurrentTaskId(data.task_id);
            break;

          case 'agent_update':
            setAgentStatuses((prev) => {
              const existing = prev.findIndex((a) => a.role === data.agent.role);
              if (existing >= 0) {
                const next = [...prev];
                next[existing] = data.agent;
                return next;
              }
              return [...prev, data.agent];
            });
            break;

          case 'completion':
            setTaskResult(data.result);
            setCurrentTaskId(null);
            break;

          case 'error':
            console.error('Task error:', data.error);
            break;

          case 'connected':
            console.log('WS connected, client:', data.client_id);
            break;
        }
      } catch (e) {
        console.error('WS message parse error:', e);
      }
    };

    websocket.onclose = () => {
      setIsConnected(false);
    };

    websocket.onerror = (err) => {
      console.error('WebSocket error:', err);
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, []);

  const sendTask = useCallback(
    (task: string) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'run_task', task }));
      }
      // Also trigger via HTTP for reliability
      fetch(`${API_URL}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });
    },
    [ws]
  );

  const stopTask = useCallback(() => {
    if (ws && ws.readyState === WebSocket.OPEN && currentTaskId) {
      ws.send(JSON.stringify({ type: 'stop_task', task_id: currentTaskId }));
    }
    fetch(`${API_URL}/tasks/${currentTaskId}/stop`, {
      method: 'POST',
    });
  }, [ws, currentTaskId]);

  const pauseTask = useCallback(() => {
    if (ws && ws.readyState === WebSocket.OPEN && currentTaskId) {
      ws.send(JSON.stringify({ type: 'pause_task', task_id: currentTaskId }));
    }
    fetch(`${API_URL}/tasks/${currentTaskId}/pause`, {
      method: 'POST',
    });
  }, [ws, currentTaskId]);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        plan,
        results,
        taskResult,
        agentStatuses,
        sendTask,
        stopTask,
        pauseTask,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
}
