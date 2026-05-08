// Analytics page

'use client';

import { UsageChart } from '@/app/components/usage-chart';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { 
  BarChart3, 
  TrendingUp, 
  DollarSign, 
  Clock,
  FileText,
  Image,
  Video,
  Cpu
} from 'lucide-react';

export default function AnalyticsPage() {
  // Mock data for analytics
  const stats = [
    { title: 'Total Sessions', value: '142', change: '+12%', icon: FileText },
    { title: 'Total Tokens', value: '2.4M', change: '+18%', icon: Cpu },
    { title: 'Total Cost', value: '$0.24', change: '+5%', icon: DollarSign },
    { title: 'Avg. Response Time', value: '1.2s', change: '-0.3s', icon: Clock },
  ];

  const modelUsage = [
    { model: 'GPT-4', usage: 45, color: 'bg-blue-500' },
    { model: 'Dolphin-3', usage: 30, color: 'bg-green-500' },
    { model: 'DeepSeek V3', usage: 15, color: 'bg-purple-500' },
    { model: 'Other', usage: 10, color: 'bg-gray-500' },
  ];

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-line">
        <h1 className="text-2xl font-bold">Analytics</h1>
        <p className="text-text-secondary">Usage statistics and performance metrics</p>
      </div>
      
      <div className="flex-1 overflow-auto p-4 space-y-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((stat, index) => (
            <Card key={index}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {stat.title}
                </CardTitle>
                <stat.icon className="h-4 w-4 text-text-secondary" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
                <p className="text-xs text-text-secondary">
                  {stat.change}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
        
        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <UsageChart />
          
          <Card>
            <CardHeader>
              <CardTitle>Model Usage</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {modelUsage.map((model, index) => (
                  <div key={index}>
                    <div className="flex justify-between text-sm mb-1">
                      <span>{model.model}</span>
                      <span>{model.usage}%</span>
                    </div>
                    <div className="w-full bg-panel-3 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full ${model.color}`} 
                        style={{ width: `${model.usage}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
