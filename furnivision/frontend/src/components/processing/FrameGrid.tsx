import type { FrameStatus } from '@/lib/types';
import { cn } from '@/lib/utils';

interface FrameGridProps {
  frames: FrameStatus[];
}

export default function FrameGrid({ frames }: FrameGridProps) {
  // Pad to 32 if needed
  const paddedFrames: (FrameStatus | null)[] = [...frames];
  while (paddedFrames.length < 32) {
    paddedFrames.push(null);
  }

  return (
    <div className="grid grid-cols-8 gap-1">
      {paddedFrames.slice(0, 32).map((frame, i) => {
        const status = frame?.status ?? 'pending';
        const isKeyframe = frame?.is_keyframe ?? false;

        return (
          <div
            key={i}
            className={cn(
              'aspect-square rounded-sm transition-all duration-300 relative',
              status === 'pending' && 'bg-surface-900 border border-gray-800',
              status === 'generating' && 'bg-accent/30 border border-accent/50 animate-pulse',
              status === 'completed' && 'bg-success/80 border border-success',
              status === 'failed' && 'bg-danger/80 border border-danger',
            )}
            title={`Frame ${i}${isKeyframe ? ' (Keyframe)' : ''} - ${status}`}
          >
            {isKeyframe && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div
                  className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    status === 'completed' ? 'bg-white' : 'bg-gray-400',
                  )}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
