     1	// Sessions page
     2	
     3	'use client';
     4	
     5	import { useState } from 'react';
     6	import { Session } from '@/app/types';
     7	import { Button } from '@/app/components/ui/button';
     8	import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
     9	import { 
    10	  Play, 
    11	  Square, 
    12	  FileText, 
    13	  BarChart3, 
    14	  Settings,
    15	  Circle,
    16	  CheckCircle,
    17	  AlertCircle,
    18	  Clock,
    19	  Search
    20	} from 'lucide-react';
    21	import { Input } from '@/app/components/ui/input';
    22	import { formatBytes } from '@/app/lib/utils';
    23	
    24	export default function SessionsPage() {
    25	  const [sessions, setSessions] = useState<Session[]>([
    26	    { 
    27	      id: '1', 
    28	      title: 'Website Redesign', 
    29	      status: 'completed', 
    30	      createdAt: new Date(Date.now() - 3600000),
    31	      updatedAt: new Date(Date.now() - 3000000),
    32	      task: 'Redesign company website with modern UI',
    33	      result: {
    34	        output: '# Website Redesign Complete\n\nRedesigned the website with a modern UI...',
    35	        route: { tier: 'standard', estimated_cost_usd: 0.0012 },
    36	        task_id: '1',
    37	        agents: 3,
    38	        plan_time: 0.45,
    39	        exec_time: 12.3,
    40	        latency_s: 12.75,
    41	        cost_usd: 0.0012,
    42	        tokens: { in: 1200, out: 2400, total: 3600 },
    43	        specialist_results: [
    44	          { role: 'Designer', status: 'ok', latency: 4.2, provider: 'cloud', uncensored: false, tokens_in: 400, tokens_out: 800, model: 'gpt-4', output: 'Design mockups created' },
    45	          { role: 'Developer', status: 'ok', latency: 5.1, provider: 'local', uncensored: false, tokens_in: 500, tokens_out: 1000, model: 'dolphin3', output: 'Frontend code implemented' },
    46	          { role: 'Reviewer', status: 'ok', latency: 3.0, provider: 'cloud', uncensored: false, tokens_in: 300, tokens_out: 600, model: 'gpt-4', output: 'Code review completed' }
    47	        ]
    48	      }
    49	    },
    50	    { 
    51	      id: '2', 
    52	      title: 'Market Analysis', 
    53	      status: 'completed', 
    54	      createdAt: new Date(Date.now() - 7200000),
    55	      updatedAt: new Date(Date.now() - 6600000),
    56	      task: 'Analyze market trends for Q3 2026'
    57	    },
    58	    { 
    59	      id: '3', 
    60	      title: 'Content Generation', 
    61	      status: 'error', 
    62	      createdAt: new Date(Date.now() - 10800000),
    63	      updatedAt: new Date(Date.now() - 10200000),
    64	      task: 'Generate blog posts about AI advancements'
    65	    },
    66	    { 
    67	      id: '4', 
    68	      title: 'Video Production', 
    69	      status: 'active', 
    70	      createdAt: new Date(Date.now() - 14400000),
    71	      updatedAt: new Date(Date.now() - 14400000),
    72	      task: 'Create promotional video for new product launch'
    73	    },
    74	  ]);
    75	  
    76	  const [searchTerm, setSearchTerm] = useState('');
    77	
    78	  const getStatusIcon = (status: string) => {
    79	    switch (status) {
    80	      case 'active': return <Circle className="h-3 w-3 text-blue-500" />;
    81	      case 'completed': return <CheckCircle className="h-3 w-3 text-green-500" />;
    82	      case 'error': return <AlertCircle className="h-3 w-3 text-red-500" />;
    83	      default: return <Clock className="h-3 w-3 text-gray-500" />;
    84	    }
    85	  };
    86	
    87	  const filteredSessions = sessions.filter(session => 
    88	    session.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    89	    (session.task && session.task.toLowerCase().includes(searchTerm.toLowerCase()))
    90	  );
    91	
    92	  return (
    93	    <div className="h-full flex flex-col">
    94	      <div className="p-4 border-b border-line">
    95	        <h1 className="text-2xl font-bold">Sessions</h1>
    96	        <p className="text-text-secondary">View and manage your task sessions</p>
    97	      </div>
    98	      
    99	      <div className="p-4 border-b border-line">
   100	        <div className="relative">
   101	          <Search className="absolute left-2 top-2.5 h-4 w-4 text-text-secondary" />
   102	          <Input
   103	            placeholder="Search sessions..."
   104	            className="pl-8"
   105	            value={searchTerm}
   106	            onChange={(e) => setSearchTerm(e.target.value)}
   107	          />
   108	        </div>
   109	      </div>
   110	      
   111	      <div className="flex-1 overflow-auto p-4">
   112	        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
   113	          {filteredSessions.map((session) => (
   114	            <Card key={session.id} className="hover:bg-panel-2 transition-colors">
   115	              <CardHeader className="pb-2">
   116	                <div className="flex items-center justify-between">
   117	                  <CardTitle className="text-lg flex items-center gap-2">
   118	                    {getStatusIcon(session.status)}
   119	                    <span className="truncate">{session.title}</span>
   120	                  </CardTitle>
   121	                  <Button variant="ghost" size="sm">
   122	                    <Play className="h-4 w-4" />
   123	                  </Button>
   124	                </div>
   125	              </CardHeader>
   126	              <CardContent>
   127	                <div className="space-y-2">
   128	                  <p className="text-sm text-text-secondary line-clamp-2">
   129	                    {session.task || 'No description'}
   130	                  </p>
   131	                  <div className="flex justify-between text-xs text-text-tertiary">
   132	                    <span>
   133	                      {session.createdAt.toLocaleDateString([], { month: 'short', day: 'numeric' })}
   134	                    </span>
   135	                    <span>
   136	                      {session.status === 'completed' && session.result 
   137	                        ? `${formatBytes(session.result.tokens.total)} tokens` 
   138	                        : session.status}
   139	                    </span>
   140	                  </div>
   141	                </div>
   142	              </CardContent>
   143	            </Card>
   144	          ))}
   145	        </div>
   146	      </div>
   147	    </div>
   148	  );
   149	}