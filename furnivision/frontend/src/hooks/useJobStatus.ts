import { useQuery } from '@tanstack/react-query';
import { getPipelineStatus } from '@/lib/api';
import { usePipelineStore } from '@/stores/pipelineStore';
import type { PipelineState } from '@/lib/types';

export function useJobStatus(jobId: string | null) {
  const updateState = usePipelineStore((s) => s.updateState);

  return useQuery<PipelineState>({
    queryKey: ['pipeline-status', jobId],
    queryFn: async () => {
      if (!jobId) throw new Error('No job ID');
      const state = await getPipelineStatus(jobId);
      updateState(state);
      return state;
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      if (data.status === 'completed' || data.status === 'failed') return false;
      return 3000;
    },
  });
}
