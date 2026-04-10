import axios from 'axios';
import type {
  CreateProjectRequest,
  CreateProjectResponse,
  Project,
  ExtractionResult,
  ConfirmExtractionRequest,
  StartPipelineRequest,
  StartPipelineResponse,
  PipelineState,
  RoomPipelineState,
  RoomApprovalRequest,
  OutputsResponse,
  V5Project,
  V5ExtractionResponse,
  V5Room,
  V5GeneratedImage,
} from './types';

const API_BASE = (import.meta as any).env?.DEV
  ? '/api/v1'  // Vite proxy in dev
  : 'https://furnivision-api-production.up.railway.app/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// ---- Project ----

export async function createProject(
  data: CreateProjectRequest,
): Promise<CreateProjectResponse> {
  const res = await api.post<CreateProjectResponse>('/projects', data);
  return res.data;
}

export async function getProject(projectId: string): Promise<Project> {
  const res = await api.get<Project>(`/projects/${projectId}`);
  return res.data;
}

// ---- Upload ----

export async function uploadFloorplan(
  projectId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<{ file_id: string; gcs_path: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post<{ file_id: string; gcs_path: string }>(
    `/projects/${projectId}/upload/floorplan`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    },
  );
  return res.data;
}

export async function uploadFurniture(
  projectId: string,
  files: File[],
  onProgress?: (pct: number) => void,
): Promise<{ files: Array<{ file_id: string; filename: string; gcs_path: string }> }> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await api.post<{ files: Array<{ file_id: string; filename: string; gcs_path: string }> }>(
    `/projects/${projectId}/upload/furniture`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    },
  );
  return res.data;
}

// ---- Extraction ----

interface BackendExtraction {
  project_id: string;
  rooms: Array<{ id: string; label: string; area_sqm_estimated?: number; polygon_relative?: number[][] }>;
  furniture_items: Array<{ furniture_image_index: number; item_name: string; item_type?: string; color_primary?: string; material?: string }>;
  furniture_assignments: Array<{ furniture_image_index: number; room_id: string; item_name: string; confidence: number }>;
  missing_fields: Array<{ field: string; question: string; default_guess?: string | number | null; importance: string }>;
  confidence_overall: number;
}

function adaptExtraction(b: BackendExtraction): ExtractionResult {
  const rooms = b.rooms.map((r) => ({
    id: r.id,
    name: r.label,
    room_type: r.label,
    area: r.area_sqm_estimated ?? 0,
    geometry: r.polygon_relative?.length
      ? {
          vertices: r.polygon_relative as [number, number][],
          area: r.area_sqm_estimated ?? 0,
          centroid: [0.5, 0.5] as [number, number],
          bounding_box: { x: 0, y: 0, width: 1, height: 1 },
        }
      : undefined,
    furniture_ids: b.furniture_assignments
      .filter((a) => a.room_id === r.id)
      .map((a) => String(a.furniture_image_index)),
    status: 'pending' as const,
  }));

  const furniture = b.furniture_items.map((fi) => ({
    id: String(fi.furniture_image_index),
    name: fi.item_name,
    category: fi.item_type ?? 'other',
    color: fi.color_primary ?? undefined,
    material: fi.material ?? undefined,
  }));

  const assignments = b.furniture_assignments.map((a) => {
    const room = b.rooms.find((r) => r.id === a.room_id);
    return {
      furniture_id: String(a.furniture_image_index),
      furniture_name: a.item_name,
      room_id: a.room_id,
      room_name: room?.label ?? a.room_id,
      confidence: a.confidence,
    };
  });

  const missing_fields = b.missing_fields.map((mf) => {
    const isNumber = typeof mf.default_guess === 'number' ||
      /height|area|width|length|count|_m$|_sqm/.test(mf.field);
    return {
      field_name: mf.field,
      label: mf.question,
      field_type: (isNumber ? 'number' : 'text') as 'text' | 'number' | 'select',
      default_value: mf.default_guess ?? undefined,
      agent_guess: mf.default_guess ?? undefined,
      required: mf.importance === 'critical',
    };
  });

  return {
    project_id: b.project_id,
    rooms,
    furniture,
    assignments,
    missing_fields,
    floorplan_image_url: '',
    confidence: b.confidence_overall,
  };
}

export async function getExtraction(
  projectId: string,
): Promise<ExtractionResult> {
  const res = await api.get<BackendExtraction>(`/projects/${projectId}/extraction`);
  return adaptExtraction(res.data);
}

export async function confirmExtraction(
  data: ConfirmExtractionRequest,
): Promise<void> {
  await api.post(`/projects/${data.project_id}/confirm/extraction`, data);
}

// ---- Pipeline ----

export async function startPipeline(
  data: StartPipelineRequest,
): Promise<StartPipelineResponse> {
  const res = await api.post<StartPipelineResponse>(
    `/projects/${data.project_id}/pipeline/start`,
    data,
  );
  return res.data;
}

// Backend pipeline status shape (differs from frontend PipelineState)
interface BackendPipelineStatus {
  project_id: string;
  job_id: string;
  current_stage: number;
  stage_name: string;
  rooms: Array<{
    room_id: string;
    label: string;
    status: string;
    frames: Array<{ frame_idx: number; frame_type: string; status: string; gcs_url: string | null }>;
    preview_url: string | null;
    hero_frame_urls: string[];
    video_url: string | null;
    qc_score: number | null;
    rejection_count: number;
    rejection_feedback: string | null;
  }>;
  gate_1_confirmed: boolean;
  gate_2_rooms_approved: Record<string, boolean>;
  started_at: string;
  estimated_complete_at: string | null;
  error: string | null;
}

function adaptPipelineStatus(b: BackendPipelineStatus): PipelineState {
  const stageMap: Record<string, PipelineState['stage']> = {
    initializing: 'parse',
    parsing: 'parse',
    planning: 'plan',
    generating: 'generate',
    validating: 'validate',
    animating: 'animate',
  };

  const rooms: RoomPipelineState[] = b.rooms.map((r) => {
    const completedFrames = r.frames.filter((f) => f.status === 'complete').length;
    const progress = r.frames.length > 0 ? Math.round((completedFrames / r.frames.length) * 100) : 0;
    const roomStatusMap: Record<string, RoomPipelineState['status']> = {
      pending: 'queued',
      planning: 'processing',
      generating: 'processing',
      validating: 'processing',
      animating: 'processing',
      complete: 'completed',
      rejected: 'failed',
      failed: 'failed',
    };
    return {
      room_id: r.room_id,
      room_name: r.label,
      status: roomStatusMap[r.status] ?? 'queued',
      current_stage: stageMap[b.stage_name] ?? 'parse',
      frames: r.frames.map((f) => ({
        frame_index: f.frame_idx,
        status: (f.status === 'complete' ? 'completed' : f.status) as 'pending' | 'generating' | 'completed' | 'failed',
        image_url: f.gcs_url ?? undefined,
        is_keyframe: f.frame_type === 'keyframe',
      })),
      progress,
      preview_url: r.preview_url ?? undefined,
    };
  });

  const completedRooms = rooms.filter((r) => r.status === 'completed').length;
  const progress = rooms.length > 0 ? Math.round((completedRooms / rooms.length) * 100) : 0;

  let status: PipelineState['status'] = 'running';
  if (b.error) status = 'failed';
  else if (rooms.length > 0 && rooms.every((r) => r.status === 'completed')) status = 'completed';

  return {
    job_id: b.job_id,
    project_id: b.project_id,
    stage: stageMap[b.stage_name] ?? 'parse',
    status,
    rooms,
    progress,
    started_at: b.started_at,
    estimated_completion: b.estimated_complete_at ?? undefined,
  };
}

export async function getPipelineStatus(projectId: string): Promise<PipelineState> {
  const res = await api.get<BackendPipelineStatus>(`/projects/${projectId}/pipeline/status`);
  return adaptPipelineStatus(res.data);
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

export async function getOutputs(projectId: string): Promise<OutputsResponse> {
  const res = await api.get<OutputsResponse>(`/projects/${projectId}/outputs`);
  return res.data;
}

// ---- V5 Human-in-the-Loop API ----

export async function createV5Project(name: string): Promise<{ project_id: string; status: string }> {
  const res = await api.post('/v5/projects', null, { params: { name } });
  return res.data;
}

export async function getV5Project(projectId: string): Promise<V5Project> {
  const res = await api.get<V5Project>(`/v5/projects/${projectId}`);
  return res.data;
}

export async function uploadSpec(
  projectId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<{ project_id: string; status: string; filename: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post(`/v5/projects/${projectId}/upload-spec`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
  return res.data;
}

export async function uploadLogo(projectId: string, file: File): Promise<{ logo_path: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post(`/v5/projects/${projectId}/upload-logo`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function uploadMusic(projectId: string, file: File): Promise<{ music_path: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post(`/v5/projects/${projectId}/upload-music`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function getV5Extraction(projectId: string): Promise<V5ExtractionResponse> {
  const res = await api.get<V5ExtractionResponse>(`/v5/projects/${projectId}/extraction`);
  return res.data;
}

export async function updateV5Room(
  projectId: string,
  roomId: string,
  data: { label?: string; products?: V5Room['products'] },
): Promise<void> {
  await api.put(`/v5/projects/${projectId}/rooms/${roomId}`, data);
}

export async function swapProduct(
  projectId: string,
  roomId: string,
  data: { old_product_id: string; new_product_image_path: string; new_product_name?: string },
): Promise<void> {
  await api.post(`/v5/projects/${projectId}/rooms/${roomId}/swap-product`, data);
}

export async function approveExtraction(projectId: string): Promise<{ status: string; rooms_count: number }> {
  const res = await api.post(`/v5/projects/${projectId}/approve-extraction`);
  return res.data;
}

export async function getRoomImages(
  projectId: string,
  roomId: string,
): Promise<{ room_id: string; images: V5GeneratedImage[] }> {
  const res = await api.get(`/v5/projects/${projectId}/rooms/${roomId}/images`);
  return res.data;
}

export async function regenerateRoom(projectId: string, roomId: string): Promise<void> {
  await api.post(`/v5/projects/${projectId}/rooms/${roomId}/regenerate`);
}

export interface RegionSelect {
  x: number;  // 0-1 relative
  y: number;
  width: number;
  height: number;
}

export async function submitRoomFeedback(
  projectId: string,
  roomId: string,
  data: { feedback: string; product_ids?: string[]; region?: RegionSelect | null },
): Promise<{ edited_image_id: string; edited_image_path: string; version: number }> {
  const res = await api.post(`/v5/projects/${projectId}/rooms/${roomId}/feedback`, data);
  return res.data;
}

export async function approveRoomImage(
  projectId: string,
  roomId: string,
): Promise<{ room_id: string; status: string; all_approved: boolean }> {
  const res = await api.post(`/v5/projects/${projectId}/rooms/${roomId}/approve`);
  return res.data;
}

export async function generateVideos(projectId: string, videoMode: 'standard' | 'premium' = 'standard'): Promise<{ status: string; rooms_count: number; video_mode: string }> {
  const res = await api.post(`/v5/projects/${projectId}/generate-videos`, { video_mode: videoMode });
  return res.data;
}

export async function compileFinalVideo(
  projectId: string,
  roomOrder?: string[],
): Promise<{ project_id: string; video_path: string; status: string }> {
  const res = await api.post(`/v5/projects/${projectId}/compile`, { room_order: roomOrder });
  return res.data;
}

export function getFinalVideoUrl(projectId: string): string {
  return `/api/v1/v5/projects/${projectId}/final-video`;
}

export function getLocalFileUrl(filePath: string): string {
  // In demo mode, paths are already web-relative (e.g. /demo/rooms/xxx.png)
  if (filePath.startsWith('/demo/') || filePath.startsWith('http')) return filePath;
  // Convert local file paths to API URL
  const base = (import.meta as any).env?.DEV ? '' : 'https://furnivision-api-production.up.railway.app';
  const storageMatch = filePath.split('/storage/').pop();
  if (storageMatch && storageMatch !== filePath) return `${base}/api/v1/local-storage/${storageMatch}`;
  const tmpMatch = filePath.match(/\/tmp\/furnivision\/(.+)/);
  if (tmpMatch) return `${base}/api/v1/local-storage/${tmpMatch[1]}`;
  return filePath;
}
