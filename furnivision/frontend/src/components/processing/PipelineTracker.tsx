import type { PipelineStage } from '@/lib/types';
import { cn } from '@/lib/utils';

interface PipelineTrackerProps {
  currentStage: PipelineStage;
  status: string;
}

const STAGES: { key: PipelineStage; label: string; icon: string }[] = [
  { key: 'parse', label: 'Parse', icon: '1' },
  { key: 'plan', label: 'Plan', icon: '2' },
  { key: 'generate', label: 'Generate', icon: '3' },
  { key: 'validate', label: 'Validate', icon: '4' },
  { key: 'animate', label: 'Animate', icon: '5' },
];

export default function PipelineTracker({ currentStage, status }: PipelineTrackerProps) {
  const currentIdx = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="w-full">
      <div className="flex items-center justify-between relative">
        {/* Connector line */}
        <div className="absolute top-5 left-0 right-0 h-0.5 bg-gray-700" />
        <div
          className="absolute top-5 left-0 h-0.5 bg-accent transition-all duration-500"
          style={{
            width: `${status === 'completed' ? 100 : (currentIdx / (STAGES.length - 1)) * 100}%`,
          }}
        />

        {STAGES.map((stage, idx) => {
          const isCompleted = status === 'completed' || idx < currentIdx;
          const isCurrent = idx === currentIdx && status !== 'completed';
          const isPending = idx > currentIdx && status !== 'completed';

          return (
            <div key={stage.key} className="relative z-10 flex flex-col items-center gap-2">
              <div
                className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300',
                  isCompleted && 'bg-accent text-white shadow-lg shadow-accent/30',
                  isCurrent && 'bg-accent text-white animate-pulse-glow',
                  isPending && 'bg-surface-800 text-gray-500 border border-gray-700',
                )}
              >
                {isCompleted ? (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  stage.icon
                )}
              </div>
              <span
                className={cn(
                  'text-xs font-medium',
                  isCompleted && 'text-accent-light',
                  isCurrent && 'text-white',
                  isPending && 'text-gray-500',
                )}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
