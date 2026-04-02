import { useRef, useEffect, useCallback, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useFrameSequence } from '@/hooks/useFrameSequence';
import type { ViewerManifest } from '@/lib/types';
import { cn } from '@/lib/utils';

/* ── Inner Three.js scene ────────────────────────────────────────── */

interface FramePlaneProps {
  texture: THREE.Texture | null;
  opacity: number;
  position: [number, number, number];
}

function FramePlane({ texture, opacity, position }: FramePlaneProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame(() => {
    if (materialRef.current) {
      materialRef.current.opacity += (opacity - materialRef.current.opacity) * 0.15;
    }
  });

  if (!texture) return null;

  return (
    <mesh ref={meshRef} position={position}>
      <planeGeometry args={[16, 9]} />
      <meshBasicMaterial
        ref={materialRef}
        map={texture}
        transparent
        opacity={opacity}
        toneMapped={false}
      />
    </mesh>
  );
}

interface SceneProps {
  currentTexture: THREE.Texture | null;
  nextTexture: THREE.Texture | null;
  isTransitioning: boolean;
}

function Scene({ currentTexture, nextTexture, isTransitioning }: SceneProps) {
  return (
    <>
      <FramePlane texture={currentTexture} opacity={isTransitioning ? 0 : 1} position={[0, 0, 0]} />
      <FramePlane texture={nextTexture} opacity={isTransitioning ? 1 : 0} position={[0, 0, 0.01]} />
    </>
  );
}

/* ── Main FrameNavigator component ───────────────────────────────── */

interface FrameNavigatorProps {
  manifest: ViewerManifest | null;
  className?: string;
}

export default function FrameNavigator({ manifest, className }: FrameNavigatorProps) {
  const {
    currentIndex,
    currentTexture,
    nextTexture,
    isTransitioning,
    totalFrames,
    currentFrame,
    isLoading,
    goToFrame,
    nextFrame,
    prevFrame,
  } = useFrameSequence({ manifest, preloadRadius: 4 });

  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartFrame = useRef(0);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        nextFrame();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        prevFrame();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextFrame, prevFrame]);

  // Mouse drag
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      setIsDragging(true);
      dragStartX.current = e.clientX;
      dragStartFrame.current = currentIndex;
    },
    [currentIndex],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging || totalFrames === 0) return;
      const dx = e.clientX - dragStartX.current;
      const containerWidth = containerRef.current?.clientWidth ?? 800;
      const frameDelta = Math.round((dx / containerWidth) * totalFrames * 0.5);
      const newFrame = ((dragStartFrame.current + frameDelta) % totalFrames + totalFrames) % totalFrames;
      goToFrame(newFrame);
    },
    [isDragging, totalFrames, goToFrame],
  );

  const handleMouseUp = useCallback(() => setIsDragging(false), []);

  // Touch swipe
  const touchStartX = useRef(0);
  const touchStartFrame = useRef(0);

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      touchStartX.current = e.touches[0].clientX;
      touchStartFrame.current = currentIndex;
    },
    [currentIndex],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (totalFrames === 0) return;
      const dx = e.touches[0].clientX - touchStartX.current;
      const containerWidth = containerRef.current?.clientWidth ?? 800;
      const frameDelta = Math.round((dx / containerWidth) * totalFrames * 0.5);
      const newFrame = ((touchStartFrame.current + frameDelta) % totalFrames + totalFrames) % totalFrames;
      goToFrame(newFrame);
    },
    [totalFrames, goToFrame],
  );

  if (!manifest) {
    return (
      <div className={cn('flex items-center justify-center bg-surface-900 rounded-xl h-96', className)}>
        <p className="text-gray-500">No viewer data available</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn('relative select-none rounded-xl overflow-hidden bg-black', className)}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
    >
      {/* Three.js canvas */}
      <Canvas
        orthographic
        camera={{ zoom: 50, position: [0, 0, 10] }}
        style={{ width: '100%', height: '100%', minHeight: 400 }}
        gl={{ antialias: false, toneMapping: THREE.NoToneMapping }}
      >
        <Scene
          currentTexture={currentTexture}
          nextTexture={nextTexture}
          isTransitioning={isTransitioning}
        />
      </Canvas>

      {/* Navigation arrows */}
      <button
        className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors"
        onClick={(e) => {
          e.stopPropagation();
          prevFrame();
        }}
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <button
        className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors"
        onClick={(e) => {
          e.stopPropagation();
          nextFrame();
        }}
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {/* Loading indicator */}
      {isLoading && (
        <div className="absolute top-3 right-3">
          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        </div>
      )}

      {/* Bottom HUD */}
      <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm font-mono text-white/90">
              {currentIndex + 1} / {totalFrames}
            </span>
            {currentFrame && (
              <span
                className={cn(
                  'badge text-[10px]',
                  currentFrame.type === 'keyframe'
                    ? 'bg-accent/30 text-accent-light'
                    : 'bg-gray-700 text-gray-400',
                )}
              >
                {currentFrame.type === 'keyframe' ? 'KEY' : 'INTERP'}
              </span>
            )}
          </div>
          {currentFrame?.camera_description && (
            <p className="text-xs text-gray-400 truncate max-w-[300px]">
              {currentFrame.camera_description}
            </p>
          )}
        </div>

        {/* Frame scrubber */}
        <div className="mt-2 flex gap-px">
          {Array.from({ length: totalFrames }, (_, i) => (
            <button
              key={i}
              className={cn(
                'flex-1 h-1 rounded-full transition-all',
                i === currentIndex ? 'bg-accent' : 'bg-white/20 hover:bg-white/40',
              )}
              onClick={(e) => {
                e.stopPropagation();
                goToFrame(i);
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
