import { Routes, Route } from 'react-router-dom';
import Upload from './pages/Upload';
import Confirm from './pages/Confirm';
import Processing from './pages/Processing';
import Review from './pages/Review';
import Outputs from './pages/Outputs';

function App() {
  return (
    <div className="min-h-screen bg-surface-900">
      <Routes>
        <Route path="/" element={<Upload />} />
        <Route path="/confirm/:projectId" element={<Confirm />} />
        <Route path="/processing/:projectId" element={<Processing />} />
        <Route path="/review/:projectId" element={<Review />} />
        <Route path="/outputs/:projectId" element={<Outputs />} />
      </Routes>
    </div>
  );
}

export default App;
