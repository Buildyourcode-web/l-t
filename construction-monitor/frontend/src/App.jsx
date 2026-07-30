import React, { useState } from 'react';
import { Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { Shield, AlertTriangle, FileText, Activity, HardHat, Bell, X, AlertCircle } from 'lucide-react';
import { useWebSocket } from './hooks/useWebSocket';
import Dashboard from './pages/Dashboard';
import Violations from './pages/Violations';
import Reports from './pages/Reports';
import SystemHealth from './pages/SystemHealth';

function Toast({ message, type, onClose }) {
  const bgColor = type === 'fire' ? 'bg-red-500/90' : type === 'no_helmet' ? 'bg-amber-500/90' : 'bg-blue-500/90';
  const Icon = type === 'fire' ? AlertTriangle : AlertCircle;
  
  return (
    <div className={`animate-slide-in flex items-center gap-3 ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg backdrop-blur-sm`}>
      <Icon className="w-5 h-5" />
      <div className="flex-1">
        <p className="font-medium text-sm">{message}</p>
      </div>
      <button onClick={onClose} className="p-1 hover:bg-white/20 rounded-full transition-colors">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export default function App() {
  const [toasts, setToasts] = useState([]);
  const wsConnected = useWebSocket((data) => {
    if (data.type === 'violation') {
      const id = Date.now();
      const typeStr = data.violation_type === 'fire' ? '🔥 Fire Alert' : data.violation_type === 'no_helmet' ? 'No Helmet' : 'No Vest';
      setToasts(prev => [...prev, { id, message: `${typeStr} detected on Camera ${data.camera_id}`, type: data.violation_type }]);
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 5000);
    }
  });

  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: Shield },
    { path: '/violations', label: 'Violations', icon: AlertTriangle },
    { path: '/reports', label: 'Reports', icon: FileText },
    { path: '/health', label: 'System Health', icon: Activity },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800/60 bg-gray-900/40 backdrop-blur-md flex flex-col z-20">
        <div className="h-16 flex items-center px-6 border-b border-gray-800/60 gap-3">
          <div className="bg-blue-600/20 p-2 rounded-lg border border-blue-500/30">
            <HardHat className="w-6 h-6 text-blue-400" />
          </div>
          <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">SiteMonitor AI</span>
        </div>
        <nav className="flex-1 py-6 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                  isActive 
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20 shadow-sm' 
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800/60">
          <div className="glass-card p-3 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center">
              <span className="font-semibold text-gray-300">AD</span>
            </div>
            <div>
              <p className="text-sm font-medium">Admin User</p>
              <p className="text-xs text-gray-500">Site Manager</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative z-10 overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b border-gray-800/60 bg-gray-950/80 backdrop-blur-md flex items-center justify-between px-8 z-20">
          <h2 className="text-lg font-semibold text-gray-200 capitalize">
            {location.pathname === '/' ? 'Dashboard' : location.pathname.substring(1).replace('-', ' ')}
          </h2>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-400">Live Feed</span>
              {wsConnected ? (
                <div className="flex items-center gap-1.5 bg-green-500/10 text-green-400 px-2.5 py-1 rounded-full border border-green-500/20 text-xs font-medium">
                  <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                  Connected
                </div>
              ) : (
                <div className="flex items-center gap-1.5 bg-red-500/10 text-red-400 px-2.5 py-1 rounded-full border border-red-500/20 text-xs font-medium">
                  <div className="w-2 h-2 rounded-full bg-red-400"></div>
                  Disconnected
                </div>
              )}
            </div>
            <button className="text-gray-400 hover:text-white transition-colors relative">
              <Bell className="w-5 h-5" />
              {toasts.length > 0 && (
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-500 rounded-full animate-ping"></span>
              )}
            </button>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-6 md:p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/violations" element={<Violations />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/health" element={<SystemHealth />} />
          </Routes>
        </div>
      </main>

      {/* Toasts Container */}
      <div className="absolute top-20 right-8 z-50 flex flex-col gap-2 w-80 pointer-events-none">
        {toasts.map(toast => (
          <div key={toast.id} className="pointer-events-auto">
            <Toast message={toast.message} type={toast.type} onClose={() => setToasts(prev => prev.filter(t => t.id !== toast.id))} />
          </div>
        ))}
      </div>
    </div>
  );
}
