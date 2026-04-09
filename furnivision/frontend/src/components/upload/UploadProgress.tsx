import { cn } from '@/lib/utils';

interface UploadProgressProps {
  filename: string;
  progress: number;
  status?: 'uploading' | 'complete' | 'error';
  className?: string;
}

export default function UploadProgress({
  filename,
  progress,
  status = 'uploading',
  className,
}: UploadProgressProps) {
  return (
    <div className={cn('p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]', className)}>
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-sm text-gray-400 truncate max-w-[200px]">{filename}</span>
        <span
          className={cn(
            'text-xs font-medium tabular-nums',
            status === 'complete' && 'text-emerald-400',
            status === 'error' && 'text-red-400',
            status === 'uploading' && 'text-accent',
          )}
        >
          {status === 'complete' ? 'Complete' : status === 'error' ? 'Failed' : `${progress}%`}
        </span>
      </div>
      <div className="w-full h-1 bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            status === 'complete' && 'bg-emerald-500',
            status === 'error' && 'bg-red-500',
            status === 'uploading' && 'bg-accent',
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
