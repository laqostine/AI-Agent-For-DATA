import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getV5Project, submitRoomFeedback, approveRoomImage, regenerateRoom, generateVideos, getLocalFileUrl } from '@/lib/api';
import type { RegionSelect } from '@/lib/api';
import { getDemoProject, DEMO_ID } from '@/lib/demo';
import RegionSelector from '@/components/review/RegionSelector';
import type { V5Room } from '@/lib/types';
import { cn } from '@/lib/utils';

export default function ImageReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [selectedRoom, setSelectedRoom] = useState<string | null>(null);
  const isDemo = projectId === DEMO_ID;

  const { data: project, refetch } = useQuery({
    queryKey: ['v5-project', projectId],
    queryFn: () => isDemo ? getDemoProject() : getV5Project(projectId!),
    enabled: !!projectId,
    refetchInterval: isDemo ? false : 5000,
  });

  const genVideosMutation = useMutation({
    mutationFn: () => isDemo ? Promise.resolve({ status: 'ok', rooms_count: 13 }) : generateVideos(projectId!),
    onSuccess: () => navigate(`/video-preview/${projectId}`),
  });

  if (!projectId) return null;
  const rooms = project?.v5_rooms ?? [];
  const approvedCount = rooms.filter((r) => ['image_approved', 'video_ready', 'complete'].includes(r.status)).length;
  const readyCount = rooms.filter((r) => ['image_ready', 'image_approved', 'video_ready', 'complete'].includes(r.status)).length;
  const allApproved = rooms.length > 0 && approvedCount === rooms.length;

  // Generating images — progress view
  if (project?.status === 'generating_images' && readyCount < rooms.length) {
    const pct = rooms.length > 0 ? (readyCount / rooms.length) * 100 : 0;
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="relative mx-auto mb-10 w-24 h-24">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="2" className="text-white/[0.06]" />
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-accent"
                strokeDasharray={264} strokeDashoffset={264 - (264 * readyCount / Math.max(rooms.length, 1))} strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
            </svg>
            <span className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xl font-semibold text-white tabular-nums">{readyCount}</span>
              <span className="text-[10px] text-gray-600">of {rooms.length}</span>
            </span>
          </div>
          <h2 className="heading-display text-xl mb-2">Generating Room Images</h2>
          <p className="text-gray-500 text-sm">Imagen 4 base render + Gemini Flash refinement</p>
          <div className="mt-8 space-y-1.5">
            {rooms.map((r) => (
              <div key={r.id} className="flex items-center gap-2.5 text-xs px-3 py-1.5 rounded-lg hover:bg-white/[0.02] transition-colors">
                <div className={cn('w-1.5 h-1.5 rounded-full transition-colors',
                  r.status === 'image_ready' || r.status === 'image_approved' ? 'bg-emerald-500' :
                  r.status === 'generating' ? 'bg-accent animate-pulse' : 'bg-white/[0.1]')} />
                <span className={cn(
                  r.status === 'generating' ? 'text-accent' :
                  r.status === 'image_ready' || r.status === 'image_approved' ? 'text-gray-400' :
                  'text-gray-700'
                )}>
                  {r.label}
                </span>
                {r.status === 'generating' && (
                  <span className="text-[10px] text-accent/60 ml-auto">Rendering...</span>
                )}
              </div>
            ))}
          </div>
          {/* Progress bar */}
          <div className="mt-6 w-full h-0.5 bg-white/[0.06] rounded-full overflow-hidden">
            <div className="h-full bg-accent rounded-full transition-all duration-1000 ease-out" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-surface-950/80 backdrop-blur-xl border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-accent/15 text-accent text-[10px] font-bold border border-accent/20">3</span>
              <h1 className="text-[15px] font-semibold text-white tracking-tight">Review Images</h1>
            </div>
            <div className="flex items-center gap-3 ml-7.5">
              <p className="text-[11px] text-gray-600 tabular-nums">{approvedCount} of {rooms.length} approved</p>
              <div className="w-28 h-1 bg-white/[0.06] rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${rooms.length ? (approvedCount / rooms.length) * 100 : 0}%` }} />
              </div>
            </div>
          </div>
          <button onClick={() => genVideosMutation.mutate()} disabled={!allApproved || genVideosMutation.isPending}
            className="btn-primary flex items-center gap-2">
            {genVideosMutation.isPending ? 'Starting...' : 'Generate Videos'}
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-3">
        {rooms.map((room) => (
          <RoomImageCard key={room.id} room={room} projectId={projectId}
            isExpanded={selectedRoom === room.id}
            onToggle={() => setSelectedRoom(selectedRoom === room.id ? null : room.id)}
            onRefresh={refetch} />
        ))}
      </main>
    </div>
  );
}

function RoomImageCard({ room, projectId, isExpanded, onToggle, onRefresh }: {
  room: V5Room; projectId: string; isExpanded: boolean; onToggle: () => void; onRefresh: () => void;
}) {
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [region, setRegion] = useState<RegionSelect | null>(null);

  const feedbackMut = useMutation({
    mutationFn: () => submitRoomFeedback(projectId, room.id, { feedback, region }),
    onSuccess: () => { setFeedback(''); setRegion(null); setError(null); onRefresh(); },
    onError: (e: any) => setError(e?.response?.data?.detail ?? 'Edit failed'),
  });
  const approveMut = useMutation({
    mutationFn: () => approveRoomImage(projectId, room.id),
    onSuccess: () => { setError(null); onRefresh(); },
    onError: (e: any) => setError(e?.response?.data?.detail ?? 'Approve failed'),
  });
  const regenMut = useMutation({
    mutationFn: () => regenerateRoom(projectId, room.id),
    onSuccess: () => { setError(null); onRefresh(); },
    onError: (e: any) => setError(e?.response?.data?.detail ?? 'Regenerate failed'),
  });

  const latest = room.generated_images[room.generated_images.length - 1];
  const isApproved = ['image_approved', 'video_ready', 'complete'].includes(room.status);
  const isGen = room.status === 'generating';

  return (
    <div className={cn('card overflow-hidden transition-all duration-300', isApproved && 'border-emerald-500/20')}>
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-white/[0.02] transition-colors duration-200" onClick={onToggle}>
        <div className="flex items-center gap-3.5">
          {latest ? (
            <img src={getLocalFileUrl(latest.image_path)} alt="" className="w-14 h-9 object-cover rounded-lg border border-white/[0.08]" />
          ) : (
            <div className="w-14 h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center">
              {isGen ? <div className="w-3 h-3 border-2 border-accent/30 border-t-accent rounded-full animate-spin" /> : <span className="text-[10px] text-gray-700">&mdash;</span>}
            </div>
          )}
          <div>
            <h3 className="text-sm font-semibold text-white tracking-tight">{room.label}</h3>
            <p className="text-[11px] text-gray-600">{room.products.length} products{room.generated_images.length > 0 && ` \u00B7 v${latest?.version}`}{room.feedback.length > 0 && ` \u00B7 ${room.feedback.length} edits`}</p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          {isApproved && <span className="badge-success">Approved</span>}
          {isGen && <span className="badge-accent animate-pulse">Generating</span>}
          <svg className={cn('w-4 h-4 text-gray-700 transition-transform duration-300', isExpanded && 'rotate-180')} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" /></svg>
        </div>
      </div>

      {/* Expanded */}
      {isExpanded && (
        <div className="border-t border-white/[0.04] p-5 animate-fade-in">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Products column */}
            <div className="lg:col-span-2">
              <p className="text-label mb-3">Product References</p>
              <div className="grid grid-cols-3 gap-2">
                {room.products.map((p) => (
                  <div key={p.id} className="rounded-lg overflow-hidden bg-white border border-white/[0.06]">
                    {p.image_path ? (
                      <img src={getLocalFileUrl(p.image_path)} alt={p.name} className="w-full aspect-square object-contain p-1" />
                    ) : (
                      <div className="w-full aspect-square bg-gray-100" />
                    )}
                    <p className="text-[9px] text-gray-700 px-1.5 py-1 truncate bg-gray-50 font-medium">{p.name}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Generated image column */}
            <div className="lg:col-span-3">
              <p className="text-label mb-3">
                AI Generated {latest && <span className="text-gray-700 normal-case">v{latest.version} &middot; {latest.type}</span>}
              </p>
              {latest && !isApproved ? (
                <RegionSelector
                  imageUrl={getLocalFileUrl(latest.image_path)}
                  selectedRegion={region}
                  onRegionSelect={setRegion}
                />
              ) : latest ? (
                <img src={getLocalFileUrl(latest.image_path)} alt="" className="w-full rounded-xl border border-white/[0.06]" />
              ) : (
                <div className="w-full aspect-video bg-white/[0.03] rounded-xl border border-white/[0.06] flex items-center justify-center">
                  {isGen ? <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
                    : <span className="text-gray-700 text-sm">No image</span>}
                </div>
              )}

              {/* Version thumbnails */}
              {room.generated_images.length > 1 && (
                <div className="flex gap-2 mt-3 overflow-x-auto scrollbar-none">
                  {room.generated_images.map((img) => (
                    <img key={img.id} src={getLocalFileUrl(img.image_path)} alt=""
                      className="w-16 h-10 object-cover rounded-lg border border-white/[0.06] flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity" />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          {latest && !isApproved && (
            <div className="mt-6 pt-5 border-t border-white/[0.04]">
              {error && <div className="mb-3 p-3 rounded-xl bg-red-500/5 border border-red-500/15 text-red-400 text-xs">{error}</div>}
              <div className="flex gap-2">
                <input type="text" value={feedback} onChange={(e) => setFeedback(e.target.value)}
                  placeholder={region ? 'Describe what to change in the selected region...' : 'Feedback: e.g. chairs need casters, wrong table color...'}
                  className="input-field text-sm"
                  onKeyDown={(e) => { if (e.key === 'Enter' && feedback.trim()) feedbackMut.mutate(); }} />
                <button onClick={() => feedbackMut.mutate()} disabled={!feedback.trim() || feedbackMut.isPending}
                  className="btn-secondary px-4 py-2.5 text-sm whitespace-nowrap">
                  {feedbackMut.isPending ? '...' : 'Re-edit'}
                </button>
                <button onClick={() => regenMut.mutate()} disabled={regenMut.isPending}
                  className="btn-secondary px-4 py-2.5 text-sm whitespace-nowrap">Regen</button>
                <button onClick={() => approveMut.mutate()} disabled={approveMut.isPending}
                  className="btn-success px-5 py-2.5 text-sm whitespace-nowrap flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                  Approve
                </button>
              </div>
              {room.feedback.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {room.feedback.map((fb, i) => (
                    <span key={i} className="text-[10px] text-gray-600 bg-white/[0.04] border border-white/[0.06] px-2.5 py-0.5 rounded-full">
                      Edit {i + 1}: {fb}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
