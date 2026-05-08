'use client';

import { useState } from 'react';
import { FileNode } from '@/app/types';
import {
  Folder, FileText, Image, Video, Music,
  ChevronRight, ChevronDown, Download
} from 'lucide-react';

function getFileIcon(type: string) {
  switch (type) {
    case 'image': return <Image className="h-3.5 w-3.5 text-accent-3" />;
    case 'video': return <Video className="h-3.5 w-3.5 text-accent" />;
    case 'audio': return <Music className="h-3.5 w-3.5 text-warn" />;
    case 'directory': return <Folder className="h-3.5 w-3.5 text-text-secondary" />;
    default: return <FileText className="h-3.5 w-3.5 text-text-tertiary" />;
  }
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function FileRow({
  node,
  depth = 0,
}: {
  node: FileNode;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDir = node.type === 'directory';
  const hasChildren = isDir && node.children && node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2 px-3 py-1.5 hover:bg-panel-2 cursor-pointer transition-colors text-sm"
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        onClick={() => isDir && setExpanded(!expanded)}
      >
        {isDir && hasChildren && (
          <span className="text-text-tertiary">
            {expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </span>
        )}
        {isDir && !hasChildren && (
          <span className="w-3" />
        )}
        {!isDir && <span className="w-3" />}
        {getFileIcon(node.type)}
        <span className="flex-1 truncate text-xs">{node.name}</span>
        <span className="text-[10px] text-text-tertiary tabular-nums">
          {isDir ? '' : formatSize(node.size)}
        </span>
        {!isDir && (
          <a
            href={`/files/${node.path.split('/').pop()}`}
            download
            className="text-text-tertiary hover:text-accent transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <Download className="h-3 w-3" />
          </a>
        )}
      </div>
      {isDir && expanded && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <FileRow key={child.path} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileExplorer({ files }: { files: FileNode[] }) {
  return (
    <div className="h-full flex flex-col bg-bg">
      <div className="flex items-center justify-between px-3 py-2 border-b border-line bg-panel">
        <span className="text-xs font-medium">Workspace Files</span>
        <span className="text-[10px] text-text-tertiary">{files.length} items</span>
      </div>
      <div className="flex-1 overflow-auto">
        {files.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <Folder className="h-10 w-10 mb-2 opacity-20" />
            <p className="text-xs">No files yet</p>
          </div>
        ) : (
          files.map((file) => <FileRow key={file.path} node={file} />)
        )}
      </div>
    </div>
  );
}
