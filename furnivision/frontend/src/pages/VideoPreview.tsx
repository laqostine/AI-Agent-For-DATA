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
    return (
      <div className="min-h-screen bg-surface-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-500 mx-auto mb-4" />
          <h2 className="text-xl text-white font-semibold">Generating Walkthrough Videos...</h2>
          <p className="text-gray-400 mt-2">
            {videoCount} / {rooms.length} rooms complete
          </p>
          <div className="w-64 h-2 bg-surface-700 rounded-full mt-4 mx-auto">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all"
              style={{ width: `${rooms.length > 0 ? (videoCount / rooms.length) * 100 : 0}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Video Preview</h1>
            <p className="text-gray-400 mt-1">
              {roomsWithVideo.length} room videos ready
            </p>
          </div>
          <div className="flex items-center gap-3">
            {!hasFinalVideo ? (
              <button
                onClick={() => compileMutation.mutate()}
                disabled={roomsWithVideo.length === 0 || compileMutation.isPending}
                className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
              >
                {compileMutation.isPending ? 'Compiling...' : 'Compile Final Video'}
              </button>
            ) : (
              <a
                href={getFinalVideoUrl(projectId)}
                download
                className="px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors inline-flex items-center gap-2"
              >
                <DownloadIcon />
                Download Final MP4
              </a>
            )}
          </div>
        </div>

        {/* Final Video Player */}
        {hasFinalVideo && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-white mb-3">Final Walkthrough</h2>
            <div className="bg-black rounded-xl overflow-hidden aspect-video">
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
        )}

        {/* Individual Room Videos */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Room Videos</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {rooms.map((room) => (
              <RoomVideoCard
                key={room.id}
                room={room}
                isPlaying={playingRoom === room.id}
                onPlay={() => setPlayingRoom(room.id)}
              />
            ))}
          </div>
        </div>
      </div>
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
    <div className="bg-surface-800 rounded-xl border border-surface-700 overflow-hidden">
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
              <div className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/20 transition-colors">
                <PlayIcon />
              </div>
            )}
            {!hasVideo && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
              </div>
            )}
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-gray-500 text-sm">No preview</span>
          </div>
        )}
      </div>

      {/* Room Info */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white">{room.label}</h3>
          <span
            className={`text-xs px-2 py-1 rounded-full ${
              hasVideo
                ? 'bg-green-600/20 text-green-400'
                : 'bg-yellow-600/20 text-yellow-400'
            }`}
          >
            {hasVideo ? 'Ready' : 'Generating...'}
          </span>
        </div>
        <p className="text-sm text-gray-400 mt-1">
          {room.products.length} products · {room.generated_images.length} renders
        </p>
      </div>
    </div>
  );
}

function PlayIcon() {
  return (
    <svg className="w-14 h-14 text-white drop-shadow-lg" fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );
}
