import type { Room } from '@/lib/types';
import { cn } from '@/lib/utils';

interface RoomMapProps {
  rooms: Room[];
  floorplanUrl?: string;
  selectedRoomId?: string;
  onRoomSelect: (roomId: string) => void;
}

const COLORS = [
  'bg-indigo-500/30 border-indigo-500/60 hover:bg-indigo-500/50',
  'bg-green-500/30 border-green-500/60 hover:bg-green-500/50',
  'bg-amber-500/30 border-amber-500/60 hover:bg-amber-500/50',
  'bg-red-500/30 border-red-500/60 hover:bg-red-500/50',
  'bg-purple-500/30 border-purple-500/60 hover:bg-purple-500/50',
  'bg-cyan-500/30 border-cyan-500/60 hover:bg-cyan-500/50',
];

export default function RoomMap({
  rooms,
  floorplanUrl,
  selectedRoomId,
  onRoomSelect,
}: RoomMapProps) {
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
        Room Map
      </h3>
      {floorplanUrl ? (
        <div className="relative rounded-lg overflow-hidden">
          <img src={floorplanUrl} alt="Floor Plan" className="w-full h-auto opacity-40" />
          {/* Room clickable overlays using bounding boxes */}
          {rooms.map((room, idx) => {
            if (!room.geometry?.bounding_box) return null;
            const bb = room.geometry.bounding_box;
            return (
              <button
                key={room.id}
                className={cn(
                  'absolute border-2 rounded transition-all cursor-pointer flex items-center justify-center',
                  COLORS[idx % COLORS.length],
                  room.id === selectedRoomId && 'ring-2 ring-white/50',
                )}
                style={{
                  left: `${bb.x}%`,
                  top: `${bb.y}%`,
                  width: `${bb.width}%`,
                  height: `${bb.height}%`,
                }}
                onClick={() => onRoomSelect(room.id)}
              >
                <span className="text-xs text-white font-semibold drop-shadow-lg">
                  {room.name}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {rooms.map((room, idx) => (
            <button
              key={room.id}
              className={cn(
                'p-3 rounded-lg border-2 text-center transition-all text-sm font-medium text-gray-200',
                COLORS[idx % COLORS.length],
                room.id === selectedRoomId && 'ring-2 ring-white/50',
              )}
              onClick={() => onRoomSelect(room.id)}
            >
              {room.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
