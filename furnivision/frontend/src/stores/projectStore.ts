import { create } from 'zustand';
import type { Project, Room, FurnitureItem, ProjectBrief, ExtractionResult, FurnitureAssignment, MissingField } from '@/lib/types';

interface ProjectStore {
  currentProject: Project | null;
  rooms: Room[];
  furniture: FurnitureItem[];
  brief: ProjectBrief;
  extraction: ExtractionResult | null;
  assignments: FurnitureAssignment[];
  missingFields: MissingField[];
  missingFieldValues: Record<string, string | number>;

  setProject: (project: Project) => void;
  setRooms: (rooms: Room[]) => void;
  updateRoom: (roomId: string, updates: Partial<Room>) => void;
  setFurniture: (furniture: FurnitureItem[]) => void;
  setBrief: (brief: ProjectBrief) => void;
  updateBrief: (updates: Partial<ProjectBrief>) => void;
  setExtraction: (extraction: ExtractionResult) => void;
  setAssignments: (assignments: FurnitureAssignment[]) => void;
  setMissingFields: (fields: MissingField[]) => void;
  setMissingFieldValue: (field: string, value: string | number) => void;
  reset: () => void;
}

const defaultBrief: ProjectBrief = {
  ceiling_height: 2.7,
  floor_material: 'hardwood',
  wall_color: 'white',
  style: 'modern',
  lighting: 'natural',
};

export const useProjectStore = create<ProjectStore>((set) => ({
  currentProject: null,
  rooms: [],
  furniture: [],
  brief: defaultBrief,
  extraction: null,
  assignments: [],
  missingFields: [],
  missingFieldValues: {},

  setProject: (project) =>
    set({
      currentProject: project,
      rooms: project.rooms,
      furniture: project.furniture,
      brief: project.brief,
    }),

  setRooms: (rooms) => set({ rooms }),

  updateRoom: (roomId, updates) =>
    set((state) => ({
      rooms: state.rooms.map((r) =>
        r.id === roomId ? { ...r, ...updates } : r,
      ),
    })),

  setFurniture: (furniture) => set({ furniture }),

  setBrief: (brief) => set({ brief }),

  updateBrief: (updates) =>
    set((state) => ({
      brief: { ...state.brief, ...updates },
    })),

  setExtraction: (extraction) =>
    set({
      extraction,
      rooms: extraction.rooms,
      furniture: extraction.furniture,
      assignments: extraction.assignments,
      missingFields: extraction.missing_fields,
    }),

  setAssignments: (assignments) => set({ assignments }),

  setMissingFields: (fields) => set({ missingFields: fields }),

  setMissingFieldValue: (field, value) =>
    set((state) => ({
      missingFieldValues: { ...state.missingFieldValues, [field]: value },
    })),

  reset: () =>
    set({
      currentProject: null,
      rooms: [],
      furniture: [],
      brief: defaultBrief,
      extraction: null,
      assignments: [],
      missingFields: [],
      missingFieldValues: {},
    }),
}));
