import { useQuery } from '@tanstack/react-query';
import { getPipelineStatus } from '@/lib/api';
import { usePipelineStore } from '@/stores/pipelineStore';
import type { PipelineState } from '@/lib/types';

export function useJobStatus(projectId: string | null) {
  const updateState = usePipelineStore((s) => s.updateState);

  return useQuery<PipelineState>({
    queryKey: ['pipeline-status', projectId],
    queryFn: async () => {
      if (!projectId) throw new Error('No project ID');
      const state = await getPipelineStatus(projectId);
      updateState(state);
      return state;
    },
    enabled: !!projectId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      if (data.status === 'completed' || data.status === 'failed') return false;
      return 3000;
    },
  });
}
