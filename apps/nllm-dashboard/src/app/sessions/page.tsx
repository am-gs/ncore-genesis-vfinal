'use client';

import { useState } from 'react';
import { Session } from '@/app/types';
import { Button } from '@/app/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { Play, Circle, CheckCircle, AlertCircle, Clock, Search } from 'lucide-react';
import { Input } from '@/app/components/ui/input';

export default function SessionsPage() {
  const [sessions] = useState<Session[]>([
    {
      id: '1',
      title: 'Website Redesign',
      status: 'completed',
      createdAt: Date.now() - 3600000,
      updatedAt: Date.now() - 3000000,
      task: 'Redesign company website with modern UI',
    },
    {
      id: '2',
      title: 'Market Analysis',
      status: 'completed',
      createdAt: Date.now() - 7200000,
      updatedAt: Date.now() - 6600000,
      task: 'Analyze market trends for Q3 2026',
    },
    {
      id: '3',
      title: 'Content Generation',
      status: 'error',
      createdAt: Date.now() - 10800000,
      updatedAt: Date.now() - 10200000,
      task: 'Generate blog posts about AI advancements',
    },
    {
      id: '4',
      title: 'Video Production',
      status: 'active',
      createdAt: Date.now() - 14400000,
      updatedAt: Date.now() - 14400000,
      task: 'Create promotional video for new product launch',
    },
  ]);

  const [searchTerm, setSearchTerm] = useState('');

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <Circle className="h-3 w-3 text-accent animate-pulse" />;
      case 'completed': return <CheckCircle className="h-3 w-3 text-ok" />;
      case 'error': return <AlertCircle className="h-3 w-3 text-bad" />;
      default: return <Clock className="h-3 w-3 text-text-tertiary" />;
    }
  };

  const filteredSessions = sessions.filter(
    (session) =>
      session.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (session.task && session.task.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-line">
        <h1 className="text-lg font-bold">Sessions</h1>
        <p className="text-sm text-text-secondary">View and manage your task sessions</p>
      </div>

      <div className="p-4 border-b border-line">
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-text-secondary" />
          <Input
            placeholder="Search sessions..."
            className="pl-8"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSessions.map((session) => (
            <Card key={session.id} className="hover:bg-bg-2 transition-colors">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    {getStatusIcon(session.status)}
                    <span className="truncate">{session.title}</span>
                  </CardTitle>
                  <Button variant="ghost" size="sm">
                    <Play className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <p className="text-xs text-text-secondary line-clamp-2">
                    {session.task || 'No description'}
                  </p>
                  <div className="flex justify-between text-[10px] text-text-tertiary">
                    <span>
                      {new Date(session.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </span>
                    <span>{session.status}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
