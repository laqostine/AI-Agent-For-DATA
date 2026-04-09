import { useQuery } from '@tanstack/react-query';
import { getProject, getExtraction } from '@/lib/api';
import { useProjectStore } from '@/stores/projectStore';
import type { Project, ExtractionResult } from '@/lib/types';

export function useProjectData(projectId: string | undefined) {
  const setProject = useProjectStore((s) => s.setProject);

  const projectQuery = useQuery<Project>({
    queryKey: ['project', projectId],
    queryFn: async () => {
      if (!projectId) throw new Error('No project ID');
      const project = await getProject(projectId);
      setProject(project);
      return project;
    },
    enabled: !!projectId,
  });

  return projectQuery;
}

export function useExtractionData(projectId: string | undefined) {
  const setExtraction = useProjectStore((s) => s.setExtraction);

  return useQuery<ExtractionResult>({
    queryKey: ['extraction', projectId],
    queryFn: async () => {
      if (!projectId) throw new Error('No project ID');
      const extraction = await getExtraction(projectId);
      setExtraction(extraction);
      return extraction;
    },
    enabled: !!projectId,
    // Retry every 2s while extraction isn't ready yet (404 = still processing)
    retry: (failureCount, error: unknown) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404) return failureCount < 30; // retry up to 60s
      return failureCount < 2;
    },
    retryDelay: 2000,
  });
}
