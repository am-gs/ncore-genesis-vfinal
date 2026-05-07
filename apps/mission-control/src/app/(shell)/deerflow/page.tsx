'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { chatDeerFlow } from '@/lib/api';
import { Send, Sparkles, User, Loader2, Bot } from 'lucide-react';

interface Msg { role: 'user' | 'assistant' | 'system'; content: string; id: string }

export default function DeerFlowPage() {
  const [messages, setMessages] = useState<Msg[]>([
    { role: 'system', content: 'You are DeerFlow, a sovereign AI assistant running on local models. You help with coding, analysis, and creative tasks. You have access to web search, code execution, and memory.', id: 'sys-0' },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }, [messages]);

  const send = useCallback(async () => {
    if (!input.trim() || sending) return;
    const userMsg: Msg = { role: 'user', content: input.trim(), id: `u-${Date.now()}` };
    setMessages(m => [...m, userMsg]);
    setInput('');
    setSending(true);
    setStreaming(true);

    try {
      const apiMessages = [...messages, userMsg].filter(m => m.role !== 'system').map(m => ({ role: m.role, content: m.content }));
      const res = await chatDeerFlow(apiMessages, 'deerflow-dash');
      const fullContent = res.content || '';
      const assistantId = `a-${Date.now()}`;
      setMessages(m => [...m, { role: 'assistant', content: '', id: assistantId }]);
      
      let i = 0;
      const chunkSize = 3;
      const interval = setInterval(() => {
        i += chunkSize;
        if (i >= fullContent.length) {
          clearInterval(interval);
          setMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, content: fullContent } : msg));
          setStreaming(false);
          setSending(false);
        } else {
          setMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, content: fullContent.slice(0, i) } : msg));
        }
      }, 15);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: `Error: ${e instanceof Error ? e.message : 'Failed'}`, id: `e-${Date.now()}` }]);
      setStreaming(false);
      setSending(false);
    }
  }, [input, sending, messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4 animate-slide-up">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 shadow-lg shadow-violet-500/20">
          <Bot className="h-5 w-5 text-white" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-text tracking-tight">DeerFlow Chat</h2>
          <p className="text-xs text-muted">Sovereign LLM with local fallback &middot; Streaming enabled</p>
        </div>
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden border-white/[0.06] bg-[rgba(15,23,42,0.5)] backdrop-blur-xl">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-5">
          {messages.filter(m => m.role !== 'system').map(msg => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 shadow-lg shadow-violet-500/10">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/20'
                  : 'bg-white/[0.04] text-text border border-white/[0.06] backdrop-blur-md'
              }`}>
                <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
                {msg.role === 'assistant' && streaming && msg.content.length > 0 && messages[messages.length-1]?.content === msg.content && (
                  <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-violet-400" />
                )}
              </div>
              {msg.role === 'user' && (
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] border border-white/[0.08]">
                  <User className="h-4 w-4 text-muted" />
                </div>
              )}
            </div>
          ))}
          {sending && messages[messages.length-1]?.role !== 'assistant' && (
            <div className="flex gap-3">
              <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500">
                <Loader2 className="h-4 w-4 animate-spin text-white" />
              </div>
              <div className="rounded-2xl bg-white/[0.04] px-5 py-3.5 text-sm text-muted border border-white/[0.06]">
                <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" /><span>Thinking...</span></div>
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-white/[0.06] p-4">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything... (Shift+Enter for newline)"
              rows={1}
              className="flex-1 resize-none rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text placeholder-muted outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
            <Button onClick={send} disabled={sending || !input.trim()} variant="primary" className="shrink-0 self-end h-12 w-12 rounded-xl p-0">
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
