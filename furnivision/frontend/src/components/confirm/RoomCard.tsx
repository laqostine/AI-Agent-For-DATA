import { useState } from 'react';
import type { Room, FurnitureItem } from '@/lib/types';
import { cn } from '@/lib/utils';

interface RoomCardProps {
  room: Room;
  furniture: FurnitureItem[];
  isSelected?: boolean;
  onSelect?: () => void;
  onUpdateName?: (name: string) => void;
  onUpdateArea?: (area: number) => void;
  onRemoveFurniture?: (furnitureId: string) => void;
}

export default function RoomCard({
  room,
  furniture,
  isSelected = false,
  onSelect,
  onUpdateName,
  onUpdateArea,
  onRemoveFurniture,
}: RoomCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(room.name);
  const [editArea, setEditArea] = useState(room.area.toString());

  const handleSave = () => {
    onUpdateName?.(editName);
    const parsedArea = parseFloat(editArea);
    if (!isNaN(parsedArea) && parsedArea > 0) {
      onUpdateArea?.(parsedArea);
    }
    setIsEditing(false);
  };

  const roomFurniture = furniture.filter((f) => room.furniture_ids.includes(f.id));

  return (
    <div
      className={cn(
        'card p-4 transition-all duration-200 cursor-pointer',
        isSelected && 'ring-2 ring-accent border-accent/50',
        !isSelected && 'hover:border-gray-600',
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          {isEditing ? (
            <div className="flex flex-col gap-2">
              <input
                className="input-field text-sm py-1.5"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onClick={(e) => e.stopPropagation()}
              />
              <div className="flex items-center gap-2">
                <input
                  className="input-field text-sm py-1.5 w-24"
                  type="number"
                  step="0.1"
                  value={editArea}
                  onChange={(e) => setEditArea(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
                <span className="text-xs text-gray-500">m2</span>
              </div>
            </div>
          ) : (
            <>
              <h3 className="text-base font-semibold text-gray-100">{room.name}</h3>
              <p className="text-sm text-gray-400">
                {room.room_type} -- {room.area.toFixed(1)} m2
              </p>
            </>
          )}
        </div>
        <button
          className="text-xs text-accent hover:text-accent-light transition-colors px-2 py-1"
          onClick={(e) => {
            e.stopPropagation();
            if (isEditing) handleSave();
            else setIsEditing(true);
          }}
        >
          {isEditing ? 'Save' : 'Edit'}
        </button>
      </div>

      {roomFurniture.length > 0 && (
        <div className="mt-3 border-t border-gray-700/50 pt-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Furniture ({roomFurniture.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {roomFurniture.map((f) => (
              <span
                key={f.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-surface-900 rounded-lg text-xs text-gray-300 border border-gray-700/50"
              >
                {f.thumbnail_url && (
                  <img src={f.thumbnail_url} alt="" className="w-5 h-5 rounded object-cover" />
                )}
                {f.name}
                {onRemoveFurniture && (
                  <button
                    className="text-gray-500 hover:text-danger ml-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemoveFurniture(f.id);
                    }}
                  >
                    x
                  </button>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {roomFurniture.length === 0 && (
        <p className="text-xs text-gray-500 italic mt-2">No furniture assigned</p>
      )}
    </div>
  );
}
