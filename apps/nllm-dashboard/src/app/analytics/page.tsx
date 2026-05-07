     1	// Analytics page
     2	
     3	'use client';
     4	
     5	import { UsageChart } from '@/app/components/usage-chart';
     6	import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
     7	import { 
     8	  BarChart3, 
     9	  TrendingUp, 
    10	  DollarSign, 
    11	  Clock,
    12	  FileText,
    13	  Image,
    14	  Video,
    15	  Cpu
    16	} from 'lucide-react';
    17	
    18	export default function AnalyticsPage() {
    19	  // Mock data for analytics
    20	  const stats = [
    21	    { title: 'Total Sessions', value: '142', change: '+12%', icon: FileText },
    22	    { title: 'Total Tokens', value: '2.4M', change: '+18%', icon: Cpu },
    23	    { title: 'Total Cost', value: '$0.24', change: '+5%', icon: DollarSign },
    24	    { title: 'Avg. Response Time', value: '1.2s', change: '-0.3s', icon: Clock },
    25	  ];
    26	
    27	  const modelUsage = [
    28	    { model: 'GPT-4', usage: 45, color: 'bg-blue-500' },
    29	    { model: 'Dolphin-3', usage: 30, color: 'bg-green-500' },
    30	    { model: 'DeepSeek V3', usage: 15, color: 'bg-purple-500' },
    31	    { model: 'Other', usage: 10, color: 'bg-gray-500' },
    32	  ];
    33	
    34	  return (
    35	    <div className="h-full flex flex-col">
    36	      <div className="p-4 border-b border-line">
    37	        <h1 className="text-2xl font-bold">Analytics</h1>
    38	        <p className="text-text-secondary">Usage statistics and performance metrics</p>
    39	      </div>
    40	      
    41	      <div className="flex-1 overflow-auto p-4 space-y-6">
    42	        {/* Stats Grid */}
    43	        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
    44	          {stats.map((stat, index) => (
    45	            <Card key={index}>
    46	              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
    47	                <CardTitle className="text-sm font-medium">
    48	                  {stat.title}
    49	                </CardTitle>
    50	                <stat.icon className="h-4 w-4 text-text-secondary" />
    51	              </CardHeader>
    52	              <CardContent>
    53	                <div className="text-2xl font-bold">{stat.value}</div>
    54	                <p className="text-xs text-text-secondary">
    55	                  {stat.change}
    56	                </p>
    57	              </CardContent>
    58	            </Card>
    59	          ))}
    60	        </div>
    61	        
    62	        {/* Charts */}
    63	        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
    64	          <UsageChart />
    65	          
    66	          <Card>
    67	            <CardHeader>
    68	              <CardTitle>Model Usage</CardTitle>
    69	            </CardHeader>
    70	            <CardContent>
    71	              <div className="space-y-4">
    72	                {modelUsage.map((model, index) => (
    73	                  <div key={index}>
    74	                    <div className="flex justify-between text-sm mb-1">
    75	                      <span>{model.model}</span>
    76	                      <span>{model.usage}%</span>
    77	                    </div>
    78	                    <div className="w-full bg-panel-3 rounded-full h-2">
    79	                      <div 
    80	                        className={`h-2 rounded-full ${model.color}`} 
    81	                        style={{ width: `${model.usage}%` }}
    82	                      ></div>
    83	                    </div>
    84	                  </div>
    85	                ))}
    86	              </div>
    87	            </CardContent>
    88	          </Card>
    89	        </div>
    90	      </div>
    91	    </div>
    92	  );
    93	}