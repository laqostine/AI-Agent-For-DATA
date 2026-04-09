import { useState, useRef, useCallback } from 'react';
import type { RegionSelect } from '@/lib/api';
import { cn } from '@/lib/utils';

interface RegionSelectorProps {
  imageUrl: string;
  onRegionSelect: (region: RegionSelect | null) => void;
  selectedRegion: RegionSelect | null;
  className?: string;
}

/**
 * Overlay on an image that lets users draw a rectangle to select a region.
 * Returns normalized coordinates (0-1 relative to image dimensions).
 */
export default function RegionSelector({
  imageUrl,
  onRegionSelect,
  selectedRegion,
  className,
}: RegionSelectorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [currentPos, setCurrentPos] = useState<{ x: number; y: number } | null>(null);
  const [isSelectMode, setIsSelectMode] = useState(false);

  const getRelativePos = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    return {
      x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height)),
    };
  }, []);

  const handleStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (!isSelectMode) return;
    e.preventDefault();
    const pos = getRelativePos(e);
    setStartPos(pos);
    setCurrentPos(pos);
    setIsDrawing(true);
    onRegionSelect(null);
  }, [isSelectMode, getRelativePos, onRegionSelect]);

  const handleMove = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing || !startPos) return;
    e.preventDefault();
    setCurrentPos(getRelativePos(e));
  }, [isDrawing, startPos, getRelativePos]);

  const handleEnd = useCallback(() => {
    if (!isDrawing || !startPos || !currentPos) return;
    setIsDrawing(false);

    const x = Math.min(startPos.x, currentPos.x);
    const y = Math.min(startPos.y, currentPos.y);
    const width = Math.abs(currentPos.x - startPos.x);
    const height = Math.abs(currentPos.y - startPos.y);

    // Ignore tiny selections (accidental clicks)
    if (width < 0.03 || height < 0.03) {
      onRegionSelect(null);
      return;
    }

    onRegionSelect({ x, y, width, height });
  }, [isDrawing, startPos, currentPos, onRegionSelect]);

  // Calculate the drawn rect for display
  const drawRect = isDrawing && startPos && currentPos ? {
    left: `${Math.min(startPos.x, currentPos.x) * 100}%`,
    top: `${Math.min(startPos.y, currentPos.y) * 100}%`,
    width: `${Math.abs(currentPos.x - startPos.x) * 100}%`,
    height: `${Math.abs(currentPos.y - startPos.y) * 100}%`,
  } : selectedRegion ? {
    left: `${selectedRegion.x * 100}%`,
    top: `${selectedRegion.y * 100}%`,
    width: `${selectedRegion.width * 100}%`,
    height: `${selectedRegion.height * 100}%`,
  } : null;

  return (
    <div className={className}>
      {/* Toggle button */}
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => {
            setIsSelectMode(!isSelectMode);
            if (isSelectMode) { onRegionSelect(null); }
          }}
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all border',
            isSelectMode
              ? 'bg-accent/15 text-accent border-accent/30'
              : 'bg-surface-700/50 text-gray-400 border-gray-700/50 hover:text-gray-200 hover:border-gray-600'
          )}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
          {isSelectMode ? 'Draw region to edit' : 'Select region'}
        </button>
        {selectedRegion && (
          <button
            onClick={() => onRegionSelect(null)}
            className="text-[10px] text-gray-500 hover:text-red-400 transition-colors"
          >
            Clear selection
          </button>
        )}
      </div>

      {/* Image with overlay */}
      <div
        ref={containerRef}
        className={cn(
          'relative rounded-lg overflow-hidden border border-gray-700/30',
          isSelectMode && 'cursor-crosshair'
        )}
        onMouseDown={handleStart}
        onMouseMove={handleMove}
        onMouseUp={handleEnd}
        onMouseLeave={() => { if (isDrawing) handleEnd(); }}
        onTouchStart={handleStart}
        onTouchMove={handleMove}
        onTouchEnd={handleEnd}
      >
        <img src={imageUrl} alt="" className="w-full select-none pointer-events-none" draggable={false} />

        {/* Dimming overlay when region is selected */}
        {drawRect && (
          <div className="absolute inset-0 bg-black/40 pointer-events-none" />
        )}

        {/* Selected region highlight */}
        {drawRect && (
          <div
            className="absolute border-2 border-accent bg-accent/10 pointer-events-none"
            style={{
              left: drawRect.left,
              top: drawRect.top,
              width: drawRect.width,
              height: drawRect.height,
              boxShadow: '0 0 0 9999px rgba(0,0,0,0.4)',
            }}
          >
            {/* Corner handles */}
            <div className="absolute -top-1 -left-1 w-2 h-2 bg-accent rounded-full" />
            <div className="absolute -top-1 -right-1 w-2 h-2 bg-accent rounded-full" />
            <div className="absolute -bottom-1 -left-1 w-2 h-2 bg-accent rounded-full" />
            <div className="absolute -bottom-1 -right-1 w-2 h-2 bg-accent rounded-full" />
          </div>
        )}

        {/* Hint text */}
        {isSelectMode && !drawRect && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span className="text-xs text-white/60 bg-black/40 px-3 py-1.5 rounded-full backdrop-blur-sm">
              Click and drag to select a region
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
