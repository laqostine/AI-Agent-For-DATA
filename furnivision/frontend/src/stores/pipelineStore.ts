import { create } from 'zustand';
import type { PipelineState, PipelineStage, RoomPipelineState } from '@/lib/types';

interface PipelineStore {
  jobId: string | null;
  projectId: string | null;
  stage: PipelineStage;
  status: PipelineState['status'] | 'idle';
  rooms: RoomPipelineState[];
  progress: number;
  startedAt: string | null;
  estimatedCompletion: string | null;

  setJobId: (jobId: string, projectId: string) => void;
  updateState: (state: PipelineState) => void;
  reset: () => void;
}

export const usePipelineStore = create<PipelineStore>((set) => ({
  jobId: null,
  projectId: null,
  stage: 'parse',
  status: 'idle',
  rooms: [],
  progress: 0,
  startedAt: null,
  estimatedCompletion: null,

  setJobId: (jobId, projectId) => set({ jobId, projectId, status: 'running' }),

  updateState: (state) =>
    set({
      stage: state.stage,
      status: state.status,
      rooms: state.rooms,
      progress: state.progress,
      startedAt: state.started_at,
      estimatedCompletion: state.estimated_completion ?? null,
    }),

  reset: () =>
    set({
      jobId: null,
      projectId: null,
      stage: 'parse',
      status: 'idle',
      rooms: [],
      progress: 0,
      startedAt: null,
      estimatedCompletion: null,
    }),
}));
