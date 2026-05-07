'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { chatDeerFlow } from '@/lib/api';
import {
  Code, Folder, FileText, Terminal, Send, Play, Pause,
  RotateCcw, Save, ChevronRight, ChevronDown, Cpu, Zap
} from 'lucide-react';

interface FileNode {
  name: string;
  type: 'file' | 'dir';
  content?: string;
  language?: string;
  children?: FileNode[];
}

const fileTree: FileNode[] = [
  {
    name: 'workspace',
    type: 'dir',
    children: [
      {
        name: 'skills',
        type: 'dir',
        children: [
          { name: 'web-search', type: 'dir', children: [{ name: 'SKILL.md', type: 'file', language: 'markdown', content: '# Web Search Skill\n\nSearch the web for information.' }] },
          { name: 'code-review', type: 'dir', children: [{ name: 'SKILL.md', type: 'file', language: 'markdown', content: '# Code Review Skill\n\nReview code for quality.' }] },
          { name: 'deploy', type: 'dir', children: [{ name: 'SKILL.md', type: 'file', language: 'markdown', content: '# Deploy Skill\n\nDeploy to production.' }] },
        ]
      },
      {
        name: 'agents',
        type: 'dir',
        children: [
          { name: 'research-agent.yml', type: 'file', language: 'yaml', content: 'name: research-agent\nprompt: Research specialist for web scraping\ntools:\n  - web-search\n  - browser\n' },
          { name: 'code-agent.yml', type: 'file', language: 'yaml', content: 'name: code-agent\nprompt: Senior engineer for full-stack dev\ntools:\n  - code-edit\n  - terminal\n' },
        ]
      },
      { name: 'main.py', type: 'file', language: 'python', content: '#!/usr/bin/env python3\n"""\nSovereign Mission Control - Cognitive Infrastructure\n"""\nimport asyncio\nfrom typing import List, Dict\n\nclass Agent:\n    def __init__(self, name: str):\n        self.name = name\n        self.memory = []\n        \n    async def think(self, prompt: str):\n        # Recursive planning with subagent spawning\n        plan = await self.plan(prompt)\n        for step in plan:\n            result = await self.execute(step)\n            self.memory.append(result)\n        return self.memory\n\nif __name__ == "__main__":\n    agent = Agent("cognitive-core")\n    asyncio.run(agent.think("Build a self-healing system"))\n' },
      { name: 'config.json', type: 'file', language: 'json', content: '{\n  "agents": {\n    "max_concurrent": 8,\n    "recursive_depth": 5,\n    "self_healing": true,\n    "browser_grounding": true\n  },\n  "execution": {\n    "durable": true,\n    "resumable": true,\n    "branching": true\n  }\n}' },
    ]
  }
];

interface ConsoleLine {
  type: 'input' | 'output' | 'error' | 'system';
  content: string;
  timestamp: string;
}

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
  id: string;
  toolCalls?: { name: string; args: string; status: 'running' | 'done' | 'error' }[];
}

export default function WorkspacePage() {
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [editorContent, setEditorContent] = useState('');
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['workspace', 'workspace/skills', 'workspace/agents']));
  const [consoleLines, setConsoleLines] = useState<ConsoleLine[]>([
    { type: 'system', content: 'Sovereign Cognitive Infrastructure v1.0.0', timestamp: '00:00:00' },
    { type: 'system', content: 'Initializing agent workspace...', timestamp: '00:00:01' },
    { type: 'output', content: '✓ Agent registry loaded (3 agents)', timestamp: '00:00:02' },
    { type: 'output', content: '✓ Skill catalog loaded (12 skills)', timestamp: '00:00:02' },
    { type: 'system', content: 'Ready. Type "help" for commands.', timestamp: '00:00:03' },
  ]);
  const [consoleInput, setConsoleInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const consoleRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (consoleRef.current) consoleRef.current.scrollTop = consoleRef.current.scrollHeight; }, [consoleLines]);

  const toggleDir = (path: string) => {
    const next = new Set(expandedDirs);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setExpandedDirs(next);
  };

  const onFileClick = (file: FileNode) => {
    if (file.type === 'dir') { toggleDir(file.name); return; }
    setSelectedFile(file);
    setEditorContent(file.content || '');
  };

  const runConsole = () => {
    if (!consoleInput.trim()) return;
    const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
    setConsoleLines(prev => [...prev, { type: 'input', content: `> ${consoleInput}`, timestamp: ts }]);
    
    const cmd = consoleInput.trim();
    setTimeout(() => {
      if (cmd === 'help') {
        setConsoleLines(prev => [...prev,
          { type: 'output', content: 'Available commands:', timestamp: ts },
          { type: 'output', content: '  agent <name>    - Spawn agent', timestamp: ts },
          { type: 'output', content: '  task <prompt>   - Create task', timestamp: ts },
          { type: 'output', content: '  status          - System status', timestamp: ts },
          { type: 'output', content: '  skills            - List skills', timestamp: ts },
          { type: 'output', content: '  clear             - Clear console', timestamp: ts },
        ]);
      } else if (cmd === 'status') {
        setConsoleLines(prev => [...prev,
          { type: 'output', content: '┌─ System Status ─────────────────┐', timestamp: ts },
          { type: 'output', content: '│ Agents: 3 active, 0 pending     │', timestamp: ts },
          { type: 'output', content: '│ Tasks: 1 running, 2 completed   │', timestamp: ts },
          { type: 'output', content: '│ Memory: 1,247 entries           │', timestamp: ts },
          { type: 'output', content: '│ Skills: 12 loaded               │', timestamp: ts },
          { type: 'output', content: '└─────────────────────────────────┘', timestamp: ts },
        ]);
      } else if (cmd === 'clear') {
        setConsoleLines([]);
      } else if (cmd.startsWith('agent ')) {
        const name = cmd.slice(6);
        setConsoleLines(prev => [...prev,
          { type: 'system', content: `Spawning agent "${name}"...`, timestamp: ts },
          { type: 'output', content: `✓ Agent ${name} initialized with durable execution context`, timestamp: ts },
          { type: 'output', content: `✓ Persistent state attached (mem0)` , timestamp: ts },
          { type: 'output', content: `✓ Browser grounding enabled`, timestamp: ts },
        ]);
      } else if (cmd.startsWith('task ')) {
        const prompt = cmd.slice(5);
        setConsoleLines(prev => [...prev,
          { type: 'system', content: `Creating task: "${prompt}"`, timestamp: ts },
          { type: 'output', content: `✓ Task planned (recursive depth: 3)`, timestamp: ts },
          { type: 'output', content: `✓ Subagents spawned: research-agent, code-agent`, timestamp: ts },
          { type: 'output', content: `→ Executing...`, timestamp: ts },
        ]);
      } else {
        setConsoleLines(prev => [...prev, { type: 'error', content: `Command not found: ${cmd}`, timestamp: ts }]);
      }
    }, 200);
    setConsoleInput('');
  };

  const sendChat = useCallback(async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg: ChatMsg = { role: 'user', content: chatInput.trim(), id: `u-${Date.now()}` };
    setChatMessages(m => [...m, userMsg]);
    setChatInput('');
    setChatLoading(true);

    try {
      const apiMessages = chatMessages.concat(userMsg).map(m => ({ role: m.role, content: m.content }));
      const res = await chatDeerFlow(apiMessages, 'workspace');
      
      // Simulate tool calls
      const toolCalls = [
        { name: 'plan', args: 'recursive_plan: true, depth: 3', status: 'done' as const },
        { name: 'spawn_subagent', args: 'research-agent for context gathering', status: 'done' as const },
        { name: 'browser_grounding', args: 'verify with screenshot', status: 'running' as const },
      ];

      const assistantId = `a-${Date.now()}`;
      setChatMessages(m => [...m, { role: 'assistant', content: '', id: assistantId, toolCalls }]);
      
      const fullContent = res.content || '';
      let i = 0;
      const interval = setInterval(() => {
        i += 4;
        if (i >= fullContent.length) {
          clearInterval(interval);
          setChatMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, content: fullContent, toolCalls: toolCalls?.map(t => ({ ...t, status: 'done' as const })) } : msg));
          setChatLoading(false);
        } else {
          setChatMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, content: fullContent.slice(0, i) } : msg));
        }
      }, 12);
    } catch (e) {
      setChatMessages(m => [...m, { role: 'assistant', content: `Error: ${e instanceof Error ? e.message : 'Failed'}`, id: `e-${Date.now()}` }]);
      setChatLoading(false);
    }
  }, [chatInput, chatLoading, chatMessages]);

  const renderTree = (nodes: FileNode[], path: string = '') => {
    return nodes.map(node => {
      const fullPath = path ? `${path}/${node.name}` : node.name;
      const isExpanded = expandedDirs.has(fullPath);
      return (
        <div key={fullPath}>
          <button
            onClick={() => onFileClick(node)}
            className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition-all ${
              selectedFile?.name === node.name && node.type === 'file'
                ? 'bg-gradient-to-r from-violet-500/15 to-indigo-500/10 text-violet-300'
                : 'text-muted hover:bg-white/[0.03] hover:text-text'
            }`}
          >
            {node.type === 'dir' ? (
              <>
                {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                <Folder className="h-3.5 w-3.5 text-amber-400/60" />
              </>
            ) : (
              <>
                <span className="w-3.5" />
                <FileText className="h-3.5 w-3.5 text-cyan-400/60" />
              </>
            )}
            <span className="truncate">{node.name}</span>
          </button>
          {node.type === 'dir' && isExpanded && node.children && (
            <div className="ml-4 border-l border-white/[0.04] pl-2">
              {renderTree(node.children, fullPath)}
            </div>
          )}
        </div>
      );
    });
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4 animate-slide-up">
      {/* File Tree */}
      <Card className="w-56 shrink-0 flex flex-col overflow-hidden border-white/[0.06] bg-[rgba(10,15,28,0.8)] backdrop-blur-xl">
        <div className="flex items-center gap-2 border-b border-white/[0.06] p-3">
          <Folder className="h-4 w-4 text-muted" />
          <span className="text-xs font-semibold text-text">Explorer</span>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {renderTree(fileTree)}
        </div>
      </Card>

      {/* Main: Editor + Console + Chat */}
      <div className="flex flex-1 flex-col gap-3 overflow-hidden">
        {/* Editor */}
        <Card className="flex-1 flex flex-col overflow-hidden border-white/[0.06] bg-[rgba(10,15,28,0.6)] backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2">
            <div className="flex items-center gap-2">
              <Code className="h-4 w-4 text-cyan-400" />
              <span className="text-xs font-mono text-text">{selectedFile?.name || 'main.py'}</span>
              {selectedFile?.type === 'file' && (
                <span className="text-[10px] text-muted">{selectedFile.language}</span>
              )}
            </div>
            <div className="flex gap-1.5">
              <button className="rounded-lg p-1.5 text-muted hover:text-text hover:bg-white/[0.04] transition-all"><Save className="h-3.5 w-3.5" /></button>
              <button className="rounded-lg p-1.5 text-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all"><Play className="h-3.5 w-3.5" /></button>
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            <Editor
              height="100%"
              defaultLanguage="python"
              language={selectedFile?.language === 'json' ? 'json' : selectedFile?.language === 'yaml' ? 'yaml' : selectedFile?.language === 'markdown' ? 'markdown' : 'python'}
              value={editorContent}
              onChange={v => setEditorContent(v || '')}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: 'on',
                roundedSelection: false,
                scrollBeyondLastLine: false,
                automaticLayout: true,
                padding: { top: 16 },
                fontFamily: 'JetBrains Mono, monospace',
              }}
            />
          </div>
        </Card>

        {/* Bottom: Console + Chat */}
        <div className="flex gap-3 h-56 shrink-0">
          {/* Terminal */}
          <Card className="flex-1 flex flex-col overflow-hidden border-white/[0.06] bg-[rgba(10,15,28,0.9)] backdrop-blur-xl">
            <div className="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2">
              <Terminal className="h-3.5 w-3.5 text-muted" />
              <span className="text-[11px] font-semibold text-muted uppercase tracking-wider">Terminal</span>
              <div className="ml-auto flex gap-1">
                <button className="rounded p-1 text-muted hover:text-text hover:bg-white/[0.04] transition-all"><RotateCcw className="h-3 w-3" /></button>
              </div>
            </div>
            <div ref={consoleRef} className="flex-1 overflow-y-auto p-3 font-mono text-[11px]">
              {consoleLines.map((line, i) => (
                <div key={i} className={`mb-0.5 ${
                  line.type === 'input' ? 'text-violet-300' :
                  line.type === 'error' ? 'text-rose-400' :
                  line.type === 'system' ? 'text-amber-400' :
                  'text-text-secondary'
                }`}>
                  <span className="text-muted/40 mr-2">{line.timestamp}</span>
                  {line.content}
                </div>
              ))}
            </div>
            <div className="border-t border-white/[0.06] p-2">
              <div className="flex items-center gap-2">
                <span className="text-violet-400 font-mono text-xs">&gt;</span>
                <input
                  value={consoleInput}
                  onChange={e => setConsoleInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && runConsole()}
                  placeholder="agent research-agent | task build self-healing system | help"
                  className="flex-1 bg-transparent text-xs font-mono text-text placeholder-muted/40 outline-none"
                />
              </div>
            </div>
          </Card>

          {/* Agent Chat */}
          <Card className="w-80 shrink-0 flex flex-col overflow-hidden border-white/[0.06] bg-[rgba(10,15,28,0.8)] backdrop-blur-xl">
            <div className="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2">
              <Cpu className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-[11px] font-semibold text-muted uppercase tracking-wider">Agent Chat</span>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {chatMessages.length === 0 && (
                <div className="text-center py-8">
                  <Zap className="h-8 w-8 text-violet-500/20 mx-auto mb-2" />
                  <div className="text-xs text-muted">Ask the cognitive agent</div>
                  <div className="text-[10px] text-muted/60 mt-1">It can spawn subagents, browse, code</div>
                </div>
              )}
              {chatMessages.map(msg => (
                <div key={msg.id} className={`${msg.role === 'user' ? 'ml-4' : ''}`}>
                  <div className={`rounded-xl px-3 py-2 text-xs ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white'
                      : 'bg-white/[0.04] text-text border border-white/[0.06]'
                  }`}>
                    <pre className="whitespace-pre-wrap font-sans text-xs">{msg.content}</pre>
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="mt-2 space-y-1 border-t border-white/[0.06] pt-2">
                        {msg.toolCalls.map(tool => (
                          <div key={tool.name} className="flex items-center gap-2 text-[10px]">
                            <span className={`h-1.5 w-1.5 rounded-full ${
                              tool.status === 'done' ? 'bg-emerald-400' :
                              tool.status === 'error' ? 'bg-rose-400' :
                              'bg-amber-400 animate-pulse'
                            }`} />
                            <span className="text-muted font-mono">{tool.name}</span>
                            <span className="text-muted/60">{tool.args}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && chatMessages[chatMessages.length - 1]?.role !== 'assistant' && (
                <div className="flex gap-2 items-center text-xs text-muted">
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse delay-100" />
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse delay-200" />
                  <span>Thinking...</span>
                </div>
              )}
            </div>
            <div className="border-t border-white/[0.06] p-2">
              <div className="flex gap-2">
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendChat()}
                  placeholder="Spawn an agent, plan a task..."
                  className="flex-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-text placeholder-muted/40 outline-none focus:border-violet-500/30 transition-all"
                />
                <button onClick={sendChat} disabled={chatLoading} className="rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 p-2 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all disabled:opacity-50">
                  <Send className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
