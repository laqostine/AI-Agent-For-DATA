import { useState } from 'react';

interface RegeneratePanelProps {
  roomId: string;
  roomName: string;
  onRegenerate: (roomId: string, options: RegenerateOptions) => void;
}

export interface RegenerateOptions {
  adjustPrompt: string;
  regenerateVideo: boolean;
  regenerateFrames: boolean;
}

export default function RegeneratePanel({
  roomId,
  roomName,
  onRegenerate,
}: RegeneratePanelProps) {
  const [adjustPrompt, setAdjustPrompt] = useState('');
  const [regenerateVideo, setRegenerateVideo] = useState(true);
  const [regenerateFrames, setRegenerateFrames] = useState(true);

  const handleRegenerate = () => {
    onRegenerate(roomId, {
      adjustPrompt,
      regenerateVideo,
      regenerateFrames,
    });
  };

  return (
    <div className="card p-5 space-y-4">
      <h3 className="text-base font-semibold text-gray-100">
        Regenerate: {roomName}
      </h3>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1.5">
          Adjustment Instructions
        </label>
        <textarea
          className="input-field min-h-[60px] resize-y"
          value={adjustPrompt}
          onChange={(e) => setAdjustPrompt(e.target.value)}
          placeholder="e.g. Move the sofa to face the window, change the rug color to grey..."
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={regenerateFrames}
            onChange={(e) => setRegenerateFrames(e.target.checked)}
            className="w-4 h-4 rounded border-gray-600 bg-surface-900 text-accent focus:ring-accent/50"
          />
          <span className="text-sm text-gray-300">Regenerate all frames</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={regenerateVideo}
            onChange={(e) => setRegenerateVideo(e.target.checked)}
            className="w-4 h-4 rounded border-gray-600 bg-surface-900 text-accent focus:ring-accent/50"
          />
          <span className="text-sm text-gray-300">Regenerate video</span>
        </label>
      </div>

      <button className="btn-primary w-full" onClick={handleRegenerate}>
        Start Regeneration
      </button>
    </div>
  );
}
