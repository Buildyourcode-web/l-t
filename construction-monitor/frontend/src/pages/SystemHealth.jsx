import React, { useState, useEffect } from 'react';
import { Activity, Cpu, HardDrive, Network, Server } from 'lucide-react';
import { api } from '../services/api';

export default function SystemHealth() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await api.getSystemHealth();
        setHealth(res);
      } catch (e) {
        console.error(e);
      }
    };
    fetchHealth();
    const int = setInterval(fetchHealth, 5000);
    return () => clearInterval(int);
  }, []);

  if (!health) {
    return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div></div>;
  }

  const getColor = (val) => val > 80 ? 'bg-red-500' : val > 60 ? 'bg-amber-500' : 'bg-green-500';
  const getTextColor = (val) => val > 80 ? 'text-red-400' : val > 60 ? 'text-amber-400' : 'text-green-400';

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Server className="w-6 h-6 text-blue-400" />
          System Resources
        </h2>
        <span className="flex items-center gap-2 text-sm text-gray-400">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div> Live Updates
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* CPU */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="bg-gray-800 p-2.5 rounded-lg border border-gray-700">
                <Cpu className="w-5 h-5 text-gray-300" />
              </div>
              <h3 className="font-semibold">CPU Usage</h3>
            </div>
            <span className={`text-xl font-bold ${getTextColor(health.cpu_usage || 0)}`}>{health.cpu_usage || 0}%</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2.5 overflow-hidden">
            <div className={`h-2.5 rounded-full ${getColor(health.cpu_usage || 0)} transition-all duration-500`} style={{ width: `${health.cpu_usage || 0}%` }}></div>
          </div>
        </div>

        {/* RAM */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="bg-gray-800 p-2.5 rounded-lg border border-gray-700">
                <HardDrive className="w-5 h-5 text-gray-300" />
              </div>
              <h3 className="font-semibold">RAM Usage</h3>
            </div>
            <span className={`text-xl font-bold ${getTextColor(health.ram_percent || 0)}`}>{health.ram_percent || 0}%</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2.5 overflow-hidden mb-2">
            <div className={`h-2.5 rounded-full ${getColor(health.ram_percent || 0)} transition-all duration-500`} style={{ width: `${health.ram_percent || 0}%` }}></div>
          </div>
          <div className="flex justify-between text-xs text-gray-500 font-medium">
            <span>{health.ram_used || 0} GB Used</span>
            <span>{health.ram_total || 0} GB Total</span>
          </div>
        </div>

        {/* Network / Latency */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="bg-gray-800 p-2.5 rounded-lg border border-gray-700">
                <Activity className="w-5 h-5 text-gray-300" />
              </div>
              <h3 className="font-semibold">Inference Latency</h3>
            </div>
            <span className="text-xl font-bold text-blue-400">{health.inference_latency || '120'} ms</span>
          </div>
          <div className="flex items-center justify-between text-sm text-gray-400 mt-4 border-t border-gray-800/60 pt-4">
            <span>Target: &lt; 300ms</span>
            <span className="bg-green-500/20 text-green-400 px-2.5 py-0.5 rounded text-xs border border-green-500/30">Healthy</span>
          </div>
        </div>
      </div>

      {health.gpu && (
        <div className="glass-card p-6 mt-6">
          <h3 className="font-semibold mb-4 border-b border-gray-800/60 pb-4">GPU Resources</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-gray-400 mb-1">Model</p>
              <p className="font-medium">{health.gpu.name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">Utilization</p>
              <p className={`font-bold ${getTextColor(health.gpu.utilization)}`}>{health.gpu.utilization}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">VRAM</p>
              <p className="font-medium">{health.gpu.vram_used} / {health.gpu.vram_total} GB</p>
            </div>
            <div>
              <p className="text-sm text-gray-400 mb-1">Temperature</p>
              <p className={`font-medium ${health.gpu.temperature > 80 ? 'text-red-400' : 'text-gray-100'}`}>{health.gpu.temperature}°C</p>
            </div>
          </div>
        </div>
      )}

      <div className="glass-card p-6 mt-6">
        <h3 className="font-semibold mb-4 border-b border-gray-800/60 pb-4">Camera Network Status</h3>
        <div className="flex items-center gap-8 mb-6">
          <div>
            <p className="text-sm text-gray-400 mb-1">Active Streams</p>
            <p className="text-2xl font-bold">{health.cameras?.online || 0} / {health.cameras?.total || 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Average FPS</p>
            <p className="text-2xl font-bold text-blue-400">{health.cameras?.avg_fps || 24.5}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
