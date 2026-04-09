import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getV5Project, getV5Extraction, updateV5Room, approveExtraction, getLocalFileUrl } from '@/lib/api';
import { getDemoProject, getDemoExtraction, DEMO_ID } from '@/lib/demo';
import type { V5Room, V5Product } from '@/lib/types';
import { cn } from '@/lib/utils';

export default function ExtractionReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [editingRoom, setEditingRoom] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState('');
  const [error, setError] = useState<string | null>(null);
  const isDemo = projectId === DEMO_ID;

  const { data: project } = useQuery({
    queryKey: ['v5-project', projectId],
    queryFn: () => isDemo ? getDemoProject() : getV5Project(projectId!),
    enabled: !!projectId,
    refetchInterval: (query) => {
      if (isDemo) return false;
      const s = query.state.data?.status;
      return s === 'extracting' || s === 'uploading' ? 3000 : false;
    },
  });

  const isExtracting = !isDemo && (project?.status === 'extracting' || project?.status === 'uploading');
  const isReady = isDemo || project?.status === 'reviewing_extraction' || project?.status === 'generating_images' || project?.status === 'reviewing_images';

  const { data: extraction } = useQuery({
    queryKey: ['v5-extraction', projectId],
    queryFn: () => isDemo ? getDemoExtraction() : getV5Extraction(projectId!),
    enabled: !!projectId && isReady,
  });

  const updateRoomMutation = useMutation({
    mutationFn: ({ roomId, label }: { roomId: string; label: string }) => updateV5Room(projectId!, roomId, { label }),
    onSuccess: () => { setEditingRoom(null); setError(null); },
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed to update room'),
  });

  const approveMutation = useMutation({
    mutationFn: () => isDemo ? Promise.resolve({ status: 'ok', rooms_count: 13 }) : approveExtraction(projectId!),
    onSuccess: () => navigate(`/image-review/${projectId}`),
    onError: (err: any) => setError(err?.response?.data?.detail ?? 'Failed to approve'),
  });

  if (!projectId) return null;

  // Loading state
  if (isExtracting || (!isReady && !extraction)) {
    return (
      <div className="min-h-screen bg-surface-900 flex items-center justify-center">
        <div className="text-center max-w-sm">
          <div className="relative mx-auto mb-8 w-24 h-24">
            <div className="absolute inset-0 rounded-full border-[3px] border-surface-700" />
            <div className="absolute inset-0 rounded-full border-[3px] border-accent border-t-transparent animate-spin" />
            <div className="absolute inset-3 rounded-full border-[3px] border-purple-500/30 border-b-transparent animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
            <span className="absolute inset-0 flex items-center justify-center text-2xl">📄</span>
          </div>
          <h2 className="text-xl text-white font-bold mb-2">Analyzing Specification</h2>
          <p className="text-gray-400 text-sm leading-relaxed">
            AI is reading slides, extracting rooms, products, and floor plan layouts...
          </p>
          <div className="mt-6 inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-surface-800 border border-surface-700">
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span className="text-xs text-gray-400">Usually takes 30-60 seconds</span>
          </div>
        </div>
      </div>
    );
  }

  if (project?.status === 'failed') {
    return (
      <div className="min-h-screen bg-surface-900 flex items-center justify-center">
        <div className="text-center card p-10 max-w-sm">
          <div className="text-4xl mb-4">😔</div>
          <h2 className="text-xl text-white font-bold mb-2">Extraction Failed</h2>
          <p className="text-gray-400 text-sm mb-6">Something went wrong analyzing the PPTX.</p>
          <button onClick={() => navigate('/')} className="btn-secondary">Try Again</button>
        </div>
      </div>
    );
  }

  const rooms = extraction?.rooms ?? project?.v5_rooms ?? [];
  const floorPlans = extraction?.floor_plans ?? project?.floor_plans ?? [];
  const totalProducts = extraction?.total_products ?? rooms.reduce((s, r) => s + r.products.length, 0);

  return (
    <div className="min-h-screen bg-surface-900">
      {/* Sticky header */}
      <header className="sticky top-0 z-40 bg-surface-900/80 backdrop-blur-md border-b border-gray-800/50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <StepBadge step={2} />
              <h1 className="text-lg font-bold text-white">Review Extraction</h1>
            </div>
            <p className="text-xs text-gray-500">
              {rooms.length} rooms &middot; {totalProducts} products &middot; {floorPlans.length} floor plans
            </p>
          </div>
          <button
            onClick={() => approveMutation.mutate()}
            disabled={approveMutation.isPending || rooms.length === 0}
            className="btn-success flex items-center gap-2"
          >
            {approveMutation.isPending ? (
              <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Approving...</>
            ) : (
              <>Approve All & Generate<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg></>
            )}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/5 border border-red-500/20 text-red-400 text-sm">{error}</div>
        )}

        {/* Floor Plans Row */}
        {floorPlans.length > 0 && (
          <div className="mb-6">
            <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-3">Floor Plans</h2>
            <div className="grid grid-cols-2 gap-3">
              {floorPlans.map((fp) => (
                <div key={fp.id} className="card overflow-hidden group hover:border-gray-600 transition-colors">
                  <img src={getLocalFileUrl(fp.image_path)} alt={fp.floor_name}
                    className="w-full h-40 object-contain bg-white/95 group-hover:scale-[1.02] transition-transform" />
                  <div className="px-3 py-2 flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">{fp.floor_name} floor</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Room Cards */}
        <h2 className="text-xs uppercase tracking-widest text-gray-500 mb-3">Rooms</h2>
        <div className="space-y-4">
          {rooms.map((room) => (
            <RoomCard key={room.id} room={room}
              isEditing={editingRoom === room.id} editLabel={editLabel}
              onStartEdit={() => { setEditingRoom(room.id); setEditLabel(room.label); }}
              onCancelEdit={() => setEditingRoom(null)}
              onSaveEdit={() => updateRoomMutation.mutate({ roomId: room.id, label: editLabel })}
              onEditLabelChange={setEditLabel} />
          ))}
        </div>
      </main>
    </div>
  );
}

function StepBadge({ step }: { step: number }) {
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-accent/20 text-accent text-[10px] font-bold">
      {step}
    </span>
  );
}

function RoomCard({ room, isEditing, editLabel, onStartEdit, onCancelEdit, onSaveEdit, onEditLabelChange }: {
  room: V5Room; isEditing: boolean; editLabel: string;
  onStartEdit: () => void; onCancelEdit: () => void; onSaveEdit: () => void; onEditLabelChange: (v: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 flex items-center justify-between cursor-pointer hover:bg-surface-700/30 transition-colors"
        onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-sm">
            🏠
          </div>
          {isEditing ? (
            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
              <input type="text" value={editLabel} onChange={(e) => onEditLabelChange(e.target.value)}
                className="input-field py-1 px-2 text-sm w-48" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') onSaveEdit(); if (e.key === 'Escape') onCancelEdit(); }} />
              <button onClick={onSaveEdit} className="text-xs text-green-400 hover:text-green-300">Save</button>
              <button onClick={onCancelEdit} className="text-xs text-gray-500 hover:text-gray-300">Cancel</button>
            </div>
          ) : (
            <div>
              <h3 className="text-sm font-semibold text-white leading-tight">{room.label}</h3>
              <p className="text-[11px] text-gray-500">{room.products.length} products &middot; {room.floor} floor</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isEditing && (
            <button onClick={(e) => { e.stopPropagation(); onStartEdit(); }}
              className="text-[11px] text-gray-500 hover:text-accent px-2 py-1 rounded hover:bg-accent/10 transition-colors">
              Rename
            </button>
          )}
          <svg className={cn('w-4 h-4 text-gray-500 transition-transform', expanded && 'rotate-180')}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Products */}
      {expanded && (
        <div className="px-5 pb-4 pt-1 border-t border-gray-800/30">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2 mt-3">
            {room.products.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProductCard({ product }: { product: V5Product }) {
  return (
    <div className="group rounded-lg overflow-hidden bg-surface-900/50 border border-gray-700/30 hover:border-gray-600/50 transition-colors">
      {product.image_path ? (
        <img src={getLocalFileUrl(product.image_path)} alt={product.name}
          className="w-full aspect-square object-contain bg-white p-0.5 group-hover:scale-105 transition-transform" />
      ) : (
        <div className="w-full aspect-square bg-surface-700 flex items-center justify-center">
          <span className="text-gray-600 text-[10px]">No img</span>
        </div>
      )}
      <div className="px-1.5 py-1">
        <p className="text-[10px] text-gray-300 truncate leading-tight" title={product.name}>{product.name}</p>
        {product.dimensions && <p className="text-[9px] text-gray-600 truncate">{product.dimensions}</p>}
      </div>
    </div>
  );
}
