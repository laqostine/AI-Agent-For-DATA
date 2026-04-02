import { useCallback, useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { ViewerManifest, FrameManifest } from '@/lib/types';

const textureLoader = new THREE.TextureLoader();

interface UseFrameSequenceOptions {
  manifest: ViewerManifest | null;
  preloadRadius?: number;
}

interface FrameSequenceState {
  currentIndex: number;
  currentTexture: THREE.Texture | null;
  nextTexture: THREE.Texture | null;
  isTransitioning: boolean;
  totalFrames: number;
  currentFrame: FrameManifest | null;
  isLoading: boolean;
  goToFrame: (index: number) => void;
  nextFrame: () => void;
  prevFrame: () => void;
}

export function useFrameSequence({
  manifest,
  preloadRadius = 4,
}: UseFrameSequenceOptions): FrameSequenceState {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentTexture, setCurrentTexture] = useState<THREE.Texture | null>(null);
  const [nextTexture, setNextTexture] = useState<THREE.Texture | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const textureCache = useRef<Map<number, THREE.Texture>>(new Map());
  const loadingSet = useRef<Set<number>>(new Set());

  const totalFrames = manifest?.total_frames ?? 0;
  const currentFrame = manifest?.frames[currentIndex] ?? null;

  const loadTexture = useCallback(
    async (index: number): Promise<THREE.Texture | null> => {
      if (!manifest) return null;
      const cached = textureCache.current.get(index);
      if (cached) return cached;
      if (loadingSet.current.has(index)) return null;

      const frame = manifest.frames[index];
      if (!frame) return null;

      loadingSet.current.add(index);
      try {
        const texture = await new Promise<THREE.Texture>((resolve, reject) => {
          textureLoader.load(frame.url, resolve, undefined, reject);
        });
        texture.colorSpace = THREE.SRGBColorSpace;
        textureCache.current.set(index, texture);
        return texture;
      } catch {
        return null;
      } finally {
        loadingSet.current.delete(index);
      }
    },
    [manifest],
  );

  const preloadAround = useCallback(
    (centerIndex: number) => {
      if (!manifest) return;
      for (let offset = -preloadRadius; offset <= preloadRadius; offset++) {
        const idx = centerIndex + offset;
        if (idx >= 0 && idx < totalFrames && !textureCache.current.has(idx)) {
          loadTexture(idx);
        }
      }
    },
    [manifest, totalFrames, preloadRadius, loadTexture],
  );

  const goToFrame = useCallback(
    async (index: number) => {
      if (!manifest || index < 0 || index >= totalFrames || index === currentIndex) return;

      setIsLoading(true);
      const tex = await loadTexture(index);
      if (tex) {
        setNextTexture(tex);
        setIsTransitioning(true);
        setTimeout(() => {
          setCurrentTexture(tex);
          setNextTexture(null);
          setIsTransitioning(false);
          setCurrentIndex(index);
        }, 150);
      }
      setIsLoading(false);
      preloadAround(index);
    },
    [manifest, totalFrames, currentIndex, loadTexture, preloadAround],
  );

  const nextFrame = useCallback(() => {
    goToFrame((currentIndex + 1) % totalFrames);
  }, [currentIndex, totalFrames, goToFrame]);

  const prevFrame = useCallback(() => {
    goToFrame((currentIndex - 1 + totalFrames) % totalFrames);
  }, [currentIndex, totalFrames, goToFrame]);

  // Load initial frame
  useEffect(() => {
    if (!manifest) return;
    setCurrentIndex(0);
    loadTexture(0).then((tex) => {
      if (tex) setCurrentTexture(tex);
      preloadAround(0);
    });

    return () => {
      textureCache.current.forEach((tex) => tex.dispose());
      textureCache.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manifest]);

  return {
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
  };
}
