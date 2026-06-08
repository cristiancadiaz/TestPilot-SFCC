import { Routes, Route, Navigate } from 'react-router-dom';
import { EnvironmentsPage } from './pages/EnvironmentsPage';
import { NewRunPage } from './pages/NewRunPage';
import { LiveRunPage } from './pages/LiveRunPage';
import { RunDetailPage } from './pages/RunDetailPage';
import { HistoryPage } from './pages/HistoryPage';

// Footer shows commit SHA for auditability (NFR-MD0-M3)
const commitSha = import.meta.env.VITE_COMMIT_SHA as string | undefined;

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <nav className="flex items-center gap-6">
          <span className="font-bold text-gray-900 text-lg">TestPilot SFCC</span>
          <a href="/environments" className="text-sm text-gray-600 hover:text-gray-900">
            Ambientes
          </a>
          <a href="/runs/new" className="text-sm text-gray-600 hover:text-gray-900">
            Nuevo Run
          </a>
          <a href="/runs" className="text-sm text-gray-600 hover:text-gray-900">
            Historial
          </a>
        </nav>
      </header>

      <main className="flex-1 px-6 py-8 max-w-6xl mx-auto w-full">
        <Routes>
          <Route path="/" element={<Navigate to="/runs" replace />} />
          <Route path="/environments" element={<EnvironmentsPage />} />
          <Route path="/runs/new" element={<NewRunPage />} />
          <Route path="/runs/:runId/live" element={<LiveRunPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/runs" element={<HistoryPage />} />
        </Routes>
      </main>

      <footer className="border-t border-gray-200 px-6 py-3 text-xs text-gray-400">
        TestPilot SFCC Dashboard
        {commitSha && <span className="ml-2 font-mono">{commitSha.slice(0, 8)}</span>}
      </footer>
    </div>
  );
}
