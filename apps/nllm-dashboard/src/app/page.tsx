     1	// Main dashboard page
     2	
     3	'use client';
     4	
     5	import { useState, useEffect } from 'react';
     6	import { useWebSocket } from '@/app/contexts/websocket';
     7	import { Button } from '@/app/components/ui/button';
     8	import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
     9	import { Badge } from '@/app/components/ui/badge';
    10	import { Input } from '@/app/components/ui/input';
    11	import { ScrollArea } from '@/app/components/ui/scroll-area';
    12	import { 
    13	  Play, 
    14	  Pause, 
    15	  Square, 
    16	  FileText, 
    17	  BarChart3, 
    18	  Settings,
    19	  Circle,
    20	  CheckCircle,
    21	  AlertCircle,
    22	  Clock
    23	} from 'lucide-react';
    24	
    25	export default function DashboardPage() {
    26	  const { isConnected, plan, results, taskResult, sendTask } = useWebSocket();
    27	  const [taskInput, setTaskInput] = useState('');
    28	  const [sessions, setSessions] = useState<any[]>([
    29	    { id: '1', title: 'Website Redesign', status: 'completed', createdAt: new Date(Date.now() - 3600000) },
    30	    { id: '2', title: 'Market Analysis', status: 'completed', createdAt: new Date(Date.now() - 7200000) },
    31	    { id: '3', title: 'Content Generation', status: 'error', createdAt: new Date(Date.now() - 10800000) },
    32	  ]);
    33	  const [activeSession, setActiveSession] = useState<string | null>(null);
    34	
    35	  const handleRunTask = () => {
    36	    if (taskInput.trim()) {
    37	      sendTask(taskInput);
    38	      setTaskInput('');
    39	      
    40	      // Add to sessions
    41	      const newSession = {
    42	        id: Date.now().toString(),
    43	        title: taskInput,
    44	        status: 'active',
    45	        createdAt: new Date(),
    46	      };
    47	      setSessions(prev => [newSession, ...prev]);
    48	      setActiveSession(newSession.id);
    49	    }
    50	  };
    51	
    52	  // Update session status when task completes
    53	  useEffect(() => {
    54	    if (taskResult) {
    55	      setSessions(prev => 
    56	        prev.map(s => 
    57	          s.id === activeSession 
    58	            ? { ...s, status: 'completed', updatedAt: new Date() } 
    59	            : s
    60	        )
    61	      );
    62	    }
    63	  }, [taskResult, activeSession]);
    64	
    65	  const getStatusIcon = (status: string) => {
    66	    switch (status) {
    67	      case 'active': return <Circle className="h-3 w-3 text-blue-500" />;
    68	      case 'completed': return <CheckCircle className="h-3 w-3 text-green-500" />;
    69	      case 'error': return <AlertCircle className="h-3 w-3 text-red-500" />;
    70	      default: return <Clock className="h-3 w-3 text-gray-500" />;
    71	    }
    72	  };
    73	
    74	  return (
    75	    <div className="flex flex-col h-full">
    76	      {/* Top Bar */}
    77	      <div className="h-14 border-b border-line flex items-center justify-between px-4">
    78	        <div>
    79	          <h2 className="font-medium">Dashboard</h2>
    80	        </div>
    81	        <div className="flex items-center gap-2">
    82	          <Badge variant={isConnected ? "default" : "destructive"}>
    83	            {isConnected ? 'Connected' : 'Disconnected'}
    84	          </Badge>
    85	        </div>
    86	      </div>
    87	      
    88	      <div className="flex-1 flex flex-col md:flex-row">
    89	        {/* Left Panel - Task Input and Sessions */}
    90	        <div className="w-full md:w-80 lg:w-96 border-r border-line flex flex-col">
    91	          <div className="p-4 border-b border-line">
    92	            <h2 className="font-medium mb-2">New Task</h2>
    93	            <div className="flex gap-2">
    94	              <Input
    95	                value={taskInput}
    96	                onChange={(e) => setTaskInput(e.target.value)}
    97	                placeholder="Describe your task..."
    98	                className="flex-1"
    99	                onKeyDown={(e) => {
   100	                  if (e.key === 'Enter') handleRunTask();
   101	                }}
   102	              />
   103	              <Button onClick={handleRunTask} size="sm">
   104	                <Play className="h-4 w-4" />
   105	              </Button>
   106	            </div>
   107	          </div>
   108	          
   109	          <div className="flex-1 overflow-hidden">
   110	            <ScrollArea className="h-full p-2">
   111	              <h2 className="font-medium p-2">Recent Sessions</h2>
   112	              <div className="space-y-1">
   113	                {sessions.map((session) => (
   114	                  <div 
   115	                    key={session.id}
   116	                    className={`flex items-center gap-2 p-2 rounded-md cursor-pointer hover:bg-panel-2 ${
   117	                      activeSession === session.id ? 'bg-panel-2' : ''
   118	                    }`}
   119	                    onClick={() => setActiveSession(session.id)}
   120	                  >
   121	                    {getStatusIcon(session.status)}
   122	                    <div className="flex-1 min-w-0">
   123	                      <p className="text-sm truncate">{session.title}</p>
   124	                      <p className="text-xs text-text-tertiary">
   125	                        {session.createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
   126	                      </p>
   127	                    </div>
   128	                  </div>
   129	                ))}
   130	              </div>
   131	            </ScrollArea>
   132	          </div>
   133	        </div>
   134	        
   135	        {/* Center Panel - Agent Progress */}
   136	        <div className="flex-1 flex flex-col">
   137	          <div className="p-4 border-b border-line">
   138	            <h2 className="font-medium">Agent Progress</h2>
   139	          </div>
   140	          
   141	          <div className="flex-1 overflow-auto p-4">
   142	            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
   143	              {results.map((result, index) => (
   144	                <Card key={index}>
   145	                  <CardHeader className="pb-2">
   146	                    <CardTitle className="text-sm flex items-center justify-between">
   147	                      <span>{result.role}</span>
   148	                      {result.status === 'ok' ? (
   149	                        <CheckCircle className="h-4 w-4 text-green-500" />
   150	                      ) : result.status === 'error' ? (
   151	                        <AlertCircle className="h-4 w-4 text-red-500" />
   152	                      ) : (
   153	                        <Clock className="h-4 w-4 text-blue-500 animate-pulse" />
   154	                      )}
   155	                    </CardTitle>
   156	                  </CardHeader>
   157	                  <CardContent>
   158	                    <div className="space-y-2">
   159	                      <div className="flex justify-between text-xs">
   160	                        <span className="text-text-secondary">Provider</span>
   161	                        <span>{result.provider}</span>
   162	                      </div>
   163	                      <div className="flex justify-between text-xs">
   164	                        <span className="text-text-secondary">Latency</span>
   165	                        <span>{result.latency.toFixed(1)}s</span>
   166	                      </div>
   167	                      <div className="flex justify-between text-xs">
   168	                        <span className="text-text-secondary">Tokens</span>
   169	                        <span>{result.tokens_in + result.tokens_out}</span>
   170	                      </div>
   171	                    </div>
   172	                  </CardContent>
   173	                </Card>
   174	              ))}
   175	              
   176	              {plan && (
   177	                <Card>
   178	                  <CardHeader className="pb-2">
   179	                    <CardTitle className="text-sm">Task Plan</CardTitle>
   180	                  </CardHeader>
   181	                  <CardContent>
   182	                    <div className="text-xs space-y-1">
   183	                      {plan.agents.map((agent, index) => (
   184	                        <div key={index} className="flex items-center gap-2">
   185	                          <div className="w-2 h-2 rounded-full bg-accent"></div>
   186	                          <span>{agent.role}</span>
   187	                        </div>
   188	                      ))}
   189	                    </div>
   190	                    <div className="mt-2 text-xs text-text-secondary">
   191	                      Generated in {plan.plan_time.toFixed(2)}s
   192	                    </div>
   193	                  </CardContent>
   194	                </Card>
   195	              )}
   196	            </div>
   197	          </div>
   198	        </div>
   199	        
   200	        {/* Right Panel - Usage Stats */}
   201	        <div className="w-full md:w-80 lg:w-96 border-l border-line flex flex-col">
   202	          <div className="p-4 border-b border-line">
   203	            <h2 className="font-medium">Usage Statistics</h2>
   204	          </div>
   205	          
   206	          <div className="flex-1 overflow-auto p-4">
   207	            <div className="space-y-4">
   208	              <Card>
   209	                <CardHeader className="pb-2">
   210	                  <CardTitle className="text-sm">Current Session</CardTitle>
   211	                </CardHeader>
   212	                <CardContent>
   213	                  <div className="space-y-2">
   214	                    <div className="flex justify-between text-sm">
   215	                      <span className="text-text-secondary">Tokens</span>
   216	                      <span>{taskResult ? taskResult.tokens.total.toLocaleString() : '0'}</span>
   217	                    </div>
   218	                    <div className="flex justify-between text-sm">
   219	                      <span className="text-text-secondary">Cost</span>
   220	                      <span>{taskResult ? `$${taskResult.cost_usd.toFixed(4)}` : '$0.0000'}</span>
   221	                    </div>
   222	                    <div className="flex justify-between text-sm">
   223	                      <span className="text-text-secondary">Latency</span>
   224	                      <span>{taskResult ? `${taskResult.latency_s.toFixed(2)}s` : '0.00s'}</span>
   225	                    </div>
   226	                  </div>
   227	                </CardContent>
   228	              </Card>
   229	              
   230	              <Card>
   231	                <CardHeader className="pb-2">
   232	                  <CardTitle className="text-sm">Task Output</CardTitle>
   233	                </CardHeader>
   234	                <CardContent>
   235	                  <div className="text-sm whitespace-pre-wrap">
   236	                    {taskResult ? taskResult.output : 'No task output yet'}
   237	                  </div>
   238	                </CardContent>
   239	              </Card>
   240	            </div>
   241	          </div>
   242	        </div>
   243	      </div>
   244	    </div>
   245	  );
   246	}