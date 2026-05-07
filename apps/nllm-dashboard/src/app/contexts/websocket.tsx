     1	// WebSocket context for real-time updates
     2	
     3	'use client';
     4	
     5	import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
     6	import { TaskPlan, AgentResult, TaskResult } from '@/app/types';
     7	
     8	interface WebSocketContextType {
     9	  isConnected: boolean;
    10	  plan: TaskPlan | null;
    11	  results: AgentResult[];
    12	  taskResult: TaskResult | null;
    13	  sendTask: (task: string) => void;
    14	}
    15	
    16	const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);
    17	
    18	export function WebSocketProvider({ children }: { children: ReactNode }) {
    19	  const [isConnected, setIsConnected] = useState(false);
    20	  const [plan, setPlan] = useState<TaskPlan | null>(null);
    21	  const [results, setResults] = useState<AgentResult[]>([]);
    22	  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
    23	  const [ws, setWs] = useState<WebSocket | null>(null);
    24	
    25	  useEffect(() => {
    26	    const websocket = new WebSocket('ws://localhost:8080/ws');
    27	    
    28	    websocket.onopen = () => {
    29	      setIsConnected(true);
    30	    };
    31	    
    32	    websocket.onmessage = (event) => {
    33	      const data = JSON.parse(event.data);
    34	      
    35	      switch (data.type) {
    36	        case 'plan':
    37	          setPlan(data.data);
    38	          setResults([]);
    39	          setTaskResult(null);
    40	          break;
    41	        case 'agent_status':
    42	          // Update agent status in real-time
    43	          setResults(prev => {
    44	            const existing = prev.find(r => r.role === data.data.role);
    45	            if (existing) {
    46	              return prev.map(r => 
    47	                r.role === data.data.role 
    48	                  ? { ...r, status: data.data.status, latency: data.data.latency || r.latency } 
    49	                  : r
    50	              );
    51	            } else {
    52	              return [...prev, { 
    53	                role: data.data.role, 
    54	                status: data.data.status, 
    55	                latency: 0,
    56	                provider: 'cloud',
    57	                uncensored: false,
    58	                tokens_in: 0,
    59	                tokens_out: 0,
    60	                model: '',
    61	                output: ''
    62	              }];
    63	            }
    64	          });
    65	          break;
    66	        case 'agent_result':
    67	          // Add complete agent result
    68	          setResults(prev => {
    69	            const existing = prev.find(r => r.role === data.data.role);
    70	            if (existing) {
    71	              return prev.map(r => 
    72	                r.role === data.data.role ? { ...r, ...data.data } : r
    73	              );
    74	            } else {
    75	              return [...prev, data.data];
    76	            }
    77	          });
    78	          break;
    79	        case 'result':
    80	          setTaskResult(data.data);
    81	          break;
    82	      }
    83	    };
    84	    
    85	    websocket.onclose = () => {
    86	      setIsConnected(false);
    87	    };
    88	    
    89	    setWs(websocket);
    90	    
    91	    return () => {
    92	      websocket.close();
    93	    };
    94	  }, []);
    95	  
    96	  const sendTask = (task: string) => {
    97	    if (ws && ws.readyState === WebSocket.OPEN) {
    98	      fetch('http://localhost:8080/run', {
    99	        method: 'POST',
   100	        headers: {
   101	          'Content-Type': 'application/json',
   102	        },
   103	        body: JSON.stringify({ task }),
   104	      });
   105	    }
   106	  };
   107	  
   108	  return (
   109	    <WebSocketContext.Provider value={{ 
   110	      isConnected, 
   111	      plan, 
   112	      results, 
   113	      taskResult,
   114	      sendTask
   115	    }}>
   116	      {children}
   117	    </WebSocketContext.Provider>
   118	  );
   119	}
   120	
   121	export function useWebSocket() {
   122	  const context = useContext(WebSocketContext);
   123	  if (context === undefined) {
   124	    throw new Error('useWebSocket must be used within a WebSocketProvider');
   125	  }
   126	  return context;
   127	}