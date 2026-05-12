'use client';

import { useRef, useEffect } from 'react';
import { LangGraphNode, LangGraphEdge } from '@/app/types/swarm';

interface Props {
  nodes: LangGraphNode[];
  edges: LangGraphEdge[];
}

const NODE_COLORS: Record<string, string> = {
  entry: '#22c55e',
  end: '#6b7280',
  router: '#3b82f6',
  agent: '#8b5cf6',
  critic: '#ef4444',
  checkpoint: '#06b6d4',
};

const NODE_SIZES: Record<string, number> = {
  entry: 18,
  end: 18,
  router: 22,
  agent: 24,
  critic: 24,
  checkpoint: 14,
};

export function LangGraphCanvas({ nodes, edges }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;

    ctx.clearRect(0, 0, w, h);

    // Draw edges
    edges.forEach((edge) => {
      const from = nodes.find((n) => n.id === edge.from);
      const to = nodes.find((n) => n.id === edge.to);
      if (!from || !to) return;

      const sx = (from.x / 900) * w;
      const sy = (from.y / 120) * h;
      const ex = (to.x / 900) * w;
      const ey = (to.y / 120) * h;

      ctx.beginPath();
      ctx.moveTo(sx, sy);

      // Curved bezier
      const cpx = (sx + ex) / 2;
      const cpy = (sy + ey) / 2 + 10;
      ctx.quadraticCurveTo(cpx, cpy, ex, ey);

      const colors: Record<string, string> = {
        pending: '#3f3f46',
        active: '#3b82f6',
        completed: '#22c55e',
        error: '#ef4444',
      };
      ctx.strokeStyle = colors[edge.status] || '#3f3f46';
      ctx.lineWidth = edge.status === 'active' ? 2.5 : 1.5;
      if (edge.status === 'active') {
        ctx.setLineDash([6, 4]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrowhead
      const angle = Math.atan2(ey - cpy, ex - cpx);
      const arrLen = 6;
      ctx.beginPath();
      ctx.moveTo(ex, ey);
      ctx.lineTo(ex - arrLen * Math.cos(angle - 0.3), ey - arrLen * Math.sin(angle - 0.3));
      ctx.lineTo(ex - arrLen * Math.cos(angle + 0.3), ey - arrLen * Math.sin(angle + 0.3));
      ctx.fillStyle = colors[edge.status] || '#3f3f46';
      ctx.fill();

      // Label
      if (edge.label) {
        const mx = (sx + ex) / 2;
        const my = (sy + ey) / 2 + 5;
        ctx.font = '9px var(--font-mono)';
        ctx.fillStyle = '#71717a';
        ctx.textAlign = 'center';
        ctx.fillText(edge.label, mx, my);
      }
    });

    // Draw nodes
    nodes.forEach((node) => {
      const x = (node.x / 900) * w;
      const y = (node.y / 120) * h;
      const size = NODE_SIZES[node.type] || 20;
      const color = NODE_COLORS[node.type] || '#6b7280';

      // Glow for active
      if (node.status === 'active') {
        ctx.beginPath();
        ctx.arc(x, y, size + 6, 0, Math.PI * 2);
        ctx.fillStyle = `${color}20`;
        ctx.fill();
      }

      // Node body
      ctx.beginPath();
      if (node.type === 'checkpoint') {
        ctx.rect(x - size / 2, y - size / 2, size, size);
      } else {
        ctx.arc(x, y, size, 0, Math.PI * 2);
      }
      ctx.fillStyle = node.status === 'active' ? color : `${color}40`;
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = node.status === 'active' ? 2.5 : 1.5;
      ctx.stroke();

      // Label
      ctx.font = '10px var(--font-sans)';
      ctx.fillStyle = '#e5e5e5';
      ctx.textAlign = 'center';
      ctx.fillText(node.label, x, y + size + 14);

      // Type indicator (small text below)
      ctx.font = '8px var(--font-mono)';
      ctx.fillStyle = '#71717a';
      ctx.fillText(node.type, x, y + size + 24);
    });
  }, [nodes, edges]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ imageRendering: 'auto' }}
    />
  );
}
