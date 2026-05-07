     1	// Usage chart component
     2	
     3	'use client';
     4	
     5	import { 
     6	  LineChart, 
     7	  Line, 
     8	  XAxis, 
     9	  YAxis, 
    10	  CartesianGrid, 
    11	  Tooltip, 
    12	  Legend, 
    13	  ResponsiveContainer,
    14	  AreaChart,
    15	  Area
    16	} from 'recharts';
    17	import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
    18	import { formatCost } from '@/app/lib/utils';
    19	
    20	// Mock data for the chart
    21	const usageData = [
    22	  { time: '00:00', tokens: 1200, cost: 0.0012 },
    23	  { time: '04:00', tokens: 800, cost: 0.0008 },
    24	  { time: '08:00', tokens: 2400, cost: 0.0024 },
    25	  { time: '12:00', tokens: 3600, cost: 0.0036 },
    26	  { time: '16:00', tokens: 4200, cost: 0.0042 },
    27	  { time: '20:00', tokens: 3100, cost: 0.0031 },
    28	  { time: '24:00', tokens: 1900, cost: 0.0019 },
    29	];
    30	
    31	export function UsageChart() {
    32	  return (
    33	    <Card className="h-full">
    34	      <CardHeader>
    35	        <CardTitle>Usage Statistics</CardTitle>
    36	      </CardHeader>
    37	      <CardContent className="h-[calc(100%-4rem)]">
    38	        <div className="grid grid-cols-2 gap-4 mb-4">
    39	          <div className="bg-panel-2 p-3 rounded-md">
    40	            <p className="text-sm text-text-secondary">Total Tokens</p>
    41	            <p className="text-xl font-semibold">17,200</p>
    42	          </div>
    43	          <div className="bg-panel-2 p-3 rounded-md">
    44	            <p className="text-sm text-text-secondary">Total Cost</p>
    45	            <p className="text-xl font-semibold">{formatCost(0.0172)}</p>
    46	          </div>
    47	        </div>
    48	        
    49	        <div className="h-[calc(100%-4rem)]">
    50	          <ResponsiveContainer width="100%" height="100%">
    51	            <AreaChart
    52	              data={usageData}
    53	              margin={{
    54	                top: 10,
    55	                right: 30,
    56	                left: 0,
    57	                bottom: 0,
    58	              }}
    59	            >
    60	              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
    61	              <XAxis 
    62	                dataKey="time" 
    63	                stroke="var(--color-text-secondary)"
    64	                tick={{ fontSize: 12 }}
    65	              />
    66	              <YAxis 
    67	                stroke="var(--color-text-secondary)"
    68	                tick={{ fontSize: 12 }}
    69	                tickFormatter={(value) => value.toLocaleString()}
    70	              />
    71	              <Tooltip
    72	                contentStyle={{
    73	                  backgroundColor: 'var(--color-panel)',
    74	                  borderColor: 'var(--color-line)',
    75	                  borderRadius: 'var(--radius-md)',
    76	                  color: 'var(--color-text)'
    77	                }}
    78	                formatter={(value, name) => {
    79	                  if (name === 'cost') {
    80	                    return [formatCost(Number(value)), 'Cost'];
    81	                  }
    82	                  return [value.toLocaleString(), name === 'tokens' ? 'Tokens' : 'Cost'];
    83	                }}
    84	              />
    85	              <Area 
    86	                type="monotone" 
    87	                dataKey="tokens" 
    88	                stroke="var(--color-accent)" 
    89	                fill="var(--color-accent)" 
    90	                fillOpacity={0.2}
    91	                name="Tokens"
    92	              />
    93	            </AreaChart>
    94	          </ResponsiveContainer>
    95	        </div>
    96	      </CardContent>
    97	    </Card>
    98	  );
    99	}