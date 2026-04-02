import { useState } from 'react';
import { cn } from '@/lib/utils';

interface ApproveRejectProps {
  roomId: string;
  currentStatus: string;
  onApprove: (roomId: string) => void;
  onReject: (roomId: string, feedback: string, issues: string[]) => void;
}

const COMMON_ISSUES = [
  'Furniture placement incorrect',
  'Wrong furniture style',
  'Lighting looks unnatural',
  'Wall color mismatch',
  'Floor material incorrect',
  'Scale / proportions off',
  'Missing furniture items',
  'Camera angle poor',
];

export default function ApproveReject({
  roomId,
  currentStatus,
  onApprove,
  onReject,
}: ApproveRejectProps) {
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [selectedIssues, setSelectedIssues] = useState<string[]>([]);

  const toggleIssue = (issue: string) => {
    setSelectedIssues((prev) =>
      prev.includes(issue) ? prev.filter((i) => i !== issue) : [...prev, issue],
    );
  };

  const handleReject = () => {
    onReject(roomId, feedback, selectedIssues);
    setShowRejectForm(false);
    setFeedback('');
    setSelectedIssues([]);
  };

  if (currentStatus === 'approved') {
    return (
      <div className="flex items-center gap-2 text-success">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="font-semibold">Approved</span>
      </div>
    );
  }

  if (currentStatus === 'rejected') {
    return (
      <div className="flex items-center gap-2 text-danger">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="font-semibold">Rejected -- awaiting regeneration</span>
      </div>
    );
  }

  return (
    <div>
      {!showRejectForm ? (
        <div className="flex items-center gap-3">
          <button className="btn-success flex-1" onClick={() => onApprove(roomId)}>
            <span className="flex items-center justify-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Approve
            </span>
          </button>
          <button className="btn-danger flex-1" onClick={() => setShowRejectForm(true)}>
            <span className="flex items-center justify-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Reject
            </span>
          </button>
        </div>
      ) : (
        <div className="space-y-4 animate-fade-in">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Common Issues
            </label>
            <div className="flex flex-wrap gap-2">
              {COMMON_ISSUES.map((issue) => (
                <button
                  key={issue}
                  onClick={() => toggleIssue(issue)}
                  className={cn(
                    'px-3 py-1.5 text-xs rounded-lg border transition-all',
                    selectedIssues.includes(issue)
                      ? 'bg-danger/20 border-danger/50 text-danger'
                      : 'bg-surface-900 border-gray-700 text-gray-400 hover:border-gray-500',
                  )}
                >
                  {issue}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Additional Feedback
            </label>
            <textarea
              className="input-field min-h-[80px] resize-y"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Describe the issues you see..."
            />
          </div>

          <div className="flex gap-3">
            <button className="btn-danger flex-1" onClick={handleReject}>
              Confirm Rejection
            </button>
            <button
              className="btn-secondary"
              onClick={() => {
                setShowRejectForm(false);
                setFeedback('');
                setSelectedIssues([]);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
