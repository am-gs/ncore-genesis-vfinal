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
  { type: 'start', label: 'Start', color: '#22c55e' },
  { type: 'agent', label: 'Agent', color: '#8b5cf6' },
  { type: 'llm', label: 'LLM Call', color: '#6366f1' },
  { type: 'tool', label: 'Tool', color: '#f59e0b' },
  { type: 'output', label: 'Output', color: '#22c55e' },
];

const initialNodes = [
  { id: '1', type: 'default', position: { x: 250, y: 50 }, data: { label: 'Start' }, style: { background: '#22c55e', color: '#fff', borderRadius: 12, padding: '10px 16px', fontSize: 12, border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 } },
  { id: '2', type: 'default', position: { x: 250, y: 150 }, data: { label: 'Agent: Web Search' }, style: { background: '#8b5cf6', color: '#fff', borderRadius: 12, padding: '10px 16px', fontSize: 12, border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 } },
  { id: '3', type: 'default', position: { x: 100, y: 250 }, data: { label: 'LLM: Summarize' }, style: { background: '#6366f1', color: '#fff', borderRadius: 12, padding: '10px 16px', fontSize: 12, border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 } },
  { id: '4', type: 'default', position: { x: 400, y: 250 }, data: { label: 'Tool: Code Exec' }, style: { background: '#f59e0b', color: '#000', borderRadius: 12, padding: '10px 16px', fontSize: 12, border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 } },
  { id: '5', type: 'default', position: { x: 250, y: 350 }, data: { label: 'Output' }, style: { background: '#22c55e', color: '#fff', borderRadius: 12, padding: '10px 16px', fontSize: 12, border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 } },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#8b5cf6', strokeWidth: 2 } },
  { id: 'e2-3', source: '2', target: '3', animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } },
  { id: 'e2-4', source: '2', target: '4', animated: true, style: { stroke: '#f59e0b', strokeWidth: 2 } },
  { id: 'e3-5', source: '3', target: '5', animated: true, style: { stroke: '#22c55e', strokeWidth: 2 } },
  { id: 'e4-5', source: '4', target: '5', animated: true, style: { stroke: '#22c55e', strokeWidth: 2 } },
];

let idCounter = 6;

export default function WorkflowPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges(eds => addEdge({ ...params, animated: true, style: { stroke: '#8b5cf6', strokeWidth: 2 } }, eds)),
    [setEdges]
  );

  const addNode = (label: string, color: string) => {
    const id = `${idCounter++}`;
    setNodes(nds => [...nds, {
      id, type: 'default',
      position: { x: 200 + Math.random() * 200, y: 100 + Math.random() * 200 },
      data: { label },
      style: { background: color, color: color === '#f59e0b' ? '#000' : '#fff', borderRadius: 12, padding: '10px 16px', fontSize: 12, border: '1px solid rgba(255,255,255,0.1)', fontWeight: 600 },
    }]);
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4 animate-slide-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 shadow-lg shadow-violet-500/20">
            <GitBranch className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-text tracking-tight">Workflow Builder</h2>
            <p className="text-xs text-muted">Drag and drop agentic workflow nodes</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { setNodes(initialNodes); setEdges(initialEdges); }} className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
            <Trash2 className="h-3.5 w-3.5" /> Reset
          </button>
          <button className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
            <Play className="h-3.5 w-3.5" /> Run
          </button>
          <button className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 px-3 py-2 text-xs text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all">
            <Save className="h-3.5 w-3.5" /> Save
          </button>
        </div>
      </div>

      <div className="flex flex-1 gap-4">
        <Card className="w-52 shrink-0 flex flex-col gap-2 p-4 border-white/[0.06] bg-[rgba(15,23,42,0.5)] backdrop-blur-xl">
          <div className="text-[11px] font-semibold text-muted uppercase tracking-[0.12em] mb-2">Add Node</div>
          {nodeTypes.map(nt => (
            <button key={nt.type} onClick={() => addNode(nt.label, nt.color)}
              className="flex items-center gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5 text-xs text-text hover:bg-white/[0.06] hover:border-white/[0.1] transition-all"
            >
              <Plus className="h-3.5 w-3.5 text-muted" />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: nt.color }} />
              {nt.label}
            </button>
          ))}
        </Card>

        <Card className="flex-1 overflow-hidden border-white/[0.06] bg-[rgba(10,15,28,0.8)] backdrop-blur-xl">
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} fitView
            style={{ background: 'transparent' }}
          >
            <Background color="rgba(139,92,246,0.15)" gap={24} size={1} />
            <Controls />
            <MiniMap nodeColor={n => n.style?.background as string || '#8b5cf6'} maskColor="rgba(7,10,18,0.8)" className="!bg-[rgba(15,23,42,0.8)] !border-white/[0.06] !rounded-xl !backdrop-blur-xl" />
          </ReactFlow>
        </Card>
      </div>
    </div>
  );
}
