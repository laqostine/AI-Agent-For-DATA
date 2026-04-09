import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  getV5Project,
  compileFinalVideo,
  getFinalVideoUrl,
  getLocalFileUrl,
} from '@/lib/api';
import type { V5Room } from '@/lib/types';
import { cn } from '@/lib/utils';

export default function VideoPreview() {
  const { projectId } = useParams<{ projectId: string }>();
  const [playingRoom, setPlayingRoom] = useState<string | null>(null);

  const { data: project, refetch } = useQuery({
    queryKey: ['v5-project', projectId],
    queryFn: () => getV5Project(projectId!),
    enabled: !!projectId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'generating_videos' ? 5000 : false;
    },
  });

  const compileMutation = useMutation({
    mutationFn: () => compileFinalVideo(projectId!),
    onSuccess: () => refetch(),
  });

  if (!projectId) return <div className="p-8 text-white">No project ID</div>;

  const rooms = project?.v5_rooms ?? [];
  const roomsWithVideo = rooms.filter((r) => r.video_path);
  const isGenerating = project?.status === 'generating_videos';
  const hasFinalVideo = !!project?.final_video_path;

  // Generating videos progress
  if (isGenerating) {
    const videoCount = roomsWithVideo.length;
    const pct = rooms.length > 0 ? (videoCount / rooms.length) * 100 : 0;
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-sm">
          <div className="relative mx-auto mb-10 w-24 h-24">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="2" className="text-white/[0.06]" />
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-accent"
                strokeDasharray={264} strokeDashoffset={264 - (264 * videoCount / Math.max(rooms.length, 1))} strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
            </svg>
            <span className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xl font-semibold text-white tabular-nums">{videoCount}</span>
              <span className="text-[10px] text-gray-600">of {rooms.length}</span>
            </span>
          </div>
          <h2 className="heading-display text-xl mb-2">Generating Videos</h2>
          <p className="text-gray-500 text-sm">Creating walkthrough videos for each room...</p>
          <div className="mt-8 space-y-1.5">
            {rooms.map((r) => (
              <div key={r.id} className="flex items-center gap-2.5 text-xs px-3 py-1.5 rounded-lg">
                <div className={cn('w-1.5 h-1.5 rounded-full',
                  r.video_path ? 'bg-emerald-500' :
                  r.status === 'image_approved' ? 'bg-accent animate-pulse' : 'bg-white/[0.1]')} />
                <span className={cn(
                  r.video_path ? 'text-gray-400' :
                  r.status === 'image_approved' ? 'text-accent' : 'text-gray-700'
                )}>{r.label}</span>
                {r.video_path && (
                  <svg className="w-3 h-3 text-emerald-500 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
            ))}
          </div>
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
            <div className="flex items-center gap-2.5 mb-0.5">
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-accent/15 text-accent text-[10px] font-bold border border-accent/20">4</span>
              <h1 className="text-[15px] font-semibold text-white tracking-tight">Video Preview</h1>
            </div>
            <p className="text-[11px] text-gray-600 ml-7.5">
              {roomsWithVideo.length} of {rooms.length} room videos ready
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!hasFinalVideo ? (
              <button
                onClick={() => compileMutation.mutate()}
                disabled={roomsWithVideo.length === 0 || compileMutation.isPending}
                className="btn-primary flex items-center gap-2"
              >
                {compileMutation.isPending ? (
                  <><div className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" /> Compiling...</>
                ) : 'Compile Final Video'}
              </button>
            ) : (
              <a
                href={getFinalVideoUrl(projectId)}
                download
                className="btn-success flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download Final MP4
              </a>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Final Video Player */}
        {hasFinalVideo && (
          <div className="mb-10">
            <p className="text-label mb-3">Final Walkthrough</p>
            <div className="card overflow-hidden">
              <div className="bg-black aspect-video">
                <video
                  src={getFinalVideoUrl(projectId)}
                  controls
                  className="w-full h-full"
                  poster={roomsWithVideo[0]?.generated_images[0]?.image_path
                    ? getLocalFileUrl(roomsWithVideo[0].generated_images[0].image_path)
                    : undefined}
                />
              </div>
            </div>
          </div>
        )}

        {/* Individual Room Videos */}
        <p className="text-label mb-4">Room Videos</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rooms.map((room) => (
            <RoomVideoCard
              key={room.id}
              room={room}
              isPlaying={playingRoom === room.id}
              onPlay={() => setPlayingRoom(room.id)}
            />
          ))}
        </div>
      </main>
    </div>
  );
}

function RoomVideoCard({
  room,
  isPlaying,
  onPlay,
}: {
  room: V5Room;
  isPlaying: boolean;
  onPlay: () => void;
}) {
  const hasVideo = !!room.video_path;
  const thumbnail = room.generated_images[room.generated_images.length - 1];

  return (
    <div className="card-hover overflow-hidden group">
      {/* Video / Thumbnail */}
      <div className="aspect-video bg-black relative">
        {hasVideo && isPlaying ? (
          <video
            src={getLocalFileUrl(room.video_path!)}
            controls
            autoPlay
            className="w-full h-full"
          />
        ) : thumbnail ? (
          <div className="relative cursor-pointer" onClick={onPlay}>
            <img
              src={getLocalFileUrl(thumbnail.image_path)}
              alt={room.label}
              className="w-full h-full object-cover"
            />
            {hasVideo && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-black/20 transition-colors duration-300">
                <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center group-hover:scale-110 group-hover:bg-white/15 transition-all duration-300">
                  <svg className="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                </div>
              </div>
            )}
            {!hasVideo && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                <div className="w-5 h-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
              </div>
            )}
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-gray-700 text-xs">No preview</span>
          </div>
        )}
      </div>

      {/* Room Info */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white tracking-tight">{room.label}</h3>
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full border',
            hasVideo
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/15'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/15'
          )}>
            {hasVideo ? 'Ready' : 'Generating'}
          </span>
        </div>
        <p className="text-[11px] text-gray-600 mt-1">
          {room.products.length} products &middot; {room.generated_images.length} renders
        </p>
      </div>
    </div>
  );
}
