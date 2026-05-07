'use client';
import { useState, useCallback } from 'react';
import ReactFlow, {
  Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState, type Edge, type Connection
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card } from '@/components/ui/Card';
import { GitBranch, Plus, Trash2, Play, Save } from 'lucide-react';

const nodeTypes = [
  { type: 'start', label: 'Start', color: 'bg-green-500' },
  { type: 'agent', label: 'Agent', color: 'bg-accent' },
  { type: 'llm', label: 'LLM Call', color: 'bg-accent-2' },
  { type: 'tool', label: 'Tool', color: 'bg-warn' },
  { type: 'output', label: 'Output', color: 'bg-ok' },
];

const initialNodes = [
  { id: '1', type: 'default', position: { x: 250, y: 50 }, data: { label: 'Start' }, style: { background: '#22c55e', color: '#fff', borderRadius: 8, padding: 10, fontSize: 12, border: '1px solid #1e293b' } },
  { id: '2', type: 'default', position: { x: 250, y: 150 }, data: { label: 'Agent: Web Search' }, style: { background: '#8b5cf6', color: '#fff', borderRadius: 8, padding: 10, fontSize: 12, border: '1px solid #1e293b' } },
  { id: '3', type: 'default', position: { x: 100, y: 250 }, data: { label: 'LLM: Summarize' }, style: { background: '#6366f1', color: '#fff', borderRadius: 8, padding: 10, fontSize: 12, border: '1px solid #1e293b' } },
  { id: '4', type: 'default', position: { x: 400, y: 250 }, data: { label: 'Tool: Code Exec' }, style: { background: '#f59e0b', color: '#000', borderRadius: 8, padding: 10, fontSize: 12, border: '1px solid #1e293b' } },
  { id: '5', type: 'default', position: { x: 250, y: 350 }, data: { label: 'Output' }, style: { background: '#22c55e', color: '#fff', borderRadius: 8, padding: 10, fontSize: 12, border: '1px solid #1e293b' } },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#8b5cf6' } },
  { id: 'e2-3', source: '2', target: '3', animated: true, style: { stroke: '#6366f1' } },
  { id: 'e2-4', source: '2', target: '4', animated: true, style: { stroke: '#f59e0b' } },
  { id: 'e3-5', source: '3', target: '5', animated: true, style: { stroke: '#22c55e' } },
  { id: 'e4-5', source: '4', target: '5', animated: true, style: { stroke: '#22c55e' } },
];

let idCounter = 6;

export default function WorkflowPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: '#8b5cf6' } }, eds)),
    [setEdges]
  );

  const addNode = (type: string, color: string) => {
    const id = `${idCounter++}`;
    const isLight = color === 'bg-warn';
    setNodes((nds) => [...nds, {
      id,
      type: 'default',
      position: { x: 200 + Math.random() * 200, y: 100 + Math.random() * 200 },
      data: { label: type },
      style: {
        background: color.replace('bg-', '').replace('green-500', '#22c55e').replace('accent', '#8b5cf6').replace('accent-2', '#6366f1').replace('warn', '#f59e0b').replace('ok', '#22c55e'),
        color: isLight ? '#000' : '#fff',
        borderRadius: 8,
        padding: 10,
        fontSize: 12,
        border: '1px solid #1e293b',
      },
    }]);
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="h-5 w-5 text-accent" />
          <div>
            <h2 className="text-sm font-semibold text-text">Workflow Builder</h2>
            <p className="text-xs text-muted">Drag and drop agentic workflow nodes</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setNodes(initialNodes)} className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-text transition-colors">
            <Trash2 className="h-3 w-3" /> Reset
          </button>
          <button className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-text transition-colors">
            <Play className="h-3 w-3" /> Run
          </button>
          <button className="inline-flex items-center gap-1 rounded-md bg-accent px-2 py-1 text-xs text-white hover:bg-accent/80 transition-colors">
            <Save className="h-3 w-3" /> Save
          </button>
        </div>
      </div>

      <div className="flex flex-1 gap-4">
        <Card className="w-48 shrink-0 flex flex-col gap-2 p-3">
          <div className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Add Node</div>
          {nodeTypes.map((nt) => (
            <button
              key={nt.type}
              onClick={() => addNode(nt.label, nt.color)}
              className="flex items-center gap-2 rounded-md border border-line bg-panel-2 px-3 py-2 text-xs text-text hover:border-accent transition-colors"
            >
              <Plus className="h-3 w-3" />
              {nt.label}
            </button>
          ))}
        </Card>

        <Card className="flex-1 overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            style={{ background: '#070a12' }}
          >
            <Background color="#1e293b" gap={20} size={1} />
            <Controls />
            <MiniMap
              nodeColor={(n) => n.style?.background as string || '#8b5cf6'}
              maskColor="rgba(7, 10, 18, 0.8)"
              className="!bg-panel !border-line"
            />
          </ReactFlow>
        </Card>
      </div>
    </div>
  );
}
