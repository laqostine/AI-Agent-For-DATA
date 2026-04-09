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
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-sm">
          <div className="relative mx-auto mb-10 w-20 h-20">
            <div className="absolute inset-0 rounded-full border border-white/[0.06]" />
            <div className="absolute inset-0 rounded-full border border-accent/60 border-t-transparent animate-spin" />
            <div className="absolute inset-2.5 rounded-full border border-accent/20 border-b-transparent animate-spin" style={{ animationDirection: 'reverse', animationDuration: '2s' }} />
            <div className="absolute inset-0 flex items-center justify-center">
              <svg className="w-6 h-6 text-accent/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
          </div>
          <h2 className="heading-display text-xl mb-2">Analyzing Specification</h2>
          <p className="text-gray-500 text-sm leading-relaxed">
            Extracting rooms, products, and floor plan layouts from your specification...
          </p>
          <div className="mt-8 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/[0.03] border border-white/[0.06]">
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span className="text-[11px] text-gray-500">Usually takes 30-60 seconds</span>
          </div>
        </div>
      </div>
    );
  }

  if (project?.status === 'failed') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center card p-12 max-w-sm">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/15 flex items-center justify-center mx-auto mb-5">
            <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h2 className="heading-display text-xl mb-2">Extraction Failed</h2>
          <p className="text-gray-500 text-sm mb-8">Something went wrong analyzing the specification.</p>
          <button onClick={() => navigate('/')} className="btn-secondary">Start Over</button>
        </div>
      </div>
    );
  }

  const rooms = extraction?.rooms ?? project?.v5_rooms ?? [];
  const floorPlans = extraction?.floor_plans ?? project?.floor_plans ?? [];
  const totalProducts = extraction?.total_products ?? rooms.reduce((s, r) => s + r.products.length, 0);

  return (
    <div className="min-h-screen">
      {/* Sticky header */}
      <header className="sticky top-0 z-40 bg-surface-950/80 backdrop-blur-xl border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5 mb-0.5">
              <StepBadge step={2} />
              <h1 className="text-sm sm:text-[15px] font-semibold text-white tracking-tight truncate">Review Extraction</h1>
            </div>
            <p className="text-[11px] text-gray-600 ml-7.5 truncate">
              {rooms.length} rooms &middot; {totalProducts} products
            </p>
          </div>
          <button
            onClick={() => approveMutation.mutate()}
            disabled={approveMutation.isPending || rooms.length === 0}
            className="btn-success flex items-center gap-2 flex-shrink-0 text-xs sm:text-sm px-4 sm:px-6 py-2.5 sm:py-3"
          >
            {approveMutation.isPending ? (
              <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> <span className="hidden sm:inline">Approving...</span></>
            ) : (
              <>
                <span className="hidden sm:inline">Approve & Generate</span>
                <span className="sm:hidden">Approve</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {error && (
          <div className="mb-5 p-3.5 rounded-xl bg-red-500/5 border border-red-500/15 text-red-400 text-sm">{error}</div>
        )}

        {/* Floor Plans Row */}
        {floorPlans.length > 0 && (
          <div className="mb-8">
            <h2 className="text-label mb-3">Floor Plans</h2>
            <div className="grid grid-cols-2 gap-4">
              {floorPlans.map((fp) => (
                <div key={fp.id} className="card-hover overflow-hidden group">
                  <img src={getLocalFileUrl(fp.image_path)} alt={fp.floor_name}
                    className="w-full h-40 object-contain bg-white/95 group-hover:scale-[1.02] transition-transform duration-500" />
                  <div className="px-4 py-2.5">
                    <span className="text-label">{fp.floor_name} floor</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Room Cards */}
        <h2 className="text-label mb-4">Rooms</h2>
        <div className="space-y-3">
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
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-accent/15 text-accent text-[10px] font-bold border border-accent/20">
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
      <div className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-white/[0.02] transition-colors duration-200"
        onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-accent/8 border border-accent/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-accent/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
            </svg>
          </div>
          {isEditing ? (
            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
              <input type="text" value={editLabel} onChange={(e) => onEditLabelChange(e.target.value)}
                className="input-field py-1.5 px-3 text-sm w-52" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') onSaveEdit(); if (e.key === 'Escape') onCancelEdit(); }} />
              <button onClick={onSaveEdit} className="text-xs text-emerald-400 hover:text-emerald-300 font-medium">Save</button>
              <button onClick={onCancelEdit} className="text-xs text-gray-600 hover:text-gray-400 font-medium">Cancel</button>
            </div>
          ) : (
            <div>
              <h3 className="text-sm font-semibold text-white leading-tight tracking-tight">{room.label}</h3>
              <p className="text-[11px] text-gray-600 mt-0.5">{room.products.length} products &middot; {room.floor} floor</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isEditing && (
            <button onClick={(e) => { e.stopPropagation(); onStartEdit(); }}
              className="text-[11px] text-gray-600 hover:text-accent px-2.5 py-1 rounded-lg hover:bg-accent/5 transition-all duration-200 font-medium">
              Rename
            </button>
          )}
          <svg className={cn('w-4 h-4 text-gray-600 transition-transform duration-300', expanded && 'rotate-180')}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Products */}
      {expanded && (
        <div className="px-5 pb-5 pt-1 border-t border-white/[0.04]">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2.5 mt-3">
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
    <div className="group rounded-xl overflow-hidden bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.1] transition-all duration-300">
      {product.image_path ? (
        <img src={getLocalFileUrl(product.image_path)} alt={product.name}
          className="w-full aspect-square object-contain bg-white p-1 group-hover:scale-105 transition-transform duration-500" />
      ) : (
        <div className="w-full aspect-square bg-surface-700 flex items-center justify-center">
          <span className="text-gray-700 text-[9px]">No image</span>
        </div>
      )}
      <div className="px-2 py-1.5">
        <p className="text-[10px] text-gray-400 truncate leading-tight" title={product.name}>{product.name}</p>
        {product.dimensions && <p className="text-[9px] text-gray-700 truncate">{product.dimensions}</p>}
      </div>
    </div>
  );
}
