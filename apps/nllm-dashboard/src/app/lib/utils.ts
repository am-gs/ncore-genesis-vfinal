     1	// lib/utils.ts
     2	
     3	import { clsx, type ClassValue } from "clsx"
     4	import { twMerge } from "tailwind-merge"
     5	
     6	export function cn(...inputs: ClassValue[]) {
     7	  return twMerge(clsx(inputs))
     8	}
     9	
    10	export function formatCost(cost: number): string {
    11	  if (cost === 0) return '$0.0000';
    12	  if (cost < 0.0001) return '<$0.0001';
    13	  return `$${cost.toFixed(4)}`;
    14	}
    15	
    16	export function formatTokenCount(tokens: number): string {
    17	  if (tokens < 1000) return tokens.toString();
    18	  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}k`;
    19	  return `${(tokens / 1000000).toFixed(1)}M`;
    20	}
    21	
    22	export function relativeTime(timestamp: number): string {
    23	  const now = Date.now();
    24	  const diff = now - timestamp;
    25	  const seconds = Math.floor(diff / 1000);
    26	  const minutes = Math.floor(seconds / 60);
    27	  const hours = Math.floor(minutes / 60);
    28	  const days = Math.floor(hours / 24);
    29	
    30	  if (seconds < 60) return `${seconds}s ago`;
    31	  if (minutes < 60) return `${minutes}m ago`;
    32	  if (hours < 24) return `${hours}h ago`;
    33	  return `${days}d ago`;
    34	}
    35	
    36	export function formatBytes(bytes: number): string {
    37	  if (bytes < 1024) return `${bytes} B`;
    38	  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    39	  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    40	  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    41	}