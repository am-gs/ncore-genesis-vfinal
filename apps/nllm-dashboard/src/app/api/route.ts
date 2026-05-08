// API route for proxying requests to the orchestrator

import { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const path = searchParams.get('path') || '';
  
  // In a real implementation, this would proxy to the orchestrator service
  // For now, we'll return mock data for testing
  if (path === '/health') {
    return new Response(JSON.stringify({ status: 'ok' }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }
  
  if (path === '/files') {
    return new Response(JSON.stringify({
      files: [
        { name: 'report.pdf', type: 'document', size: 1024000, url: '/files/report.pdf', modified: Date.now() - 3600000 },
        { name: 'image.png', type: 'image', size: 2048000, url: '/files/image.png', modified: Date.now() - 7200000 },
        { name: 'video.mp4', type: 'video', size: 10240000, url: '/files/video.mp4', modified: Date.now() - 10800000 },
      ]
    }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }
  
  return new Response(JSON.stringify({ message: 'API route placeholder' }), {
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function POST(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const path = searchParams.get('path') || '';
  
  // In a real implementation, this would proxy to the orchestrator service
  // For now, we'll return mock data for testing
  if (path === '/run') {
    const data = await request.json();
    
    // Simulate task processing
    return new Response(JSON.stringify({
      task_id: 'mock-task-id',
      output: `# Task Result\n\nProcessed task: ${data.task}`,
      latency_s: 1.23,
      cost_usd: 0.0004,
      tokens: { in: 50, out: 100, total: 150 }
    }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }
  
  return new Response(JSON.stringify({ message: 'API route placeholder' }), {
    headers: { 'Content-Type': 'application/json' },
  });
}
