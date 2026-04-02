import { useState } from 'react';
import type { FurnitureItem, Room, FurnitureAssignment } from '@/lib/types';
import { cn } from '@/lib/utils';

interface FurnitureAssignerProps {
  furniture: FurnitureItem[];
  rooms: Room[];
  assignments: FurnitureAssignment[];
  onAssign: (furnitureId: string, roomId: string) => void;
  onUnassign: (furnitureId: string, roomId: string) => void;
}

export default function FurnitureAssigner({
  furniture,
  rooms,
  assignments,
  onAssign,
  onUnassign,
}: FurnitureAssignerProps) {
  const [draggedItem, setDraggedItem] = useState<string | null>(null);

  const unassignedFurniture = furniture.filter(
    (f) => !assignments.some((a) => a.furniture_id === f.id),
  );

  const getAssignedFurniture = (roomId: string) =>
    assignments.filter((a) => a.room_id === roomId);

  return (
    <div className="space-y-4">
      {/* Unassigned pool */}
      <div className="card p-4">
        <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Unassigned Furniture ({unassignedFurniture.length})
        </h4>
        <div className="flex flex-wrap gap-2 min-h-[48px]">
          {unassignedFurniture.map((f) => (
            <div
              key={f.id}
              draggable
              onDragStart={() => setDraggedItem(f.id)}
              onDragEnd={() => setDraggedItem(null)}
              className={cn(
                'flex items-center gap-2 px-3 py-2 bg-surface-900 rounded-lg text-sm text-gray-300',
                'border border-gray-700 cursor-grab active:cursor-grabbing hover:border-accent/50 transition-colors',
                draggedItem === f.id && 'opacity-50',
              )}
            >
              {f.thumbnail_url && (
                <img src={f.thumbnail_url} alt="" className="w-8 h-8 rounded object-cover" />
              )}
              <span>{f.name}</span>
            </div>
          ))}
          {unassignedFurniture.length === 0 && (
            <p className="text-xs text-gray-600 italic">All furniture has been assigned</p>
          )}
        </div>
      </div>

      {/* Room targets */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {rooms.map((room) => {
          const assigned = getAssignedFurniture(room.id);
          return (
            <div
              key={room.id}
              className="card p-4 transition-colors"
              onDragOver={(e) => {
                e.preventDefault();
                e.currentTarget.classList.add('ring-2', 'ring-accent/50');
              }}
              onDragLeave={(e) => {
                e.currentTarget.classList.remove('ring-2', 'ring-accent/50');
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.currentTarget.classList.remove('ring-2', 'ring-accent/50');
                if (draggedItem) {
                  onAssign(draggedItem, room.id);
                  setDraggedItem(null);
                }
              }}
            >
              <h4 className="text-sm font-semibold text-gray-200 mb-2">{room.name}</h4>
              <div className="flex flex-wrap gap-1.5 min-h-[36px]">
                {assigned.map((a) => (
                  <span
                    key={a.furniture_id}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-accent/10 border border-accent/30 rounded text-xs text-accent-light"
                  >
                    {a.furniture_name}
                    <button
                      className="text-accent/50 hover:text-danger ml-0.5"
                      onClick={() => onUnassign(a.furniture_id, a.room_id)}
                    >
                      x
                    </button>
                  </span>
                ))}
                {assigned.length === 0 && (
                  <span className="text-xs text-gray-600 italic">
                    Drop furniture here
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
