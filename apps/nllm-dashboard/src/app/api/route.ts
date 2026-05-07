     1	// API route for proxying requests to the orchestrator
     2	
     3	import { NextRequest } from 'next/server';
     4	
     5	export async function GET(request: NextRequest) {
     6	  const { searchParams } = new URL(request.url);
     7	  const path = searchParams.get('path') || '';
     8	  
     9	  // In a real implementation, this would proxy to the orchestrator service
    10	  // For now, we'll return mock data for testing
    11	  if (path === '/health') {
    12	    return new Response(JSON.stringify({ status: 'ok' }), {
    13	      headers: { 'Content-Type': 'application/json' },
    14	    });
    15	  }
    16	  
    17	  if (path === '/files') {
    18	    return new Response(JSON.stringify({
    19	      files: [
    20	        { name: 'report.pdf', type: 'document', size: 1024000, url: '/files/report.pdf', modified: Date.now() - 3600000 },
    21	        { name: 'image.png', type: 'image', size: 2048000, url: '/files/image.png', modified: Date.now() - 7200000 },
    22	        { name: 'video.mp4', type: 'video', size: 10240000, url: '/files/video.mp4', modified: Date.now() - 10800000 },
    23	      ]
    24	    }), {
    25	      headers: { 'Content-Type': 'application/json' },
    26	    });
    27	  }
    28	  
    29	  return new Response(JSON.stringify({ message: 'API route placeholder' }), {
    30	    headers: { 'Content-Type': 'application/json' },
    31	  });
    32	}
    33	
    34	export async function POST(request: NextRequest) {
    35	  const { searchParams } = new URL(request.url);
    36	  const path = searchParams.get('path') || '';
    37	  
    38	  // In a real implementation, this would proxy to the orchestrator service
    39	  // For now, we'll return mock data for testing
    40	  if (path === '/run') {
    41	    const data = await request.json();
    42	    
    43	    // Simulate task processing
    44	    return new Response(JSON.stringify({
    45	      task_id: 'mock-task-id',
    46	      output: `# Task Result\n\nProcessed task: ${data.task}`,
    47	      latency_s: 1.23,
    48	      cost_usd: 0.0004,
    49	      tokens: { in: 50, out: 100, total: 150 }
    50	    }), {
    51	      headers: { 'Content-Type': 'application/json' },
    52	    });
    53	  }
    54	  
    55	  return new Response(JSON.stringify({ message: 'API route placeholder' }), {
    56	    headers: { 'Content-Type': 'application/json' },
    57	  });
    58	}