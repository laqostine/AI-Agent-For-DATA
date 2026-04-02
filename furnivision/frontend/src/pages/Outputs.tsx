import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getOutputs } from '@/lib/api';
import { useProjectData } from '@/hooks/useProjectData';
import { useProjectStore } from '@/stores/projectStore';
import FrameNavigator from '@/components/viewer/FrameNavigator';
import VideoPlayer from '@/components/viewer/VideoPlayer';
import RoomMap from '@/components/viewer/RoomMap';
import type { ViewerManifest, OutputsResponse } from '@/lib/types';
import axios from 'axios';

export default function Outputs() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  useProjectData(projectId);
  const { rooms, currentProject } = useProjectStore();

  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [viewerManifest, setViewerManifest] = useState<ViewerManifest | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const { data: outputs, isLoading } = useQuery<OutputsResponse>({
    queryKey: ['outputs', projectId],
    queryFn: () => getOutputs(projectId!),
    enabled: !!projectId,
  });

  // Select first room by default
  useEffect(() => {
    if (outputs?.rooms && outputs.rooms.length > 0 && !selectedRoomId) {
      setSelectedRoomId(outputs.rooms[0].room_id);
    }
  }, [outputs, selectedRoomId]);

  // Load viewer manifest for selected room
  useEffect(() => {
    if (!selectedRoomId || !outputs) return;
    const roomOutput = outputs.rooms.find((r) => r.room_id === selectedRoomId);
    if (!roomOutput?.viewer_manifest_url) {
      setViewerManifest(null);
      return;
    }

    axios
      .get<ViewerManifest>(roomOutput.viewer_manifest_url)
      .then((res) => setViewerManifest(res.data))
      .catch(() => setViewerManifest(null));
  }, [selectedRoomId, outputs]);

  const selectedRoomOutput = outputs?.rooms.find((r) => r.room_id === selectedRoomId);

  const handleCopyShareLink = () => {
    if (outputs?.share_url) {
      navigator.clipboard.writeText(outputs.share_url);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-accent/30 border-t-accent rounded-full animate-spin" />
          <p className="text-gray-400">Loading outputs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-surface-800/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-100">
                Your room visualisations are ready
              </h1>
              <p className="text-gray-400 mt-1">
                {outputs?.rooms.length ?? 0} rooms -- {currentProject?.name ?? 'Project'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {outputs?.share_url && (
                <button
                  className="btn-secondary flex items-center gap-2"
                  onClick={handleCopyShareLink}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                  {copiedLink ? 'Copied!' : 'Share Link'}
                </button>
              )}
              {outputs?.zip_url && (
                <a href={outputs.zip_url} download className="btn-primary flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download All (ZIP)
                </a>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        {/* Room selector */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
          <div className="lg:col-span-1">
            <RoomMap
              rooms={rooms}
              floorplanUrl={currentProject?.floorplan_url}
              selectedRoomId={selectedRoomId ?? undefined}
              onRoomSelect={setSelectedRoomId}
            />
          </div>

          {/* Room quick stats */}
          <div className="lg:col-span-3">
            <div className="flex gap-4 overflow-x-auto pb-2">
              {outputs?.rooms.map((room) => (
                <button
                  key={room.room_id}
                  className={`card p-4 min-w-[200px] transition-all ${
                    room.room_id === selectedRoomId
                      ? 'ring-2 ring-accent border-accent/50'
                      : 'hover:border-gray-600'
                  }`}
                  onClick={() => setSelectedRoomId(room.room_id)}
                >
                  <h3 className="text-sm font-semibold text-gray-200 mb-1">{room.room_name}</h3>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                      {room.hero_renders.length} renders
                    </span>
                    <span className={`badge text-[10px] ${
                      room.qc_score >= 80 ? 'bg-success/20 text-success' : 'bg-warning/20 text-warning'
                    }`}>
                      QC {room.qc_score}%
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {selectedRoomOutput && (
          <div className="space-y-8 animate-fade-in" key={selectedRoomId}>
            {/* Hero renders grid */}
            <section>
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Hero Renders</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {selectedRoomOutput.hero_renders.map((url, idx) => (
                  <a
                    key={idx}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group relative aspect-[4/3] rounded-xl overflow-hidden bg-surface-800 border border-gray-700/50 hover:border-accent/50 transition-all"
                  >
                    <img
                      src={url}
                      alt={`Render ${idx + 1}`}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                      <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                      </svg>
                    </div>
                    <div className="absolute bottom-2 right-2">
                      <a
                        href={url}
                        download
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 rounded-lg bg-black/60 text-white hover:bg-black/80 transition-colors"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                      </a>
                    </div>
                  </a>
                ))}
              </div>
            </section>

            {/* Video player */}
            {selectedRoomOutput.video_url && (
              <section>
                <h2 className="text-lg font-semibold text-gray-100 mb-4">Walkthrough Video</h2>
                <VideoPlayer
                  src={selectedRoomOutput.video_url}
                  poster={selectedRoomOutput.hero_renders[0]}
                />
              </section>
            )}

            {/* Interactive viewer */}
            <section>
              <h2 className="text-lg font-semibold text-gray-100 mb-2">Interactive Viewer</h2>
              <p className="text-sm text-gray-500 mb-4">
                Use arrow keys, click-drag, or swipe to navigate between frames
              </p>
              <FrameNavigator manifest={viewerManifest} className="h-[500px]" />
            </section>
          </div>
        )}

        {!selectedRoomOutput && outputs && outputs.rooms.length > 0 && (
          <div className="card p-12 text-center">
            <p className="text-gray-500">Select a room to view its outputs</p>
          </div>
        )}

        {outputs && outputs.rooms.length === 0 && (
          <div className="card p-12 text-center">
            <p className="text-gray-500 text-lg mb-4">No outputs available yet</p>
            <button className="btn-primary" onClick={() => navigate('/')}>
              Start New Project
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
