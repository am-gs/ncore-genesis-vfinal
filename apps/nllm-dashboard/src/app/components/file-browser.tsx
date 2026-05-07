     1	// File browser component
     2	
     3	'use client';
     4	
     5	import { useState, useEffect } from 'react';
     6	import { FileItem } from '@/app/types';
     7	import { formatBytes } from '@/app/lib/utils';
     8	import { 
     9	  FileText, 
    10	  Image, 
    11	  Video, 
    12	  AudioLines, 
    13	  Folder,
    14	  Search,
    15	  Download
    16	} from 'lucide-react';
    17	import { Input } from '@/app/components/ui/input';
    18	import { Button } from '@/app/components/ui/button';
    19	
    20	export function FileBrowser() {
    21	  const [files, setFiles] = useState<FileItem[]>([]);
    22	  const [filteredFiles, setFilteredFiles] = useState<FileItem[]>([]);
    23	  const [searchTerm, setSearchTerm] = useState('');
    24	
    25	  // In a real implementation, this would fetch from the API
    26	  useEffect(() => {
    27	    // Mock data for now
    28	    const mockFiles: FileItem[] = [
    29	      { name: 'report.pdf', type: 'document', size: 1024000, url: '/files/report.pdf', modified: Date.now() - 3600000 },
    30	      { name: 'image.png', type: 'image', size: 2048000, url: '/files/image.png', modified: Date.now() - 7200000 },
    31	      { name: 'video.mp4', type: 'video', size: 10240000, url: '/files/video.mp4', modified: Date.now() - 10800000 },
    32	      { name: 'audio.mp3', type: 'audio', size: 5120000, url: '/files/audio.mp3', modified: Date.now() - 14400000 },
    33	      { name: 'data.csv', type: 'document', size: 256000, url: '/files/data.csv', modified: Date.now() - 18000000 },
    34	    ];
    35	    setFiles(mockFiles);
    36	    setFilteredFiles(mockFiles);
    37	  }, []);
    38	
    39	  useEffect(() => {
    40	    if (searchTerm) {
    41	      const filtered = files.filter(file => 
    42	        file.name.toLowerCase().includes(searchTerm.toLowerCase())
    43	      );
    44	      setFilteredFiles(filtered);
    45	    } else {
    46	      setFilteredFiles(files);
    47	    }
    48	  }, [searchTerm, files]);
    49	
    50	  const getFileIcon = (type: string) => {
    51	    switch (type) {
    52	      case 'image': return <Image className="h-4 w-4" />;
    53	      case 'video': return <Video className="h-4 w-4" />;
    54	      case 'audio': return <AudioLines className="h-4 w-4" />;
    55	      default: return <FileText className="h-4 w-4" />;
    56	    }
    57	  };
    58	
    59	  return (
    60	    <div className="h-full flex flex-col">
    61	      <div className="p-4 border-b border-line">
    62	        <h2 className="text-lg font-semibold mb-4">Workspace Files</h2>
    63	        <div className="relative">
    64	          <Search className="absolute left-2 top-2.5 h-4 w-4 text-text-secondary" />
    65	          <Input
    66	            placeholder="Search files..."
    67	            className="pl-8"
    68	            value={searchTerm}
    69	            onChange={(e) => setSearchTerm(e.target.value)}
    70	          />
    71	        </div>
    72	      </div>
    73	      
    74	      <div className="flex-1 overflow-auto p-4">
    75	        <div className="grid grid-cols-1 gap-2">
    76	          {filteredFiles.map((file, index) => (
    77	            <div 
    78	              key={index} 
    79	              className="flex items-center gap-3 p-2 rounded-md hover:bg-panel-2 cursor-pointer"
    80	            >
    81	              <div className="text-accent">
    82	                {getFileIcon(file.type)}
    83	              </div>
    84	              <div className="flex-1 min-w-0">
    85	                <p className="text-sm truncate">{file.name}</p>
    86	                <p className="text-xs text-text-secondary">
    87	                  {formatBytes(file.size)} • {new Date(file.modified).toLocaleDateString()}
    88	                </p>
    89	              </div>
    90	              <Button variant="ghost" size="sm">
    91	                <Download className="h-4 w-4" />
    92	              </Button>
    93	            </div>
    94	          ))}
    95	        </div>
    96	      </div>
    97	    </div>
    98	  );
    99	}