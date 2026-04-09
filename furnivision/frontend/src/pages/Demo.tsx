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
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-white/[0.06] bg-surface-900/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-shrink-0">
            <img src="/cadre-logo.png" alt="CADRE" className="w-8 h-8 rounded-xl object-contain" />
            <div className="hidden sm:block">
              <h1 className="text-sm font-semibold text-white leading-tight tracking-[0.15em] uppercase">Cadre</h1>
              <p className="text-[10px] text-gray-600 tracking-widest uppercase">Forthing Showroom</p>
            </div>
            <h1 className="sm:hidden text-sm font-semibold text-white tracking-[0.15em] uppercase">Cadre</h1>
          </div>

          {/* Tabs */}
          <div className="flex items-center bg-white/[0.03] rounded-xl p-0.5 border border-white/[0.06]">
            <button onClick={() => setActiveTab('rooms')}
              className={cn('px-4 py-1.5 rounded-[10px] text-[11px] font-medium transition-all duration-300',
                activeTab === 'rooms' ? 'bg-accent text-surface-950 shadow-glow' : 'text-gray-500 hover:text-gray-300')}>
              Rooms
            </button>
            <button onClick={() => setActiveTab('video')}
              className={cn('px-4 py-1.5 rounded-[10px] text-[11px] font-medium transition-all duration-300',
                activeTab === 'video' ? 'bg-accent text-surface-950 shadow-glow' : 'text-gray-500 hover:text-gray-300')}>
              Video
            </button>
          </div>

          <div className="flex items-center gap-4">
            <p className="text-[10px] text-gray-700 hidden md:block tabular-nums">13 rooms &middot; 48 products</p>
            <a href="/" className="text-[11px] text-accent hover:text-accent-light font-medium whitespace-nowrap transition-colors">
              Upload <span className="opacity-50">&rarr;</span>
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

/* Video Tab */

function VideoTab() {
  return (
    <main className="flex-1 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 text-center">
          <p className="text-label text-accent mb-3">Full Walkthrough</p>
          <h2 className="heading-display text-2xl sm:text-3xl mb-2">Forthing Dealership</h2>
          <p className="text-sm text-gray-500">13 rooms generated from one PPTX specification</p>
        </div>
        <div className="card overflow-hidden">
          <video src="/demo/forthing_walkthrough.mp4" controls autoPlay playsInline className="w-full" />
        </div>
        {/* Room thumbnails */}
        <div className="mt-5 grid grid-cols-4 sm:grid-cols-5 md:grid-cols-7 gap-2">
          {V4_ROOMS.map((r) => (
            <div key={r.id} className="rounded-xl overflow-hidden border border-white/[0.06] hover:border-white/[0.12] transition-colors duration-300 group">
              <img src={`/demo/v4rooms/${r.id}/render.png`} alt={r.label}
                className="w-full aspect-video object-cover group-hover:scale-105 transition-transform duration-500" />
              <p className="text-[8px] sm:text-[9px] text-gray-600 px-1.5 py-1 truncate">{r.label}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

/* Rooms Tab */

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
      <div className="lg:hidden border-b border-white/[0.04] bg-surface-900/50">
        <div className="flex overflow-x-auto gap-2 p-3 scrollbar-none">
          {v4Rooms.map((r) => (
            <button key={r.id} onClick={() => onSelectRoom(r.id)}
              className={cn(
                'flex-shrink-0 rounded-xl overflow-hidden border transition-all duration-300',
                selectedRoom === r.id ? 'border-accent/30 ring-1 ring-accent/15' : 'border-white/[0.06]'
              )}>
              <img src={`/demo/v4rooms/${r.id}/render.png`} alt=""
                className="w-20 h-12 object-cover" />
              <p className={cn('text-[9px] px-1.5 py-1 truncate w-20',
                selectedRoom === r.id ? 'text-white font-medium' : 'text-gray-600')}>{r.label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Desktop: sidebar */}
      <aside className="hidden lg:block w-56 border-r border-white/[0.04] bg-surface-900/30 overflow-y-auto flex-shrink-0">
        <div className="p-3">
          <p className="text-[9px] uppercase tracking-[0.2em] text-gray-700 mb-2.5 px-2 font-medium">Ground Floor</p>
          {v4Rooms.filter((r) => r.floor === 'ground').map((r) => (
            <SidebarItem key={r.id} room={r} active={selectedRoom === r.id} onClick={() => onSelectRoom(r.id)} />
          ))}
          <div className="my-3 border-t border-white/[0.04]" />
          <p className="text-[9px] uppercase tracking-[0.2em] text-gray-700 mb-2.5 px-2 font-medium">Mezzanine</p>
          {v4Rooms.filter((r) => r.floor === 'mezzanine').map((r) => (
            <SidebarItem key={r.id} room={r} active={selectedRoom === r.id} onClick={() => onSelectRoom(r.id)} />
          ))}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-5 sm:p-8">
        <div className="max-w-4xl mx-auto">
          {/* Room title + nav */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <p className="text-label text-accent mb-1">Room {idx + 1} of {v4Rooms.length}</p>
              <h2 className="heading-display text-xl sm:text-2xl">{selected.label}</h2>
              <p className="text-[11px] text-gray-600 mt-1">{selected.floor} floor{v5Room ? ` \u00B7 ${v5Room.products.length} products` : ''}</p>
            </div>
            <div className="flex items-center gap-1.5">
              <button onClick={() => onSelectRoom(v4Rooms[Math.max(0, idx - 1)].id)}
                disabled={idx === 0}
                className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-gray-500 hover:text-white hover:border-white/[0.12] disabled:opacity-20 transition-all duration-200">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
              </button>
              <button onClick={() => onSelectRoom(v4Rooms[Math.min(v4Rooms.length - 1, idx + 1)].id)}
                disabled={idx === v4Rooms.length - 1}
                className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-gray-500 hover:text-white hover:border-white/[0.12] disabled:opacity-20 transition-all duration-200">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
              </button>
            </div>
          </div>

          {/* Render + Video */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div className="card overflow-hidden group">
              <div className="px-4 pt-3 pb-2">
                <p className="text-label">AI Render</p>
              </div>
              <img src={`/demo/v4rooms/${selected.id}/render.png`} alt=""
                className="w-full aspect-video object-cover" />
            </div>
            <div className="card overflow-hidden group">
              <div className="px-4 pt-3 pb-2">
                <p className="text-label">Video Walkthrough</p>
              </div>
              {playingVideo === selected.id ? (
                <video src={`/demo/v4rooms/${selected.id}/video.mp4`} autoPlay controls playsInline
                  className="w-full aspect-video object-cover" onEnded={() => onPlayVideo(null)} />
              ) : (
                <div className="relative cursor-pointer" onClick={() => onPlayVideo(selected.id)}>
                  <img src={`/demo/v4rooms/${selected.id}/render.png`} alt=""
                    className="w-full aspect-video object-cover brightness-[.55] group-hover:brightness-[.65] transition-all duration-500" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center group-hover:scale-110 group-hover:bg-white/15 transition-all duration-300">
                      <svg className="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Products */}
          {v5Room && v5Room.products.length > 0 && (
            <div className="card p-5 mb-5">
              <p className="text-label mb-3">Products from Specification</p>
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2.5">
                {v5Room.products.map((p) => (
                  <div key={p.id} className="rounded-xl overflow-hidden bg-white border border-white/[0.06] group hover:shadow-card transition-all duration-300">
                    {p.image_path ? (
                      <img src={getLocalFileUrl(p.image_path)} alt={p.name}
                        className="w-full aspect-square object-contain p-1 group-hover:scale-105 transition-transform duration-500" />
                    ) : (
                      <div className="w-full aspect-square bg-gray-100" />
                    )}
                    <div className="bg-gray-50 px-2 py-1.5">
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
            <div className="card p-5">
              <p className="text-label mb-3">AI Renders</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {v5Room.generated_images.map((img) => (
                  <div key={img.id} className="rounded-xl overflow-hidden border border-white/[0.06] group hover:border-white/[0.1] transition-all duration-300">
                    <img src={getLocalFileUrl(img.image_path)} alt="" className="w-full aspect-video object-cover" />
                    <div className="px-3 py-2 flex items-center justify-between">
                      <span className="text-[10px] text-gray-600 tabular-nums">v{img.version}</span>
                      <span className="text-[10px] text-gray-700 capitalize">{img.type}</span>
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

/* Sidebar Item */

function SidebarItem({ room, active, onClick }: { room: typeof V4_ROOMS[0]; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 px-2 py-2 rounded-xl text-left transition-all duration-200 mb-0.5',
        active
          ? 'bg-accent/10 text-white border border-accent/15'
          : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] border border-transparent'
      )}>
      <img src={`/demo/v4rooms/${room.id}/render.png`} alt=""
        className={cn('w-10 h-6 rounded-lg object-cover flex-shrink-0 border transition-all duration-200',
          active ? 'border-accent/20' : 'border-white/[0.06]')} />
      <p className={cn('text-[11px] truncate', active ? 'font-semibold' : 'font-medium')}>{room.label}</p>
    </button>
  );
}
