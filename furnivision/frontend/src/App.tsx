import { Routes, Route } from 'react-router-dom';
import Upload from './pages/Upload';
import Confirm from './pages/Confirm';
import Processing from './pages/Processing';
import Review from './pages/Review';
import Outputs from './pages/Outputs';
import ExtractionReview from './pages/ExtractionReview';
import ImageReview from './pages/ImageReview';
import VideoPreview from './pages/VideoPreview';
import Demo from './pages/Demo';

function App() {
  return (
    <div className="min-h-screen bg-surface-900">
      <Routes>
        {/* V5 Human-in-the-Loop routes */}
        <Route path="/" element={<Upload />} />
        <Route path="/extraction-review/:projectId" element={<ExtractionReview />} />
        <Route path="/image-review/:projectId" element={<ImageReview />} />
        <Route path="/video-preview/:projectId" element={<VideoPreview />} />
        {/* Interactive demo */}
        <Route path="/demo" element={<Demo />} />
        {/* V4 Legacy routes */}
        <Route path="/confirm/:projectId" element={<Confirm />} />
        <Route path="/processing/:projectId" element={<Processing />} />
        <Route path="/review/:projectId" element={<Review />} />
        <Route path="/outputs/:projectId" element={<Outputs />} />
      </Routes>
    </div>
  );
}

export default App;
