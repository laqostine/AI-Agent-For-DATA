import { useState, useRef } from 'react';
import type { Room } from '@/lib/types';
import ApproveReject from './ApproveReject';
import { cn } from '@/lib/utils';

interface RoomReviewerProps {
  room: Room;
  isOpen: boolean;
  onClose: () => void;
  onApprove: (roomId: string) => void;
  onReject: (roomId: string, feedback: string, issues: string[]) => void;
}

export default function RoomReviewer({
  room,
  isOpen,
  onClose,
  onApprove,
  onReject,
}: RoomReviewerProps) {
  const [currentImageIdx, setCurrentImageIdx] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  if (!isOpen) return null;

  const heroRenders = room.hero_renders ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-surface-800 rounded-2xl border border-gray-700/50 shadow-2xl animate-fade-in">
        {/* Header */}
        <div className="sticky top-0 z-20 flex items-center justify-between p-6 bg-surface-800/95 backdrop-blur-sm border-b border-gray-700/50">
          <div>
            <h2 className="text-xl font-bold text-gray-100">{room.name}</h2>
            <p className="text-sm text-gray-400">{room.room_type}</p>
          </div>
          <div className="flex items-center gap-3">
            {room.qc_score !== undefined && (
              <span
                className={cn(
                  'badge text-sm px-3 py-1',
                  room.qc_score >= 80 && 'bg-success/20 text-success',
                  room.qc_score >= 50 && room.qc_score < 80 && 'bg-warning/20 text-warning',
                  room.qc_score < 50 && 'bg-danger/20 text-danger',
                )}
              >
                QC: {room.qc_score}%
              </span>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-gray-200 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Hero renders */}
        {heroRenders.length > 0 && (
          <div className="p-6">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Hero Renders
            </h3>
            {/* Main image */}
            <div className="rounded-xl overflow-hidden bg-surface-900 mb-3">
              <img
                src={heroRenders[currentImageIdx]}
                alt={`Render ${currentImageIdx + 1}`}
                className="w-full h-auto object-contain max-h-[400px]"
              />
            </div>
            {/* Thumbnail strip */}
            <div ref={scrollRef} className="flex gap-2 overflow-x-auto pb-2">
              {heroRenders.map((url, idx) => (
                <button
                  key={idx}
                  onClick={() => setCurrentImageIdx(idx)}
                  className={cn(
                    'flex-shrink-0 w-20 h-14 rounded-lg overflow-hidden border-2 transition-all',
                    idx === currentImageIdx ? 'border-accent' : 'border-transparent opacity-60 hover:opacity-100',
                  )}
                >
                  <img src={url} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Video */}
        {room.video_url && (
          <div className="px-6 pb-6">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Walkthrough Video
            </h3>
            <video
              src={room.video_url}
              controls
              className="w-full rounded-xl bg-black"
            />
          </div>
        )}

        {/* Approve/Reject */}
        <div className="p-6 border-t border-gray-700/50">
          <ApproveReject
            roomId={room.id}
            currentStatus={room.status}
            onApprove={onApprove}
            onReject={onReject}
          />
        </div>
      </div>
    </div>
  );
}
