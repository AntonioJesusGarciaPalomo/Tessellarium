import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import Upload from './pages/Upload'
import Session from './pages/Session'
import Sessions from './pages/Sessions'

const navItems = [
  { path: '/', label: 'Home' },
  { path: '/upload', label: 'New Experiment' },
  { path: '/sessions', label: 'Sessions' },
]

export default function App() {
  const location = useLocation()

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <nav className="w-56 bg-gray-900 text-gray-300 flex flex-col py-6 px-4 shrink-0">
        <Link to="/" className="text-white font-bold text-lg mb-1">
          Tessellarium
        </Link>
        <span className="text-xs text-gray-500 mb-8">Decisive Experiment Compiler</span>

        {navItems.map(item => (
          <Link
            key={item.path}
            to={item.path}
            className={`px-3 py-2 rounded text-sm mb-1 transition-colors ${
              location.pathname === item.path
                ? 'bg-gray-700 text-white'
                : 'hover:bg-gray-800 hover:text-white'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/session/:id" element={<Session />} />
          <Route path="/sessions" element={<Sessions />} />
        </Routes>
      </main>
    </div>
  )
}
