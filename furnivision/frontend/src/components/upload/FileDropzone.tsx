import { useDropzone, type Accept } from 'react-dropzone';
import { cn } from '@/lib/utils';

interface FileDropzoneProps {
  accept: Accept;
  multiple?: boolean;
  label: string;
  sublabel?: string;
  icon: React.ReactNode;
  onDrop: (files: File[]) => void;
  disabled?: boolean;
  maxSize?: number;
  className?: string;
}

export default function FileDropzone({
  accept,
  multiple = false,
  label,
  sublabel,
  icon,
  onDrop,
  disabled = false,
  maxSize,
  className,
}: FileDropzoneProps) {
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept,
    multiple,
    onDrop,
    disabled,
    maxSize,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        'relative flex flex-col items-center justify-center p-8 rounded-xl border border-dashed cursor-pointer transition-all duration-300',
        isDragActive && !isDragReject && 'border-accent/50 bg-accent/[0.04] scale-[1.01]',
        isDragReject && 'border-red-500/40 bg-red-500/[0.04]',
        !isDragActive && !isDragReject && 'border-white/[0.1] hover:border-accent/30 hover:bg-accent/[0.02]',
        disabled && 'opacity-40 cursor-not-allowed',
        className,
      )}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="text-gray-400">{icon}</div>
        <div>
          <p className="text-sm font-medium text-gray-300">{label}</p>
          {sublabel && <p className="text-xs text-gray-600 mt-1">{sublabel}</p>}
        </div>
        {isDragActive && !isDragReject && (
          <p className="text-accent text-xs font-medium">Release to upload</p>
        )}
        {isDragReject && (
          <p className="text-red-400 text-xs font-medium">Unsupported file type</p>
        )}
      </div>
    </div>
  );
}
