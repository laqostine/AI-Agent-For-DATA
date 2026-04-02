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
    <div className={cn('card p-4', className)}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-300 truncate max-w-[200px]">{filename}</span>
        <span
          className={cn(
            'text-xs font-medium',
            status === 'complete' && 'text-success',
            status === 'error' && 'text-danger',
            status === 'uploading' && 'text-accent-light',
          )}
        >
          {status === 'complete' ? 'Done' : status === 'error' ? 'Failed' : `${progress}%`}
        </span>
      </div>
      <div className="w-full h-2 bg-surface-900 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-300',
            status === 'complete' && 'bg-success',
            status === 'error' && 'bg-danger',
            status === 'uploading' && 'bg-accent',
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
