     1	// Types for the NLLM.ING Dashboard
     2	
     3	export interface Agent {
     4	  role: string;
     5	  prompt: string;
     6	  uncensored: boolean;
     7	  max_tokens: number;
     8	  tool?: 'gpu_image' | 'gpu_video' | 'browser' | 'code' | 'osint';
     9	}
    10	
    11	export interface TaskPlan {
    12	  task_id: string;
    13	  agents: Agent[];
    14	  plan_time: number;
    15	}
    16	
    17	export interface AgentResult {
    18	  role: string;
    19	  status: 'ok' | 'error';
    20	  latency: number;
    21	  provider: 'local' | 'cloud';
    22	  uncensored: boolean;
    23	  tokens_in: number;
    24	  tokens_out: number;
    25	  model: string;
    26	  output: string;
    27	}
    28	
    29	export interface TaskResult {
    30	  output: string;
    31	  route: {
    32	    tier: string;
    33	    estimated_cost_usd: number;
    34	  };
    35	  task_id: string;
    36	  agents: number;
    37	  plan_time: number;
    38	  exec_time: number;
    39	  latency_s: number;
    40	  cost_usd: number;
    41	  tokens: {
    42	    in: number;
    43	    out: number;
    44	    total: number;
    45	  };
    46	  specialist_results: AgentResult[];
    47	}
    48	
    49	export interface Session {
    50	  id: string;
    51	  title: string;
    52	  status: 'active' | 'completed' | 'error' | 'idle';
    53	  createdAt: Date;
    54	  updatedAt: Date;
    55	  task?: string;
    56	  result?: TaskResult;
    57	}
    58	
    59	export interface FileItem {
    60	  name: string;
    61	  type: 'image' | 'video' | 'audio' | 'document';
    62	  size: number;
    63	  url: string;
    64	  modified: number;
    65	}
    66	
    67	export interface UsageStats {
    68	  totalTokens: number;
    69	  totalCost: number;
    70	  requests: {
    71	    timestamp: number;
    72	    model: string;
    73	    inputTokens: number;
    74	    outputTokens: number;
    75	    cost: number;
    76	    latency: number;
    77	    status: 'ok' | 'error';
    78	  }[];
    79	}