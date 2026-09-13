import { NavLink, Route, Routes } from "react-router-dom";

import CaseDetailPage from "./pages/CaseDetailPage";
import CasesPage from "./pages/CasesPage";
import DashboardPage from "./pages/DashboardPage";
import SimulatorPage from "./pages/SimulatorPage";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-200"
  }`;

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold">RecoverAI</span>
            <span className="text-xs text-slate-400">AI Revenue Recovery Agent</span>
          </div>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/cases" className={navLinkClass}>
              Cases
            </NavLink>
            <NavLink to="/simulator" className={navLinkClass}>
              Simulator
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-6xl w-full px-4 py-6">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/:caseId" element={<CaseDetailPage />} />
          <Route path="/simulator" element={<SimulatorPage />} />
        </Routes>
      </main>
    </div>
  );
}
