// ---- Core Domain Models ----

export interface FurnitureItem {
  id: string;
  name: string;
  category: string;
  style?: string;
  color?: string;
  material?: string;
  dimensions?: { width: number; height: number; depth: number };
  image_url?: string;
  thumbnail_url?: string;
}

export interface RoomGeometry {
  vertices: [number, number][];
  area: number;
  centroid: [number, number];
  bounding_box: { x: number; y: number; width: number; height: number };
}

export interface ProjectBrief {
  ceiling_height: number;
  floor_material: string;
  wall_color: string;
  style: string;
  lighting: string;
  dimensions?: { width: number; length: number };
  notes?: string;
}

export interface Room {
  id: string;
  name: string;
  room_type: string;
  area: number;
  geometry?: RoomGeometry;
  furniture_ids: string[];
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'approved' | 'rejected';
  qc_score?: number;
  hero_renders?: string[];
  video_url?: string;
  viewer_manifest_url?: string;
}

export interface Project {
  id: string;
  name: string;
  status: 'created' | 'uploading' | 'extracting' | 'confirmed' | 'processing' | 'reviewing' | 'completed';
  brief: ProjectBrief;
  rooms: Room[];
  furniture?: FurnitureItem[];
  floorplan_url?: string;
  created_at: string;
  updated_at: string;
}

// ---- Pipeline State ----

export type PipelineStage = 'parse' | 'plan' | 'generate' | 'validate' | 'animate';

export interface FrameStatus {
  frame_index: number;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  image_url?: string;
  is_keyframe: boolean;
}

export interface RoomPipelineState {
  room_id: string;
  room_name: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  current_stage: PipelineStage;
  frames: FrameStatus[];
  progress: number;
  preview_url?: string;
  error?: string;
}

export interface PipelineState {
  job_id: string;
  project_id: string;
  stage: PipelineStage;
  status: 'running' | 'completed' | 'failed' | 'paused';
  rooms: RoomPipelineState[];
  progress: number;
  started_at: string;
  estimated_completion?: string;
}

// ---- Extraction Models ----

export interface MissingField {
  field_name: string;
  label: string;
  field_type: 'text' | 'number' | 'select';
  options?: string[];
  default_value?: string | number;
  agent_guess?: string | number;
  required: boolean;
}

export interface FurnitureAssignment {
  furniture_id: string;
  furniture_name: string;
  room_id: string;
  room_name: string;
  confidence: number;
}

export interface ExtractionResult {
  project_id: string;
  rooms: Room[];
  furniture: FurnitureItem[];
  assignments: FurnitureAssignment[];
  missing_fields: MissingField[];
  floorplan_image_url: string;
  confidence: number;
}

// ---- Viewer Manifest ----

export interface FrameManifest {
  index: number;
  url: string;
  type: 'keyframe' | 'interpolated';
  camera_description: string;
  camera_position?: [number, number, number];
  camera_target?: [number, number, number];
}

export interface ViewerManifest {
  room_id: string;
  room_name: string;
  total_frames: number;
  fps: number;
  frames: FrameManifest[];
}

// ---- V5 Human-in-the-Loop Models ----

export interface V5Product {
  id: string;
  name: string;
  dimensions: string;
  image_path: string;
  room_id: string;
  slide_index?: number;
  notes?: string;
}

export interface V5GeneratedImage {
  id: string;
  room_id: string;
  image_path: string;
  prompt_used: string;
  version: number;
  type: 'base' | 'refined' | 'edited';
  created_at?: string;
}

export interface V5FloorPlan {
  id: string;
  floor_name: string;
  image_path: string;
}

export type V5RoomStatus = 'pending' | 'extracted' | 'approved' | 'generating' | 'image_ready'
  | 'image_approved' | 'video_ready' | 'complete' | 'generation_failed' | 'video_failed';

export type V5ProjectStatus = 'uploading' | 'extracting' | 'reviewing_extraction'
  | 'generating_images' | 'reviewing_images' | 'generating_videos' | 'complete' | 'failed';

export interface V5Room {
  id: string;
  label: string;
  floor: string;
  status: V5RoomStatus;
  layout_image_path: string;
  products: V5Product[];
  generated_images: V5GeneratedImage[];
  video_path: string | null;
  feedback: string[];
}

export interface V5Project {
  id: string;
  name: string;
  status: V5ProjectStatus;
  spec_file_path: string;
  floor_plans: V5FloorPlan[];
  v5_rooms: V5Room[];
  logo_path: string | null;
  music_path: string | null;
  final_video_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface V5ExtractionResponse {
  project_id: string;
  status: string;
  rooms: V5Room[];
  floor_plans: V5FloorPlan[];
  total_products: number;
}

// ---- API Response Types ----

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface CreateProjectRequest {
  name: string;
  brief: ProjectBrief;
}

export interface CreateProjectResponse {
  project_id: string;
  upload_urls: {
    floorplan: string;
    furniture: string;
  };
}

export interface StartPipelineRequest {
  project_id: string;
  room_ids?: string[];
  mode: 'single_room' | 'all_rooms';
  target_room_id?: string;
}

export interface StartPipelineResponse {
  job_id: string;
  project_id: string;
  mode: string;
  message: string;
}

export interface ConfirmExtractionRequest {
  project_id: string;
  rooms: Room[];
  assignments: FurnitureAssignment[];
  brief_updates: Partial<ProjectBrief>;
  missing_field_values: Record<string, string | number>;
}

export interface RoomApprovalRequest {
  room_id: string;
  approved: boolean;
  feedback?: string;
  issues?: string[];
}

export interface OutputsResponse {
  project_id: string;
  rooms: Array<{
    room_id: string;
    room_name: string;
    hero_renders: string[];
    video_url: string;
    viewer_manifest_url: string;
    qc_score: number;
  }>;
  zip_url: string;
  share_url: string;
}
