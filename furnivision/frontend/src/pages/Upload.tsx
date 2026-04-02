import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropzone from '@/components/upload/FileDropzone';
import UploadProgress from '@/components/upload/UploadProgress';
import { createProject, uploadFloorplan, uploadFurniture, startPipeline } from '@/lib/api';
import { useProjectStore } from '@/stores/projectStore';
import { usePipelineStore } from '@/stores/pipelineStore';
import { formatFileSize, cn } from '@/lib/utils';
import type { ProjectBrief } from '@/lib/types';

export default function Upload() {
  const navigate = useNavigate();
  const { brief, updateBrief } = useProjectStore();
  const setJobId = usePipelineStore((s) => s.setJobId);

  const [floorplanFile, setFloorplanFile] = useState<File | null>(null);
  const [furnitureFiles, setFurnitureFiles] = useState<File[]>([]);
  const [floorplanPreview, setFloorplanPreview] = useState<string | null>(null);
  const [furniturePreviews, setFurniturePreviews] = useState<string[]>([]);

  const [floorplanProgress, setFloorplanProgress] = useState(0);
  const [furnitureProgress, setFurnitureProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState<string | null>(null);
  const [showBrief, setShowBrief] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFloorplanDrop = useCallback((files: File[]) => {
    const file = files[0];
    if (!file) return;
    setFloorplanFile(file);
    // Generate preview for PDFs or images
    if (file.type.startsWith('image/')) {
      setFloorplanPreview(URL.createObjectURL(file));
    } else {
      setFloorplanPreview(null);
    }
  }, []);

  const handleFurnitureDrop = useCallback((files: File[]) => {
    setFurnitureFiles((prev) => [...prev, ...files]);
    const newPreviews = files.map((f) => URL.createObjectURL(f));
    setFurniturePreviews((prev) => [...prev, ...newPreviews]);
  }, []);

  const removeFurnitureFile = (index: number) => {
    setFurnitureFiles((prev) => prev.filter((_, i) => i !== index));
    setFurniturePreviews((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (!floorplanFile) {
      setError('Please upload a floor plan');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      // Step 1: Create project
      setUploadStep('Creating project...');
      const { project_id } = await createProject({
        name: `Project ${new Date().toLocaleDateString()}`,
        brief,
      });

      // Step 2: Upload floorplan
      setUploadStep('Uploading floor plan...');
      await uploadFloorplan(project_id, floorplanFile, setFloorplanProgress);

      // Step 3: Upload furniture
      if (furnitureFiles.length > 0) {
        setUploadStep('Uploading furniture images...');
        await uploadFurniture(project_id, furnitureFiles, setFurnitureProgress);
      }

      // Step 4: Start extraction pipeline
      setUploadStep('Starting analysis...');
      const { job_id } = await startPipeline({
        project_id,
        mode: 'all',
      });
      setJobId(job_id, project_id);

      navigate(`/confirm/${project_id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
    } finally {
      setIsUploading(false);
      setUploadStep(null);
    }
  };

  const handleBriefChange = (field: keyof ProjectBrief, value: string | number) => {
    updateBrief({ [field]: value });
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-surface-800/50 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-100 tracking-tight">FurniVision AI</h1>
            <p className="text-sm text-gray-500 mt-0.5">Interior visualisation powered by AI</p>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-6xl mx-auto px-6 py-10 w-full">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-100 mb-2">Upload Your Files</h2>
          <p className="text-gray-400">
            Start by uploading your floor plan and furniture images. We will analyse them and create stunning visualisations.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Floor Plan Dropzone */}
          <div>
            <FileDropzone
              accept={{ 'application/pdf': ['.pdf'], 'image/*': ['.png', '.jpg', '.jpeg'] }}
              label="Floor Plan PDF or Image"
              sublabel="Drop your floor plan here, or click to browse"
              icon={
                <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              }
              onDrop={handleFloorplanDrop}
              disabled={isUploading}
              className="h-64"
            />
            {floorplanFile && (
              <div className="mt-3 card p-3 flex items-center gap-3">
                {floorplanPreview && (
                  <img src={floorplanPreview} alt="Preview" className="w-16 h-16 rounded-lg object-cover" />
                )}
                {!floorplanPreview && (
                  <div className="w-16 h-16 rounded-lg bg-surface-900 flex items-center justify-center">
                    <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{floorplanFile.name}</p>
                  <p className="text-xs text-gray-500">{formatFileSize(floorplanFile.size)}</p>
                </div>
                <button
                  className="text-gray-500 hover:text-danger transition-colors p-1"
                  onClick={() => {
                    setFloorplanFile(null);
                    setFloorplanPreview(null);
                  }}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}
          </div>

          {/* Furniture Dropzone */}
          <div>
            <FileDropzone
              accept={{ 'image/*': ['.png', '.jpg', '.jpeg', '.webp'] }}
              multiple
              label="Furniture Images"
              sublabel="Drop furniture photos here, or click to browse"
              icon={
                <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                </svg>
              }
              onDrop={handleFurnitureDrop}
              disabled={isUploading}
              className="h-64"
            />
            {furniturePreviews.length > 0 && (
              <div className="mt-3 grid grid-cols-4 gap-2">
                {furniturePreviews.map((preview, idx) => (
                  <div key={idx} className="relative group">
                    <img
                      src={preview}
                      alt={furnitureFiles[idx]?.name}
                      className="w-full aspect-square rounded-lg object-cover border border-gray-700/50"
                    />
                    <button
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/70 text-gray-300 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                      onClick={() => removeFurnitureFile(idx)}
                    >
                      x
                    </button>
                    <p className="text-[10px] text-gray-500 truncate mt-1">
                      {furnitureFiles[idx]?.name}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Upload progress */}
        {isUploading && (
          <div className="space-y-3 mb-8 animate-fade-in">
            <p className="text-sm text-accent-light font-medium">{uploadStep}</p>
            {floorplanProgress > 0 && (
              <UploadProgress
                filename={floorplanFile?.name ?? 'Floor plan'}
                progress={floorplanProgress}
                status={floorplanProgress >= 100 ? 'complete' : 'uploading'}
              />
            )}
            {furnitureProgress > 0 && (
              <UploadProgress
                filename={`${furnitureFiles.length} furniture images`}
                progress={furnitureProgress}
                status={furnitureProgress >= 100 ? 'complete' : 'uploading'}
              />
            )}
          </div>
        )}

        {/* Design Brief (expandable) */}
        <div className="mb-8">
          <button
            className="flex items-center gap-2 text-gray-300 hover:text-gray-100 transition-colors mb-4"
            onClick={() => setShowBrief(!showBrief)}
          >
            <svg
              className={cn('w-4 h-4 transition-transform', showBrief && 'rotate-90')}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            <span className="text-lg font-semibold">Design Brief</span>
            <span className="text-sm text-gray-500 font-normal">(optional -- defaults provided)</span>
          </button>

          {showBrief && (
            <div className="card p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-slide-up">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Ceiling Height (m)</label>
                <input
                  type="number"
                  className="input-field"
                  value={brief.ceiling_height}
                  onChange={(e) => handleBriefChange('ceiling_height', parseFloat(e.target.value) || 2.7)}
                  step="0.1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Floor Material</label>
                <select
                  className="input-field"
                  value={brief.floor_material}
                  onChange={(e) => handleBriefChange('floor_material', e.target.value)}
                >
                  <option value="hardwood">Hardwood</option>
                  <option value="tile">Tile</option>
                  <option value="carpet">Carpet</option>
                  <option value="marble">Marble</option>
                  <option value="concrete">Concrete</option>
                  <option value="laminate">Laminate</option>
                  <option value="vinyl">Vinyl</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Wall Color</label>
                <input
                  type="text"
                  className="input-field"
                  value={brief.wall_color}
                  onChange={(e) => handleBriefChange('wall_color', e.target.value)}
                  placeholder="e.g. white, cream, light grey"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Style</label>
                <select
                  className="input-field"
                  value={brief.style}
                  onChange={(e) => handleBriefChange('style', e.target.value)}
                >
                  <option value="modern">Modern</option>
                  <option value="contemporary">Contemporary</option>
                  <option value="minimalist">Minimalist</option>
                  <option value="scandinavian">Scandinavian</option>
                  <option value="industrial">Industrial</option>
                  <option value="traditional">Traditional</option>
                  <option value="mid-century">Mid-Century Modern</option>
                  <option value="bohemian">Bohemian</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Lighting</label>
                <select
                  className="input-field"
                  value={brief.lighting}
                  onChange={(e) => handleBriefChange('lighting', e.target.value)}
                >
                  <option value="natural">Natural</option>
                  <option value="warm">Warm</option>
                  <option value="cool">Cool</option>
                  <option value="ambient">Ambient</option>
                  <option value="dramatic">Dramatic</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Room Dimensions (W x L m)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    className="input-field"
                    placeholder="Width"
                    value={brief.dimensions?.width ?? ''}
                    onChange={(e) =>
                      updateBrief({
                        dimensions: {
                          width: parseFloat(e.target.value) || 0,
                          length: brief.dimensions?.length ?? 0,
                        },
                      })
                    }
                    step="0.1"
                  />
                  <input
                    type="number"
                    className="input-field"
                    placeholder="Length"
                    value={brief.dimensions?.length ?? ''}
                    onChange={(e) =>
                      updateBrief({
                        dimensions: {
                          width: brief.dimensions?.width ?? 0,
                          length: parseFloat(e.target.value) || 0,
                        },
                      })
                    }
                    step="0.1"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm animate-fade-in">
            {error}
          </div>
        )}

        {/* Submit */}
        <div className="flex justify-end">
          <button
            className="btn-primary text-lg px-8 py-4"
            onClick={handleSubmit}
            disabled={isUploading || !floorplanFile}
          >
            {isUploading ? (
              <span className="flex items-center gap-2">
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Processing...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Analyse Floor Plan
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </span>
            )}
          </button>
        </div>
      </main>
    </div>
  );
}
