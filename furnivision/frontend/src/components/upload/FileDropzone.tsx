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
        'relative flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200',
        isDragActive && !isDragReject && 'border-accent bg-accent/10 scale-[1.02]',
        isDragReject && 'border-danger bg-danger/10',
        !isDragActive && !isDragReject && 'border-gray-600 hover:border-accent/50 hover:bg-surface-800/50',
        disabled && 'opacity-50 cursor-not-allowed',
        className,
      )}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="text-gray-400">{icon}</div>
        <div>
          <p className="text-lg font-semibold text-gray-200">{label}</p>
          {sublabel && <p className="text-sm text-gray-500 mt-1">{sublabel}</p>}
        </div>
        {isDragActive && !isDragReject && (
          <p className="text-accent text-sm font-medium">Drop it here!</p>
        )}
        {isDragReject && (
          <p className="text-danger text-sm font-medium">File type not accepted</p>
        )}
      </div>
    </div>
  );
}
