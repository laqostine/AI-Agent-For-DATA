import { useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useJobStatus } from '@/hooks/useJobStatus';
import { usePipelineStore } from '@/stores/pipelineStore';
import PipelineTracker from '@/components/processing/PipelineTracker';
import RoomLane from '@/components/processing/RoomLane';
import LivePreview from '@/components/processing/LivePreview';

export default function Processing() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { jobId, stage, status, rooms, progress } = usePipelineStore();
  const { data: pipelineState } = useJobStatus(jobId);

  // Auto-navigate on completion
  useEffect(() => {
    if (status === 'completed' && projectId) {
      const timer = setTimeout(() => {
        navigate(`/review/${projectId}`);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [status, projectId, navigate]);

  // Find first room with a preview available
  const previewRoom = useMemo(() => {
    return rooms.find((r) => r.preview_url);
  }, [rooms]);

  if (!jobId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="card p-8 max-w-md text-center">
          <p className="text-gray-400 mb-4">No active pipeline job found</p>
          <button className="btn-primary" onClick={() => navigate('/')}>
            Start Over
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-900">
      {/* Header */}
      <header className="border-b border-gray-800 bg-surface-800/50 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-gray-100">Generating Visualisations</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                {status === 'completed'
                  ? 'All done! Redirecting to review...'
                  : status === 'failed'
                    ? 'Pipeline encountered an error'
                    : `Overall progress: ${Math.round(progress)}%`}
              </p>
            </div>
            {status === 'completed' && (
              <span className="badge bg-success/20 text-success text-sm px-4 py-1.5">
                Complete
              </span>
            )}
            {status === 'failed' && (
              <span className="badge bg-danger/20 text-danger text-sm px-4 py-1.5">
                Failed
              </span>
            )}
          </div>

          {/* Pipeline stages tracker */}
          <PipelineTracker currentStage={stage} status={status === 'idle' ? 'running' : status} />
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-6xl mx-auto px-6 py-8 w-full">
        {/* Overall progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">Overall Progress</span>
            <span className="text-sm font-mono text-gray-300">{Math.round(progress)}%</span>
          </div>
          <div className="w-full h-3 bg-surface-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-accent to-accent-light rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Room lanes */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-semibold text-gray-100 mb-2">Room Progress</h2>
            {rooms.map((room) => (
              <RoomLane key={room.room_id} room={room} />
            ))}
            {rooms.length === 0 && (
              <div className="card p-8 text-center">
                <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-gray-500">Waiting for room processing to begin...</p>
              </div>
            )}
          </div>

          {/* Preview panel */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-100 mb-2">Live Preview</h2>
            {previewRoom ? (
              <LivePreview
                previewUrl={previewRoom.preview_url ?? null}
                roomName={previewRoom.room_name}
              />
            ) : (
              <div className="card p-8 text-center">
                <svg className="w-12 h-12 mx-auto text-gray-700 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                </svg>
                <p className="text-sm text-gray-500">
                  Preview will appear when the first frame is rendered
                </p>
              </div>
            )}

            {/* Status info */}
            {pipelineState && (
              <div className="card p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Stage</span>
                  <span className="text-gray-200 capitalize">{pipelineState.stage}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Rooms</span>
                  <span className="text-gray-200">
                    {pipelineState.rooms.filter((r) => r.status === 'completed').length} / {pipelineState.rooms.length}
                  </span>
                </div>
                {pipelineState.estimated_completion && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Est. completion</span>
                    <span className="text-gray-200">
                      {new Date(pipelineState.estimated_completion).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
