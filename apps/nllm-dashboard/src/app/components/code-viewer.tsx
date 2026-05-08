'use client';

import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

function detectLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', jsx: 'jsx',
    tsx: 'tsx', rs: 'rust', go: 'go', rb: 'ruby', php: 'php',
    java: 'java', cpp: 'cpp', c: 'c', cs: 'csharp', swift: 'swift',
    kt: 'kotlin', scala: 'scala', md: 'markdown', json: 'json',
    yaml: 'yaml', yml: 'yaml', sql: 'sql', sh: 'bash', html: 'html',
    css: 'css', scss: 'scss', dockerfile: 'dockerfile',
  };
  return map[ext] || 'text';
}

function highlightCode(code: string, language: string): string {
  // Minimal syntax highlighting via regex (real app would use Prism/HLJS)
  let highlighted = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Comments
  if (['python', 'bash', 'sh', 'ruby'].includes(language)) {
    highlighted = highlighted.replace(/(#.*$)/gm, '<span style="color:#6b7280">$1</span>');
  } else {
    highlighted = highlighted.replace(/(\/\/.*$)/gm, '<span style="color:#6b7280">$1</span>');
    highlighted = highlighted.replace(/(\/\*[\s\S]*?\*\/)/g, '<span style="color:#6b7280">$1</span>');
  }

  // Strings
  highlighted = highlighted.replace(
    /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/g,
    '<span style="color:#22c55e">$1</span>'
  );

  // Keywords
  const keywords = ['def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif',
    'for', 'while', 'try', 'except', 'async', 'await', 'const', 'let', 'var',
    'function', 'export', 'default', 'interface', 'type', 'implements'];
  const kwPattern = new RegExp(`\\b(${keywords.join('|')})\\b`, 'g');
  highlighted = highlighted.replace(kwPattern, '<span style="color:#60a5fa">$1</span>');

  // Numbers
  highlighted = highlighted.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#f59e0b">$1</span>');

  return highlighted;
}

export function CodeViewer({
  content,
  language,
  filename = 'untitled',
}: {
  content: string;
  language: string;
  filename?: string;
}) {
  const [copied, setCopied] = useState(false);
  const lines = content.split('\n');
  const detectedLang = language || detectLanguage(filename);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full flex flex-col bg-[#0d0d0d]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#1a1a1a] border-b border-[#2a2a2a]">
        <span className="text-[10px] text-[#888] uppercase tracking-wider">
          {detectedLang}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] text-[#888] hover:text-white transition-colors"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" /> Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" /> Copy
            </>
          )}
        </button>
      </div>

      {/* Code */}
      <div className="flex-1 overflow-auto">
        {content ? (
          <div className="flex">
            {/* Line numbers */}
            <div className="select-none text-right pr-3 py-3 bg-[#0d0d0d] text-[#444] text-[13px] leading-relaxed font-mono min-w-[3rem]">
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            {/* Code */}
            <pre className="flex-1 py-3 pr-4 text-[13px] leading-relaxed font-mono whitespace-pre text-[#e5e5e5]">
              <code
                dangerouslySetInnerHTML={{
                  __html: highlightCode(content, detectedLang),
                }}
              />
            </pre>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-[#555] text-sm">
            No code to display
          </div>
        )}
      </div>
    </div>
  );
}
