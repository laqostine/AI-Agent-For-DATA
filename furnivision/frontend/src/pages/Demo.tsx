import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { V5Project, V5Room } from '@/lib/types';
import { getLocalFileUrl } from '@/lib/api';
import { cn } from '@/lib/utils';

const V4_ROOMS = [
  { id: '01_accueil', label: 'Accueil', floor: 'ground' },
  { id: '02_sales_lounge', label: 'Sales Lounge', floor: 'ground' },
  { id: '03_conversation', label: 'Conversation Area', floor: 'ground' },
  { id: '04_negotiation', label: 'Negotiation Area', floor: 'ground' },
  { id: '05_kids', label: 'Escape Kids', floor: 'ground' },
  { id: '06_magasin', label: 'Magasin', floor: 'ground' },
  { id: '07_gm_office', label: 'GM Office', floor: 'mezzanine' },
  { id: '08_office_areas', label: 'Office Area', floor: 'mezzanine' },
  { id: '09_office_small', label: 'Workstation', floor: 'mezzanine' },
  { id: '10_conference', label: 'Conference', floor: 'mezzanine' },
  { id: '11_cashier', label: "Cashier", floor: 'mezzanine' },
  { id: '12_maintenance', label: 'Maintenance', floor: 'mezzanine' },
  { id: '13_customer_lounge', label: 'Lounge', floor: 'mezzanine' },
];

type Tab = 'rooms' | 'video';

export default function Demo() {
  const [activeTab, setActiveTab] = useState<Tab>('rooms');
  const [selectedRoom, setSelectedRoom] = useState(V4_ROOMS[0].id);
  const [playingVideo, setPlayingVideo] = useState<string | null>(null);

  const { data: project } = useQuery<V5Project>({
    queryKey: ['demo-project'],
    queryFn: async () => (await fetch('/demo/project.json')).json(),
  });

  const v5Rooms = project?.v5_rooms ?? [];

  return (
    <div className="min-h-screen bg-surface-900 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800/50 bg-surface-800/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center">
              <span className="text-white font-bold text-[10px] sm:text-xs">FV</span>
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-bold text-gray-100 leading-tight">FurniVision AI</h1>
              <p className="text-[10px] text-gray-500">Forthing Showroom</p>
            </div>
            <h1 className="sm:hidden text-sm font-bold text-gray-100">FurniVision</h1>
          </div>

          {/* Tabs */}
          <div className="flex items-center bg-surface-900/50 rounded-lg p-0.5 border border-gray-800/50">
            <button onClick={() => setActiveTab('rooms')}
              className={cn('px-3 sm:px-4 py-1.5 rounded-md text-[11px] sm:text-xs font-medium transition-all',
                activeTab === 'rooms' ? 'bg-accent text-white shadow-sm' : 'text-gray-400 hover:text-gray-200')}>
              Rooms
            </button>
            <button onClick={() => setActiveTab('video')}
              className={cn('px-3 sm:px-4 py-1.5 rounded-md text-[11px] sm:text-xs font-medium transition-all',
                activeTab === 'video' ? 'bg-accent text-white shadow-sm' : 'text-gray-400 hover:text-gray-200')}>
              Video
            </button>
          </div>

          <div className="flex items-center gap-3">
            <p className="text-[10px] text-gray-500 hidden md:block">13 rooms &middot; 48 products &middot; ~$6</p>
            <a href="/" className="text-[11px] sm:text-xs text-accent hover:text-accent-light font-medium whitespace-nowrap">
              Upload →
            </a>
          </div>
        </div>
      </header>

      {activeTab === 'video' ? (
        <VideoTab />
      ) : (
        <RoomsTab
          v4Rooms={V4_ROOMS}
          v5Rooms={v5Rooms}
          selectedRoom={selectedRoom}
          onSelectRoom={(id) => { setSelectedRoom(id); setPlayingVideo(null); }}
          playingVideo={playingVideo}
          onPlayVideo={setPlayingVideo}
        />
      )}
    </div>
  );
}

/* ─── Video Tab ──────────────────────────────────────────── */

function VideoTab() {
  return (
    <main className="flex-1 p-4 sm:p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-4 sm:mb-6 text-center">
          <h2 className="text-lg sm:text-2xl font-bold text-white mb-1">Forthing Dealership Walkthrough</h2>
          <p className="text-xs sm:text-sm text-gray-400">13 rooms generated from one PPTX file</p>
        </div>
        <div className="card overflow-hidden">
          <video src="/demo/forthing_walkthrough.mp4" controls autoPlay playsInline className="w-full" />
        </div>
        {/* Room thumbnails */}
        <div className="mt-3 sm:mt-4 grid grid-cols-4 sm:grid-cols-5 md:grid-cols-7 gap-1.5 sm:gap-2">
          {V4_ROOMS.map((r) => (
            <div key={r.id} className="rounded-md sm:rounded-lg overflow-hidden border border-gray-800/50">
              <img src={`/demo/v4rooms/${r.id}/render.png`} alt={r.label}
                className="w-full aspect-video object-cover" />
              <p className="text-[8px] sm:text-[9px] text-gray-500 px-1 py-0.5 truncate">{r.label}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

/* ─── Rooms Tab ──────────────────────────────────────────── */

function RoomsTab({ v4Rooms, v5Rooms, selectedRoom, onSelectRoom, playingVideo, onPlayVideo }: {
  v4Rooms: typeof V4_ROOMS; v5Rooms: V5Room[]; selectedRoom: string;
  onSelectRoom: (id: string) => void; playingVideo: string | null; onPlayVideo: (id: string | null) => void;
}) {
  const selected = v4Rooms.find((r) => r.id === selectedRoom)!;
  const idx = v4Rooms.indexOf(selected);

  const matchV5 = (v4Label: string) => {
    const key = v4Label.split('(')[0].trim().split(' ')[0].toLowerCase();
    return v5Rooms.find((r) => r.label.toLowerCase().includes(key));
  };
  const v5Room = matchV5(selected.label);

  return (
    <div className="flex-1 flex flex-col lg:flex-row">
      {/* Mobile: horizontal room scroller */}
      <div className="lg:hidden border-b border-gray-800/50 bg-surface-800/30">
        <div className="flex overflow-x-auto gap-1.5 p-2.5 scrollbar-none">
          {v4Rooms.map((r) => (
            <button key={r.id} onClick={() => onSelectRoom(r.id)}
              className={cn(
                'flex-shrink-0 rounded-lg overflow-hidden border transition-all',
                selectedRoom === r.id ? 'border-accent/40 ring-1 ring-accent/20' : 'border-gray-800/50'
              )}>
              <img src={`/demo/v4rooms/${r.id}/render.png`} alt=""
                className="w-20 h-12 object-cover" />
              <p className={cn('text-[9px] px-1.5 py-0.5 truncate w-20',
                selectedRoom === r.id ? 'text-white font-medium' : 'text-gray-500')}>{r.label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Desktop: sidebar */}
      <aside className="hidden lg:block w-52 border-r border-gray-800/50 bg-surface-800/30 overflow-y-auto flex-shrink-0">
        <div className="p-2.5">
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mb-2 px-2">Ground</p>
          {v4Rooms.filter((r) => r.floor === 'ground').map((r) => (
            <SidebarItem key={r.id} room={r} active={selectedRoom === r.id} onClick={() => onSelectRoom(r.id)} />
          ))}
          <p className="text-[9px] uppercase tracking-widest text-gray-600 mt-3 mb-2 px-2">Mezzanine</p>
          {v4Rooms.filter((r) => r.floor === 'mezzanine').map((r) => (
            <SidebarItem key={r.id} room={r} active={selectedRoom === r.id} onClick={() => onSelectRoom(r.id)} />
          ))}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-4xl mx-auto">
          {/* Room title */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">{selected.label}</h2>
              <p className="text-[11px] text-gray-500">{selected.floor} floor{v5Room ? ` · ${v5Room.products.length} products` : ''}</p>
            </div>
            <div className="flex items-center gap-1.5">
              <button onClick={() => onSelectRoom(v4Rooms[Math.max(0, idx - 1)].id)}
                disabled={idx === 0}
                className="w-7 h-7 rounded-md bg-surface-800 border border-gray-800/50 flex items-center justify-center text-gray-400 hover:text-white disabled:opacity-30 transition-colors">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
              </button>
              <span className="text-[10px] text-gray-600 tabular-nums">{idx + 1}/{v4Rooms.length}</span>
              <button onClick={() => onSelectRoom(v4Rooms[Math.min(v4Rooms.length - 1, idx + 1)].id)}
                disabled={idx === v4Rooms.length - 1}
                className="w-7 h-7 rounded-md bg-surface-800 border border-gray-800/50 flex items-center justify-center text-gray-400 hover:text-white disabled:opacity-30 transition-colors">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
              </button>
            </div>
          </div>

          {/* Render + Video */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            <div className="card overflow-hidden">
              <p className="text-[10px] uppercase tracking-widest text-gray-500 px-3 pt-2.5 pb-1">AI Render</p>
              <img src={`/demo/v4rooms/${selected.id}/render.png`} alt=""
                className="w-full aspect-video object-cover" />
            </div>
            <div className="card overflow-hidden">
              <p className="text-[10px] uppercase tracking-widest text-gray-500 px-3 pt-2.5 pb-1">Video (7s)</p>
              {playingVideo === selected.id ? (
                <video src={`/demo/v4rooms/${selected.id}/video.mp4`} autoPlay controls playsInline
                  className="w-full aspect-video object-cover" onEnded={() => onPlayVideo(null)} />
              ) : (
                <div className="relative cursor-pointer group" onClick={() => onPlayVideo(selected.id)}>
                  <img src={`/demo/v4rooms/${selected.id}/render.png`} alt=""
                    className="w-full aspect-video object-cover brightness-[.65] group-hover:brightness-75 transition" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-12 h-12 rounded-full bg-white/15 backdrop-blur-sm flex items-center justify-center group-hover:scale-110 transition-transform">
                      <svg className="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Products */}
          {v5Room && v5Room.products.length > 0 && (
            <div className="card p-3 sm:p-4 mb-4">
              <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-2.5">Products from PPTX</p>
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                {v5Room.products.map((p) => (
                  <div key={p.id} className="rounded-lg overflow-hidden bg-white">
                    {p.image_path ? (
                      <img src={getLocalFileUrl(p.image_path)} alt={p.name}
                        className="w-full aspect-square object-contain p-0.5" />
                    ) : (
                      <div className="w-full aspect-square bg-gray-100" />
                    )}
                    <div className="bg-gray-50 px-1.5 py-1">
                      <p className="text-[9px] sm:text-[10px] text-gray-800 font-medium truncate">{p.name}</p>
                      {p.dimensions && <p className="text-[8px] sm:text-[9px] text-gray-500">{p.dimensions}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI renders */}
          {v5Room && v5Room.generated_images.length > 0 && (
            <div className="card p-3 sm:p-4">
              <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-2.5">AI Renders (Imagen + Gemini)</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {v5Room.generated_images.map((img) => (
                  <div key={img.id} className="rounded-lg overflow-hidden border border-gray-700/30">
                    <img src={getLocalFileUrl(img.image_path)} alt="" className="w-full aspect-video object-cover" />
                    <div className="px-2.5 py-1 flex items-center justify-between bg-surface-900/50">
                      <span className="text-[9px] text-gray-500">v{img.version}</span>
                      <span className="text-[9px] text-gray-600 capitalize">{img.type}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/* ─── Sidebar Item (desktop) ─────────────────────────────── */

function SidebarItem({ room, active, onClick }: { room: typeof V4_ROOMS[0]; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all mb-0.5',
        active ? 'bg-accent/15 text-white border border-accent/20' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-700/30 border border-transparent'
      )}>
      <img src={`/demo/v4rooms/${room.id}/render.png`} alt=""
        className="w-9 h-6 rounded object-cover flex-shrink-0 border border-gray-700/50" />
      <p className={cn('text-[11px] truncate', active ? 'font-semibold' : 'font-medium')}>{room.label}</p>
    </button>
  );
}
