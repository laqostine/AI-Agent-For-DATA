import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import FileDropzone from '@/components/upload/FileDropzone';
import UploadProgress from '@/components/upload/UploadProgress';
import { createV5Project, uploadSpec, uploadLogo, uploadMusic } from '@/lib/api';
import { formatFileSize, cn } from '@/lib/utils';

const STEPS = [
  { num: 1, label: 'Upload', desc: 'Specification' },
  { num: 2, label: 'Review', desc: 'Extraction' },
  { num: 3, label: 'Render', desc: 'AI Images' },
  { num: 4, label: 'Video', desc: 'Walkthrough' },
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
      <header className="border-b border-white/[0.06] bg-surface-900/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <img src="/cadre-logo.png" alt="CADRE" className="w-9 h-9 rounded-xl object-contain" />
            <div>
              <h1 className="text-[15px] font-semibold text-white tracking-[0.2em] leading-tight uppercase">Cadre</h1>
              <p className="text-[10px] text-gray-500 tracking-widest uppercase">Interior Visualization</p>
            </div>
          </div>
          {/* Step indicator */}
          <div className="hidden md:flex items-center gap-0.5">
            {STEPS.map((s, i) => (
              <div key={s.num} className="flex items-center">
                <div className={cn(
                  'flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs transition-all',
                  s.num === 1
                    ? 'bg-accent/10 text-accent border border-accent/20'
                    : 'text-gray-600',
                )}>
                  <span className={cn(
                    'w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-semibold',
                    s.num === 1 ? 'bg-accent text-surface-950' : 'bg-white/[0.06] text-gray-500',
                  )}>{s.num}</span>
                  <span className="font-medium">{s.label}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className="w-8 flex items-center justify-center">
                    <div className="w-full h-px bg-white/[0.06]" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-2xl mx-auto px-6 py-16 w-full">
        {/* Demo banner in production */}
        {!(import.meta as any).env?.DEV && (
          <div className="mb-10 card-glass p-5 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-white">Experience Cadre</p>
              <p className="text-xs text-gray-500 mt-0.5">Interactive demo with AI-generated renders from a Forthing dealership</p>
            </div>
            <a href="/demo" className="btn-primary px-5 py-2.5 text-xs">
              View Demo
            </a>
          </div>
        )}

        {/* Hero */}
        <div className="text-center mb-14">
          <p className="text-label text-accent mb-4">Step 1 of 4</p>
          <h2 className="heading-display text-4xl md:text-5xl leading-[1.1]">
            Upload Your<br />Specification
          </h2>
          <p className="text-gray-500 mt-4 text-base max-w-md mx-auto leading-relaxed">
            Drop your PPTX furniture specification. AI will extract every room,
            product, and layout automatically.
          </p>
        </div>

        {/* Main dropzone card */}
        <div className="card p-8 mb-6">
          <FileDropzone
            accept={{
              'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
              'application/vnd.ms-powerpoint': ['.ppt'],
            }}
            label="PPTX Specification"
            sublabel="Drag & drop or click to browse"
            icon={
              <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/15 flex items-center justify-center">
                <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </div>
            }
            onDrop={handleSpecDrop}
            disabled={isUploading}
            className="h-44"
          />

          {/* File preview */}
          {specFile && (
            <div className="mt-4 flex items-center gap-3 p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/15 flex items-center justify-center flex-shrink-0">
                <span className="text-accent text-[9px] font-bold tracking-wider">PPTX</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 truncate font-medium">{specFile.name}</p>
                <p className="text-[11px] text-gray-600">{formatFileSize(specFile.size)}</p>
              </div>
              <button
                className="text-gray-600 hover:text-red-400 transition-colors p-2 rounded-lg hover:bg-red-500/10"
                onClick={() => setSpecFile(null)}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Optional section */}
        <div className="mb-10">
          <button
            className="flex items-center gap-2.5 text-gray-500 hover:text-gray-300 transition-colors group"
            onClick={() => setShowOptional(!showOptional)}
          >
            <svg className={cn('w-3 h-3 transition-transform duration-300', showOptional && 'rotate-90')}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            <span className="text-sm">Optional: Logo & background music</span>
          </button>
          {showOptional && (
            <div className="mt-4 grid grid-cols-2 gap-4 animate-slide-up">
              <div className="card p-5">
                <FileDropzone
                  accept={{ 'image/*': ['.png', '.jpg', '.jpeg', '.svg'] }}
                  label="Logo"
                  sublabel="Video end card"
                  icon={
                    <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.41a2.25 2.25 0 013.182 0l2.909 2.91m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                    </svg>
                  }
                  onDrop={(f) => setLogoFile(f[0] ?? null)}
                  disabled={isUploading}
                  className="h-24"
                />
                {logoFile && <p className="text-[11px] text-gray-600 mt-2 truncate">{logoFile.name}</p>}
              </div>
              <div className="card p-5">
                <FileDropzone
                  accept={{ 'audio/*': ['.mp3', '.wav', '.m4a'] }}
                  label="Music"
                  sublabel="Background audio"
                  icon={
                    <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
                    </svg>
                  }
                  onDrop={(f) => setMusicFile(f[0] ?? null)}
                  disabled={isUploading}
                  className="h-24"
                />
                {musicFile && <p className="text-[11px] text-gray-600 mt-2 truncate">{musicFile.name}</p>}
              </div>
            </div>
          )}
        </div>

        {/* Progress */}
        {isUploading && (
          <div className="card p-6 mb-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-5 h-5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
              <span className="text-sm font-medium text-accent">{uploadStep}</span>
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
          <div className="mb-6 p-4 rounded-xl bg-red-500/5 border border-red-500/15 text-red-400 text-sm flex items-center gap-3 animate-fade-in">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          className="w-full btn-primary text-base py-4 flex items-center justify-center gap-2.5"
          onClick={handleSubmit}
          disabled={isUploading || !specFile}
        >
          {isUploading ? (
            <>
              <div className="w-4 h-4 border-2 border-surface-950/30 border-t-surface-950 rounded-full animate-spin" />
              Processing...
            </>
          ) : (
            <>
              Extract & Review
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </>
          )}
        </button>

        {/* Forthing walkthrough video */}
        <div className="mt-16 card overflow-hidden">
          <div className="px-6 py-4 flex items-center justify-between border-b border-white/[0.04]">
            <div>
              <p className="text-label mb-0.5">AI-Generated Output</p>
              <p className="text-[11px] text-gray-600">Forthing dealership — 13 rooms from a single PPTX</p>
            </div>
            <a href="/demo" className="text-xs text-accent hover:text-accent-light transition-colors font-medium tracking-wide">
              Live demo
              <span className="ml-1 opacity-60">&rarr;</span>
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
              style={{ maxHeight: '420px' }}
            />
          </div>
        </div>

        {/* How it works */}
        <div className="mt-16 pt-10 border-t border-white/[0.04]">
          <p className="text-center text-label text-gray-600 mb-8">How it works</p>
          <div className="grid grid-cols-4 gap-6">
            {STEPS.map((s) => (
              <div key={s.num} className="text-center group">
                <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center mx-auto mb-3 group-hover:border-accent/20 group-hover:bg-accent/5 transition-all duration-300">
                  <span className="text-xs font-semibold text-gray-500 group-hover:text-accent transition-colors">{s.num}</span>
                </div>
                <p className="text-xs font-medium text-gray-300">{s.label}</p>
                <p className="text-[10px] text-gray-600 mt-0.5">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
