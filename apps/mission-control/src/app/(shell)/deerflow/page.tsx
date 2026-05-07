'use client';
import { useState, useRef, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { chatDeerFlow } from '@/lib/api';
import { Send, Bot, User, Sparkles, Loader2 } from 'lucide-react';

interface Msg { role: 'user' | 'assistant' | 'system'; content: string; id: string }

export default function DeerFlowPage() {
  const [messages, setMessages] = useState<Msg[]>([
    { role: 'system', content: 'You are DeerFlow, a sovereign AI assistant running on local models. You help with coding, analysis, and creative tasks. You have access to web search, code execution, and memory.', id: 'sys-0' },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }, [messages]);

  const send = useCallback(async () => {
    if (!input.trim() || sending) return;
    const userMsg: Msg = { role: 'user', content: input.trim(), id: `u-${Date.now()}` };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setSending(true);
    setStreaming(true);

    try {
      const apiMessages = [...messages, userMsg].filter((m) => m.role !== 'system').map((m) => ({ role: m.role, content: m.content }));
      const res = await chatDeerFlow(apiMessages, 'deerflow-dash');
      
      // Simulate streaming by adding character by character
      const fullContent = res.content || '';
      const assistantId = `a-${Date.now()}`;
      setMessages((m) => [...m, { role: 'assistant', content: '', id: assistantId }]);
      
      let i = 0;
      const chunkSize = 3;
      const interval = setInterval(() => {
        i += chunkSize;
        if (i >= fullContent.length) {
          clearInterval(interval);
          setMessages((m) => m.map((msg) => msg.id === assistantId ? { ...msg, content: fullContent } : msg));
          setStreaming(false);
          setSending(false);
        } else {
          setMessages((m) => m.map((msg) => msg.id === assistantId ? { ...msg, content: fullContent.slice(0, i) } : msg));
        }
      }, 15);
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${e instanceof Error ? e.message : 'Failed'}`, id: `e-${Date.now()}` }]);
      setStreaming(false);
      setSending(false);
    }
  }, [input, sending, messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4">
      <div className="flex items-center gap-3">
        <Bot className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">DeerFlow Chat</h2>
          <p className="text-xs text-muted">Sovereign LLM with local fallback · Streaming enabled</p>
        </div>
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.filter((m) => m.role !== 'system').map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15">
                  <Sparkles className="h-3.5 w-3.5 text-accent" />
                </div>
              )}
              <div className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-accent text-white'
                  : 'bg-panel-2 text-text border border-line'
              }`}>
                <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
                {msg.role === 'assistant' && streaming && msg.content.length > 0 && !messages[messages.length - 1]?.content && (
                  <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-accent" />
                )}
              </div>
              {msg.role === 'user' && (
                <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-panel-2 border border-line">
                  <User className="h-3.5 w-3.5 text-muted" />
                </div>
              )}
            </div>
          ))}
          {sending && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="flex gap-3">
              <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
              </div>
              <div className="rounded-lg bg-panel-2 px-4 py-2.5 text-sm text-muted border border-line">
                Thinking...
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-line p-3">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything... (Shift+Enter for newline)"
              rows={1}
              className="flex-1 resize-none rounded-md border border-line bg-panel-2 px-3 py-2 text-sm text-text placeholder-muted outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
              style={{ minHeight: '40px', maxHeight: '120px' }}
            />
            <Button onClick={send} disabled={sending || !input.trim()} variant="primary" className="shrink-0 self-end h-10 w-10 p-0">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
