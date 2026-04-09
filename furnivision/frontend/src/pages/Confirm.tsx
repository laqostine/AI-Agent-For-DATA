import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useExtractionData } from '@/hooks/useProjectData';
import { useProjectStore } from '@/stores/projectStore';
import { usePipelineStore } from '@/stores/pipelineStore';
import { confirmExtraction, startPipeline } from '@/lib/api';
import RoomCard from '@/components/confirm/RoomCard';
import FurnitureAssigner from '@/components/confirm/FurnitureAssigner';
import MissingFieldsForm from '@/components/confirm/MissingFieldsForm';
import FloorPlanOverlay from '@/components/confirm/FloorPlanOverlay';
import type { FurnitureAssignment } from '@/lib/types';
import { cn } from '@/lib/utils';

export default function Confirm() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { isLoading, error: fetchError } = useExtractionData(projectId);

  const {
    rooms,
    furniture,
    assignments,
    missingFields,
    missingFieldValues,
    extraction,
    brief,
    updateRoom,
    setAssignments,
    setMissingFieldValue,
  } = useProjectStore();

  const setJobId = usePipelineStore((s) => s.setJobId);

  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [mode, setMode] = useState<'all_rooms' | 'single_room'>('all_rooms');
  const [singleRoomId, setSingleRoomId] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (rooms.length > 0 && !selectedRoomId) {
      setSelectedRoomId(rooms[0].id);
    }
    if (rooms.length > 0 && !singleRoomId) {
      setSingleRoomId(rooms[0].id);
    }
  }, [rooms, selectedRoomId, singleRoomId]);

  const handleAssign = (furnitureId: string, roomId: string) => {
    const item = furniture.find((f) => f.id === furnitureId);
    if (!item) return;
    const room = rooms.find((r) => r.id === roomId);
    if (!room) return;

    const newAssignment: FurnitureAssignment = {
      furniture_id: furnitureId,
      furniture_name: item.name,
      room_id: roomId,
      room_name: room.name,
      confidence: 1.0,
    };

    setAssignments([
      ...assignments.filter((a) => a.furniture_id !== furnitureId),
      newAssignment,
    ]);
  };

  const handleUnassign = (furnitureId: string, _roomId: string) => {
    setAssignments(assignments.filter((a) => a.furniture_id !== furnitureId));
  };

  const handleStartGeneration = async () => {
    if (!projectId) return;
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await confirmExtraction({
        project_id: projectId,
        rooms,
        assignments,
        brief_updates: brief,
        missing_field_values: missingFieldValues,
      });

      const { job_id } = await startPipeline({
        project_id: projectId,
        mode,
        target_room_id: mode === 'single_room' ? singleRoomId : undefined,
      });

      setJobId(job_id, projectId);
      navigate(`/processing/${projectId}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to start generation';
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-3 border-accent/30 border-t-accent rounded-full animate-spin" />
          <p className="text-gray-400">Analysing your floor plan...</p>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="card p-8 max-w-md text-center">
          <p className="text-danger mb-4">Failed to load extraction data</p>
          <button className="btn-primary" onClick={() => navigate('/')}>
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-surface-800/50 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-100">Confirm Extraction</h1>
            <p className="text-sm text-gray-500">
              Review detected rooms and furniture assignments
            </p>
          </div>
          <button
            className="text-sm text-gray-400 hover:text-gray-200"
            onClick={() => navigate('/')}
          >
            Back to Upload
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-6 py-6 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left: Floor plan */}
          <div className="lg:col-span-3 space-y-6">
            {extraction?.floorplan_image_url && (
              <FloorPlanOverlay
                imageUrl={extraction.floorplan_image_url}
                rooms={rooms}
                selectedRoomId={selectedRoomId ?? undefined}
                onRoomClick={setSelectedRoomId}
              />
            )}

            {/* Furniture Assigner */}
            <div>
              <h3 className="text-lg font-semibold text-gray-100 mb-3">Furniture Assignments</h3>
              <FurnitureAssigner
                furniture={furniture}
                rooms={rooms}
                assignments={assignments}
                onAssign={handleAssign}
                onUnassign={handleUnassign}
              />
            </div>
          </div>

          {/* Right: Room cards */}
          <div className="lg:col-span-2 space-y-4">
            <h3 className="text-lg font-semibold text-gray-100">
              Detected Rooms ({rooms.length})
            </h3>
            <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
              {rooms.map((room) => (
                <RoomCard
                  key={room.id}
                  room={room}
                  furniture={furniture.filter((f) =>
                    assignments.some(
                      (a) => a.room_id === room.id && a.furniture_id === f.id,
                    ),
                  )}
                  isSelected={selectedRoomId === room.id}
                  onSelect={() => setSelectedRoomId(room.id)}
                  onUpdateName={(name) => updateRoom(room.id, { name })}
                  onUpdateArea={(area) => updateRoom(room.id, { area })}
                  onRemoveFurniture={(fId) => handleUnassign(fId, room.id)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Missing fields */}
        {missingFields.length > 0 && (
          <div className="mt-8">
            <MissingFieldsForm
              fields={missingFields}
              values={missingFieldValues}
              onChange={setMissingFieldValue}
            />
          </div>
        )}

        {/* Mode toggle + submit */}
        <div className="mt-8 card p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
            <span className="text-sm font-medium text-gray-300">Generation Mode:</span>
            <div className="flex gap-2">
              <button
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  mode === 'all_rooms'
                    ? 'bg-accent text-white'
                    : 'bg-surface-900 text-gray-400 border border-gray-700 hover:border-gray-500',
                )}
                onClick={() => setMode('all_rooms')}
              >
                All Rooms
              </button>
              <button
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  mode === 'single_room'
                    ? 'bg-accent text-white'
                    : 'bg-surface-900 text-gray-400 border border-gray-700 hover:border-gray-500',
                )}
                onClick={() => setMode('single_room')}
              >
                Single Room (test)
              </button>
            </div>

            {mode === 'single_room' && (
              <select
                className="input-field w-auto"
                value={singleRoomId}
                onChange={(e) => setSingleRoomId(e.target.value)}
              >
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {submitError && (
            <div className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
              {submitError}
            </div>
          )}

          <div className="flex justify-end">
            <button
              className="btn-success text-lg px-8 py-4"
              onClick={handleStartGeneration}
              disabled={isSubmitting || rooms.length === 0}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Starting...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Start Generation
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </span>
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
