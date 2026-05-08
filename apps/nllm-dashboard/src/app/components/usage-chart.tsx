// Usage chart component

'use client';

import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { formatCost } from '@/app/lib/utils';

// Mock data for the chart
const usageData = [
  { time: '00:00', tokens: 1200, cost: 0.0012 },
  { time: '04:00', tokens: 800, cost: 0.0008 },
  { time: '08:00', tokens: 2400, cost: 0.0024 },
  { time: '12:00', tokens: 3600, cost: 0.0036 },
  { time: '16:00', tokens: 4200, cost: 0.0042 },
  { time: '20:00', tokens: 3100, cost: 0.0031 },
  { time: '24:00', tokens: 1900, cost: 0.0019 },
];

export function UsageChart() {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Usage Statistics</CardTitle>
      </CardHeader>
      <CardContent className="h-[calc(100%-4rem)]">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="bg-panel-2 p-3 rounded-md">
            <p className="text-sm text-text-secondary">Total Tokens</p>
            <p className="text-xl font-semibold">17,200</p>
          </div>
          <div className="bg-panel-2 p-3 rounded-md">
            <p className="text-sm text-text-secondary">Total Cost</p>
            <p className="text-xl font-semibold">{formatCost(0.0172)}</p>
          </div>
        </div>
        
        <div className="h-[calc(100%-4rem)]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={usageData}
              margin={{
                top: 10,
                right: 30,
                left: 0,
                bottom: 0,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
              <XAxis 
                dataKey="time" 
                stroke="var(--color-text-secondary)"
                tick={{ fontSize: 12 }}
              />
              <YAxis 
                stroke="var(--color-text-secondary)"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => value.toLocaleString()}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--color-panel)',
                  borderColor: 'var(--color-line)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--color-text)'
                }}
                formatter={(value, name) => {
                  if (name === 'cost') {
                    return [formatCost(Number(value)), 'Cost'];
                  }
                  return [value.toLocaleString(), name === 'tokens' ? 'Tokens' : 'Cost'];
                }}
              />
              <Area 
                type="monotone" 
                dataKey="tokens" 
                stroke="var(--color-accent)" 
                fill="var(--color-accent)" 
                fillOpacity={0.2}
                name="Tokens"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
