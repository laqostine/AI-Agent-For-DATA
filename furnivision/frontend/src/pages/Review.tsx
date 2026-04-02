import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProjectData } from '@/hooks/useProjectData';
import { useProjectStore } from '@/stores/projectStore';
import { approveRoom, rejectRoom } from '@/lib/api';
import RoomReviewer from '@/components/review/RoomReviewer';
import { cn } from '@/lib/utils';
import type { Room } from '@/lib/types';

export default function Review() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { isLoading } = useProjectData(projectId);
  const { rooms, updateRoom } = useProjectStore();

  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);

  const allApproved = rooms.length > 0 && rooms.every((r) => r.status === 'approved');
  const completedRooms = rooms.filter(
    (r) => r.status === 'completed' || r.status === 'approved' || r.status === 'rejected',
  );

  const handleApprove = async (roomId: string) => {
    if (!projectId) return;
    try {
      await approveRoom(projectId, { room_id: roomId, approved: true });
      updateRoom(roomId, { status: 'approved' });
    } catch {
      // handle error silently
    }
  };

  const handleReject = async (roomId: string, feedback: string, issues: string[]) => {
    if (!projectId) return;
    try {
      await rejectRoom(projectId, {
        room_id: roomId,
        approved: false,
        feedback,
        issues,
      });
      updateRoom(roomId, { status: 'rejected' });
    } catch {
      // handle error silently
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-3 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-surface-800/50 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">Review Renders</h1>
            <p className="text-sm text-gray-500">
              {allApproved
                ? 'All rooms approved! Generate final outputs.'
                : `${completedRooms.filter((r) => r.status === 'approved').length} of ${completedRooms.length} rooms approved`}
            </p>
          </div>
          <button
            className="btn-success"
            disabled={!allApproved}
            onClick={() => navigate(`/outputs/${projectId}`)}
          >
            <span className="flex items-center gap-2">
              Generate Final Outputs
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </span>
          </button>
        </div>
      </header>

      {/* Room grid */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {completedRooms.map((room) => {
            const firstRender = room.hero_renders?.[0];
            return (
              <button
                key={room.id}
                className="card overflow-hidden text-left transition-all hover:scale-[1.02] hover:shadow-xl group"
                onClick={() => setSelectedRoom(room)}
              >
                {/* Thumbnail */}
                <div className="relative aspect-video bg-surface-900 overflow-hidden">
                  {firstRender ? (
                    <img
                      src={firstRender}
                      alt={room.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <svg className="w-12 h-12 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                      </svg>
                    </div>
                  )}

                  {/* Status badge */}
                  <div className="absolute top-3 right-3">
                    <span
                      className={cn(
                        'badge backdrop-blur-sm',
                        room.status === 'approved' && 'bg-success/80 text-white',
                        room.status === 'rejected' && 'bg-danger/80 text-white',
                        room.status === 'completed' && 'bg-accent/80 text-white',
                      )}
                    >
                      {room.status === 'approved' && 'Approved'}
                      {room.status === 'rejected' && 'Rejected'}
                      {room.status === 'completed' && 'Pending Review'}
                    </span>
                  </div>

                  {/* QC score */}
                  {room.qc_score !== undefined && (
                    <div className="absolute top-3 left-3">
                      <span
                        className={cn(
                          'badge backdrop-blur-sm',
                          room.qc_score >= 80 && 'bg-success/20 text-success border border-success/30',
                          room.qc_score >= 50 && room.qc_score < 80 && 'bg-warning/20 text-warning border border-warning/30',
                          room.qc_score < 50 && 'bg-danger/20 text-danger border border-danger/30',
                        )}
                      >
                        QC {room.qc_score}%
                      </span>
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-4">
                  <h3 className="text-base font-semibold text-gray-100">{room.name}</h3>
                  <p className="text-sm text-gray-500">
                    {room.room_type} -- {room.area.toFixed(1)} m2
                  </p>
                  {room.hero_renders && (
                    <p className="text-xs text-gray-600 mt-1">
                      {room.hero_renders.length} renders available
                    </p>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {completedRooms.length === 0 && (
          <div className="card p-12 text-center">
            <p className="text-gray-500 text-lg">No rooms ready for review yet</p>
          </div>
        )}
      </main>

      {/* Review modal */}
      {selectedRoom && (
        <RoomReviewer
          room={selectedRoom}
          isOpen={!!selectedRoom}
          onClose={() => setSelectedRoom(null)}
          onApprove={(roomId) => {
            handleApprove(roomId);
            setSelectedRoom(null);
          }}
          onReject={(roomId, feedback, issues) => {
            handleReject(roomId, feedback, issues);
            setSelectedRoom(null);
          }}
        />
      )}
    </div>
  );
}
