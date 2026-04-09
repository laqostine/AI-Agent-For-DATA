import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropzone from '@/components/upload/FileDropzone';
import UploadProgress from '@/components/upload/UploadProgress';
import { createV5Project, uploadSpec, uploadLogo, uploadMusic } from '@/lib/api';
import { formatFileSize, cn } from '@/lib/utils';

const STEPS = [
  { num: 1, label: 'Upload', icon: '📄' },
  { num: 2, label: 'Review', icon: '🔍' },
  { num: 3, label: 'Render', icon: '🎨' },
  { num: 4, label: 'Video', icon: '🎬' },
];

export default function Upload() {
  const navigate = useNavigate();
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [musicFile, setMusicFile] = useState<File | null>(null);
  const [specProgress, setSpecProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showOptional, setShowOptional] = useState(false);

  const handleSpecDrop = useCallback((files: File[]) => {
    const file = files[0];
    if (!file) return;
    setSpecFile(file);
    setError(null);
  }, []);

  const handleSubmit = async () => {
    if (!specFile) { setError('Please upload a PPTX specification file'); return; }
    setIsUploading(true);
    setError(null);
    try {
      setUploadStep('Creating project...');
      const { project_id } = await createV5Project(`Project ${new Date().toLocaleDateString('en-GB')}`);
      setUploadStep('Uploading specification...');
      await uploadSpec(project_id, specFile, setSpecProgress);
      if (logoFile) { setUploadStep('Uploading logo...'); await uploadLogo(project_id, logoFile); }
      if (musicFile) { setUploadStep('Uploading music...'); await uploadMusic(project_id, musicFile); }
      navigate(`/extraction-review/${project_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
      setUploadStep(null);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800/50 bg-surface-800/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">FV</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-100 tracking-tight leading-tight">FurniVision AI</h1>
              <p className="text-[11px] text-gray-500 -mt-0.5">Showroom Visualisation</p>
            </div>
          </div>
          {/* Step indicator */}
          <div className="hidden md:flex items-center gap-1">
            {STEPS.map((s, i) => (
              <div key={s.num} className="flex items-center">
                <div className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                  s.num === 1 ? 'bg-accent/20 text-accent border border-accent/30' : 'text-gray-500',
                )}>
                  <span>{s.icon}</span>
                  <span>{s.label}</span>
                </div>
                {i < STEPS.length - 1 && <div className="w-6 h-px bg-gray-700 mx-1" />}
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-3xl mx-auto px-6 py-12 w-full">
        {/* Demo banner in production (no backend) */}
        {!(import.meta as any).env?.DEV && (
          <div className="mb-8 card p-5 flex items-center justify-between bg-accent/5 border-accent/20">
            <div>
              <p className="text-sm font-medium text-white">See FurniVision in action</p>
              <p className="text-xs text-gray-400 mt-0.5">Interactive demo with real AI-generated renders from a Forthing dealership spec</p>
            </div>
            <a href="/demo" className="btn-primary px-5 py-2.5 text-sm flex-shrink-0">
              Open Demo
            </a>
          </div>
        )}

        {/* Hero */}
        <div className="text-center mb-10">
          <h2 className="text-4xl font-extrabold text-gray-100 tracking-tight">
            Upload Your Spec
          </h2>
          <p className="text-gray-400 mt-3 text-lg max-w-xl mx-auto">
            Drop your PPTX furniture specification and let AI extract every room, product, and layout automatically.
          </p>
        </div>

        {/* Main dropzone card */}
        <div className="card p-8 mb-6">
          <FileDropzone
            accept={{
              'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
              'application/vnd.ms-powerpoint': ['.ppt'],
            }}
            label="PPTX Specification File"
            sublabel="Drag & drop or click to browse"
            icon={
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500/20 to-red-500/20 border border-orange-500/20 flex items-center justify-center mb-1">
                <svg className="w-8 h-8 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
                </svg>
              </div>
            }
            onDrop={handleSpecDrop}
            disabled={isUploading}
            className="h-48"
          />

          {/* File preview */}
          {specFile && (
            <div className="mt-4 flex items-center gap-3 p-3 rounded-lg bg-surface-900/50 border border-gray-700/30">
              <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center flex-shrink-0">
                <span className="text-orange-400 text-[10px] font-bold">PPTX</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 truncate font-medium">{specFile.name}</p>
                <p className="text-xs text-gray-500">{formatFileSize(specFile.size)}</p>
              </div>
              <button
                className="text-gray-500 hover:text-red-400 transition-colors p-1.5 rounded-lg hover:bg-red-500/10"
                onClick={() => setSpecFile(null)}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Optional section */}
        <div className="mb-8">
          <button
            className="flex items-center gap-2 text-gray-400 hover:text-gray-200 transition-colors group"
            onClick={() => setShowOptional(!showOptional)}
          >
            <svg className={cn('w-3.5 h-3.5 transition-transform', showOptional && 'rotate-90')}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            <span className="text-sm">Optional: Logo & Music for final video</span>
          </button>
          {showOptional && (
            <div className="mt-3 grid grid-cols-2 gap-3 animate-slide-up">
              <div className="card p-4">
                <FileDropzone
                  accept={{ 'image/*': ['.png', '.jpg', '.jpeg', '.svg'] }}
                  label="Logo"
                  sublabel="Video end card"
                  icon={<span className="text-2xl">🏢</span>}
                  onDrop={(f) => setLogoFile(f[0] ?? null)}
                  disabled={isUploading}
                  className="h-24"
                />
                {logoFile && <p className="text-[11px] text-gray-500 mt-2 truncate">{logoFile.name}</p>}
              </div>
              <div className="card p-4">
                <FileDropzone
                  accept={{ 'audio/*': ['.mp3', '.wav', '.m4a'] }}
                  label="Music"
                  sublabel="Background audio"
                  icon={<span className="text-2xl">🎵</span>}
                  onDrop={(f) => setMusicFile(f[0] ?? null)}
                  disabled={isUploading}
                  className="h-24"
                />
                {musicFile && <p className="text-[11px] text-gray-500 mt-2 truncate">{musicFile.name}</p>}
              </div>
            </div>
          )}
        </div>

        {/* Progress */}
        {isUploading && (
          <div className="card p-5 mb-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-5 h-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
              <span className="text-sm font-medium text-accent-light">{uploadStep}</span>
            </div>
            {specProgress > 0 && (
              <UploadProgress
                filename={specFile?.name ?? 'Specification'}
                progress={specProgress}
                status={specProgress >= 100 ? 'complete' : 'uploading'}
              />
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/5 border border-red-500/20 text-red-400 text-sm flex items-center gap-3 animate-fade-in">
            <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          className="w-full btn-primary text-lg py-4 flex items-center justify-center gap-2"
          onClick={handleSubmit}
          disabled={isUploading || !specFile}
        >
          {isUploading ? (
            <>
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Processing...
            </>
          ) : (
            <>
              Extract & Review
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </>
          )}
        </button>

        {/* Forthing walkthrough video */}
        <div className="mt-12 card overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800/30 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-widest text-gray-500">AI-Generated Output</p>
              <p className="text-[11px] text-gray-600 mt-0.5">Forthing dealership showroom — 13 rooms rendered from a single PPTX spec</p>
            </div>
            <a href="/demo" className="text-xs text-accent hover:text-accent-light transition-colors font-medium">
              Try live demo →
            </a>
          </div>
          <div className="bg-black">
            <video
              src="/demo/forthing_walkthrough.mp4"
              controls
              muted
              autoPlay
              loop
              playsInline
              className="w-full"
              style={{ maxHeight: '450px' }}
            />
          </div>
        </div>

        {/* How it works */}
        <div className="mt-10 pt-8 border-t border-gray-800/50">
          <p className="text-center text-xs text-gray-600 uppercase tracking-widest mb-6">How it works</p>
          <div className="grid grid-cols-4 gap-4">
            {STEPS.map((s) => (
              <div key={s.num} className="text-center group">
                <div className="text-2xl mb-2">{s.icon}</div>
                <p className="text-xs font-medium text-gray-300">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
