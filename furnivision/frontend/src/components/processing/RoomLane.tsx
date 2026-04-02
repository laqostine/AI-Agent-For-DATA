import type { RoomPipelineState } from '@/lib/types';
import FrameGrid from './FrameGrid';
import { cn } from '@/lib/utils';

interface RoomLaneProps {
  room: RoomPipelineState;
}

export default function RoomLane({ room }: RoomLaneProps) {
  const statusColor = {
    queued: 'text-gray-500',
    processing: 'text-accent-light',
    completed: 'text-success',
    failed: 'text-danger',
  }[room.status];

  const statusLabel = {
    queued: 'Queued',
    processing: `${room.current_stage} -- ${Math.round(room.progress)}%`,
    completed: 'Complete',
    failed: 'Failed',
  }[room.status];

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'w-2.5 h-2.5 rounded-full',
              room.status === 'queued' && 'bg-gray-500',
              room.status === 'processing' && 'bg-accent animate-pulse',
              room.status === 'completed' && 'bg-success',
              room.status === 'failed' && 'bg-danger',
            )}
          />
          <h3 className="text-sm font-semibold text-gray-200">{room.room_name}</h3>
        </div>
        <span className={cn('text-xs font-medium', statusColor)}>{statusLabel}</span>
      </div>

      <FrameGrid frames={room.frames} />

      {room.error && (
        <p className="text-xs text-danger mt-2">{room.error}</p>
      )}
    </div>
  );
}
