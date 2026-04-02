import axios from 'axios';
import type {
  ApiResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  Project,
  ExtractionResult,
  ConfirmExtractionRequest,
  StartPipelineRequest,
  StartPipelineResponse,
  PipelineState,
  RoomApprovalRequest,
  OutputsResponse,
} from './types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// ---- Project ----

export async function createProject(
  data: CreateProjectRequest,
): Promise<CreateProjectResponse> {
  const res = await api.post<ApiResponse<CreateProjectResponse>>(
    '/projects',
    data,
  );
  return res.data.data;
}

export async function getProject(projectId: string): Promise<Project> {
  const res = await api.get<ApiResponse<Project>>(
    `/projects/${projectId}`,
  );
  return res.data.data;
}

// ---- Upload ----

export async function uploadFloorplan(
  projectId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<{ url: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post<ApiResponse<{ url: string }>>(
    `/projects/${projectId}/floorplan`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    },
  );
  return res.data.data;
}

export async function uploadFurniture(
  projectId: string,
  files: File[],
  onProgress?: (pct: number) => void,
): Promise<{ urls: string[] }> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await api.post<ApiResponse<{ urls: string[] }>>(
    `/projects/${projectId}/furniture`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    },
  );
  return res.data.data;
}

// ---- Extraction ----

export async function getExtraction(
  projectId: string,
): Promise<ExtractionResult> {
  const res = await api.get<ApiResponse<ExtractionResult>>(
    `/projects/${projectId}/extraction`,
  );
  return res.data.data;
}

export async function confirmExtraction(
  data: ConfirmExtractionRequest,
): Promise<void> {
  await api.post(`/projects/${data.project_id}/confirm`, data);
}

// ---- Pipeline ----

export async function startPipeline(
  data: StartPipelineRequest,
): Promise<StartPipelineResponse> {
  const res = await api.post<ApiResponse<StartPipelineResponse>>(
    `/pipeline/start`,
    data,
  );
  return res.data.data;
}

export async function getPipelineStatus(
  jobId: string,
): Promise<PipelineState> {
  const res = await api.get<ApiResponse<PipelineState>>(
    `/pipeline/status/${jobId}`,
  );
  return res.data.data;
}

// ---- Review ----

export async function approveRoom(
  projectId: string,
  data: RoomApprovalRequest,
): Promise<void> {
  await api.post(`/projects/${projectId}/rooms/${data.room_id}/approve`, data);
}

export async function rejectRoom(
  projectId: string,
  data: RoomApprovalRequest,
): Promise<void> {
  await api.post(`/projects/${projectId}/rooms/${data.room_id}/reject`, data);
}

// ---- Outputs ----

export async function getOutputs(
  projectId: string,
): Promise<OutputsResponse> {
  const res = await api.get<ApiResponse<OutputsResponse>>(
    `/projects/${projectId}/outputs`,
  );
  return res.data.data;
}
