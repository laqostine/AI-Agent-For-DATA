import { useMemo } from 'react';
import type { Room } from '@/lib/types';
import { cn } from '@/lib/utils';

interface FloorPlanOverlayProps {
  imageUrl: string;
  rooms: Room[];
  selectedRoomId?: string;
  onRoomClick?: (roomId: string) => void;
  imageWidth?: number;
  imageHeight?: number;
}

const ROOM_COLORS = [
  'rgba(99,102,241,0.3)',  // indigo
  'rgba(34,197,94,0.3)',   // green
  'rgba(245,158,11,0.3)',  // amber
  'rgba(239,68,68,0.3)',   // red
  'rgba(168,85,247,0.3)',  // purple
  'rgba(6,182,212,0.3)',   // cyan
  'rgba(236,72,153,0.3)',  // pink
  'rgba(251,146,60,0.3)',  // orange
];

const ROOM_BORDER_COLORS = [
  'rgba(99,102,241,0.8)',
  'rgba(34,197,94,0.8)',
  'rgba(245,158,11,0.8)',
  'rgba(239,68,68,0.8)',
  'rgba(168,85,247,0.8)',
  'rgba(6,182,212,0.8)',
  'rgba(236,72,153,0.8)',
  'rgba(251,146,60,0.8)',
];

export default function FloorPlanOverlay({
  imageUrl,
  rooms,
  selectedRoomId,
  onRoomClick,
  imageWidth = 800,
  imageHeight = 600,
}: FloorPlanOverlayProps) {
  const roomPolygons = useMemo(() => {
    return rooms.map((room, index) => {
      if (!room.geometry?.vertices || room.geometry.vertices.length < 3) return null;
      const points = room.geometry.vertices.map(([x, y]) => `${x},${y}`).join(' ');
      return {
        room,
        points,
        fill: ROOM_COLORS[index % ROOM_COLORS.length],
        stroke: ROOM_BORDER_COLORS[index % ROOM_BORDER_COLORS.length],
        centroid: room.geometry.centroid,
      };
    });
  }, [rooms]);

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-gray-700/50">
      <img
        src={imageUrl}
        alt="Floor Plan"
        className="w-full h-auto"
        draggable={false}
      />
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox={`0 0 ${imageWidth} ${imageHeight}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {roomPolygons.map((data) => {
          if (!data) return null;
          const isSelected = data.room.id === selectedRoomId;
          return (
            <g key={data.room.id} className="cursor-pointer">
              <polygon
                points={data.points}
                fill={isSelected ? data.fill.replace('0.3', '0.5') : data.fill}
                stroke={data.stroke}
                strokeWidth={isSelected ? 3 : 2}
                className={cn(
                  'transition-all duration-200',
                  !isSelected && 'hover:opacity-80',
                )}
                onClick={() => onRoomClick?.(data.room.id)}
              />
              {data.centroid && (
                <text
                  x={data.centroid[0]}
                  y={data.centroid[1]}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="white"
                  fontSize="14"
                  fontWeight="600"
                  className="pointer-events-none select-none"
                  style={{
                    textShadow: '0 1px 3px rgba(0,0,0,0.8)',
                  }}
                >
                  {data.room.name}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
