/**
 * Demo mode — loads pre-captured project data from /demo/project.json
 * when no backend is available (e.g. Vercel static deploy).
 */

import type { V5Project, V5ExtractionResponse } from './types';

const DEMO_PROJECT_ID = 'demo';
let _cache: V5Project | null = null;

async function loadDemoProject(): Promise<V5Project> {
  if (_cache) return _cache;
  const res = await fetch('/demo/project.json');
  if (!res.ok) throw new Error('Demo data not found');
  const data = await res.json();
  // Override ID and status for demo
  data.id = DEMO_PROJECT_ID;
  data.name = 'Forthing Showroom';
  data.status = 'reviewing_images';
  _cache = data as V5Project;
  return _cache;
}

export const DEMO_ID = DEMO_PROJECT_ID;

export function isDemoMode(): boolean {
  return window.location.search.includes('demo=true') ||
    (import.meta as any).env?.VITE_DEMO_MODE === 'true' ||
    !(import.meta as any).env?.DEV;
}

export async function getDemoProject(): Promise<V5Project> {
  return loadDemoProject();
}

export async function getDemoExtraction(): Promise<V5ExtractionResponse> {
  const p = await loadDemoProject();
  return {
    project_id: p.id,
    status: 'reviewing_extraction',
    rooms: p.v5_rooms,
    floor_plans: p.floor_plans,
    total_products: p.v5_rooms.reduce((s, r) => s + r.products.length, 0),
  };
}

export function getDemoImageUrl(path: string): string {
  // In demo mode, paths are already relative (e.g. /demo/rooms/xxx.png)
  if (path.startsWith('/demo/')) return path;
  return path;
}
