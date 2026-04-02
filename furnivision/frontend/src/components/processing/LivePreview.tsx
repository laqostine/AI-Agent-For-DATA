import { cn } from '@/lib/utils';

interface LivePreviewProps {
  previewUrl: string | null;
  roomName: string;
  className?: string;
}

export default function LivePreview({ previewUrl, roomName, className }: LivePreviewProps) {
  if (!previewUrl) return null;

  return (
    <div className={cn('card overflow-hidden animate-fade-in', className)}>
      <div className="relative">
        <img
          src={previewUrl}
          alt={`${roomName} preview`}
          className="w-full h-auto"
        />
        <div className="absolute top-3 left-3">
          <span className="badge bg-success/90 text-white backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-white mr-1.5 animate-pulse" />
            PREVIEW READY
          </span>
        </div>
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-4">
          <p className="text-sm font-semibold text-white">{roomName}</p>
          <p className="text-xs text-gray-300">First render complete</p>
        </div>
      </div>
    </div>
  );
}
