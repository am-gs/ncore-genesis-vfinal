// File browser component

'use client';

import { useState, useEffect } from 'react';
import { FileNode } from '@/app/types';
import { formatBytes } from '@/app/lib/utils';
import { 
  FileText, 
  Image, 
  Video, 
  AudioLines, 
  Folder,
  Search,
  Download
} from 'lucide-react';
import { Input } from '@/app/components/ui/input';
import { Button } from '@/app/components/ui/button';

export function FileBrowser() {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [filteredFiles, setFilteredFiles] = useState<FileNode[]>([]);
  const [searchTerm, setSearchTerm] = useState('');

  // In a real implementation, this would fetch from the API
  useEffect(() => {
    // Mock data for now
    const mockFiles: FileNode[] = [
      { name: 'report.pdf', path: '/workspace/report.pdf', type: 'document', size: 1024000, modified: Date.now() - 3600000 },
      { name: 'image.png', path: '/workspace/image.png', type: 'image', size: 2048000, modified: Date.now() - 7200000 },
      { name: 'video.mp4', path: '/workspace/video.mp4', type: 'video', size: 10240000, modified: Date.now() - 10800000 },
      { name: 'audio.mp3', path: '/workspace/audio.mp3', type: 'audio', size: 5120000, modified: Date.now() - 14400000 },
      { name: 'data.csv', path: '/workspace/data.csv', type: 'document', size: 256000, modified: Date.now() - 18000000 },
    ];
    setFiles(mockFiles);
    setFilteredFiles(mockFiles);
  }, []);

  useEffect(() => {
    if (searchTerm) {
      const filtered = files.filter(file => 
        file.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredFiles(filtered);
    } else {
      setFilteredFiles(files);
    }
  }, [searchTerm, files]);

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'image': return <Image className="h-4 w-4" />;
      case 'video': return <Video className="h-4 w-4" />;
      case 'audio': return <AudioLines className="h-4 w-4" />;
      default: return <FileText className="h-4 w-4" />;
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-line">
        <h2 className="text-lg font-semibold mb-4">Workspace Files</h2>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-text-secondary" />
          <Input
            placeholder="Search files..."
            className="pl-8"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 gap-2">
          {filteredFiles.map((file, index) => (
            <div 
              key={index} 
              className="flex items-center gap-3 p-2 rounded-md hover:bg-panel-2 cursor-pointer"
            >
              <div className="text-accent">
                {getFileIcon(file.type)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{file.name}</p>
                <p className="text-xs text-text-secondary">
                  {formatBytes(file.size)} • {new Date(file.modified).toLocaleDateString()}
                </p>
              </div>
              <Button variant="ghost" size="sm">
                <Download className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
