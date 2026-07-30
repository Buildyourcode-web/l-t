import React, { useEffect, useState } from 'react';
import { Camera, AlertTriangle, ShieldAlert, Video, EyeOff } from 'lucide-react';
import { api } from '../services/api';
import { formatDistanceToNow } from 'date-fns';

export default function Dashboard() {
  const [data, setData] = useState({ cameras: [], stats: { total_cameras: 0, online_cameras: 0, today_violations: 0, today_fire: 0 } });
  const [latestImages, setLatestImages] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = async () => {
    try {
      const res = await api.getDashboard();
      setData(res);
      const imgRes = await api.getLatestImages(10);
      setLatestImages(imgRes);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const int = setInterval(fetchDashboard, 10000);
    return () => clearInterval(int);
  }, []);

  if (loading) {
    return <div className="animate-pulse flex gap-6"><div className="flex-1 space-y-4"><div className="h-24 glass-card"></div></div></div>;
  }

  return (
    <div className="flex flex-col xl:flex-row gap-6 h-full">
      <div className="flex-1 space-y-6 flex flex-col">
        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card p-5 flex items-center gap-4">
            <div className="bg-blue-500/20 p-3 rounded-lg border border-blue-500/30">
              <Camera className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-medium">Total Cameras</p>
              <h3 className="text-2xl font-bold text-gray-100">{data.stats?.total_cameras || 0}</h3>
            </div>
          </div>
          
          <div className="glass-card p-5 flex items-center gap-4">
            <div className="bg-green-500/20 p-3 rounded-lg border border-green-500/30">
              <Video className="w-6 h-6 text-green-400" />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-medium">Online Cameras</p>
              <div className="flex items-center gap-2">
                <h3 className="text-2xl font-bold text-gray-100">{data.stats?.online_cameras || 0}</h3>
                <span className="flex h-2.5 w-2.5 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                </span>
              </div>
            </div>
          </div>

          <div className="glass-card p-5 flex items-center gap-4">
            <div className="bg-amber-500/20 p-3 rounded-lg border border-amber-500/30">
              <ShieldAlert className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-medium">Today's Violations</p>
              <h3 className="text-2xl font-bold text-gray-100">{data.stats?.today_violations || 0}</h3>
            </div>
          </div>

          <div className={`glass-card p-5 flex items-center gap-4 ${(data.stats?.today_fire || 0) > 0 ? 'border-red-500/50 shadow-[0_0_15px_rgba(239,68,68,0.2)]' : ''}`}>
            <div className="bg-red-500/20 p-3 rounded-lg border border-red-500/30">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-medium">Fire Alerts</p>
              <h3 className="text-2xl font-bold text-red-400">{data.stats?.today_fire || 0}</h3>
            </div>
          </div>
        </div>

        {/* Camera Grid */}
        <div className="flex-1 glass-card p-5 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-lg">Camera Feeds</h3>
          </div>
          <div className="flex-1 overflow-auto pr-2">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5 gap-4">
              {data.cameras?.map((cam) => (
                <div key={cam.id} className="glass-card-hover p-4 group relative overflow-hidden flex flex-col gap-2">
                  <div className="flex justify-between items-start">
                    <span className="font-semibold text-gray-200">{cam.name}</span>
                    {cam.status === 'online' ? (
                      <span className="flex h-2 w-2 relative mt-1.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                      </span>
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-red-500 mt-1.5"></span>
                    )}
                  </div>
                  <div className="mt-auto pt-4 flex items-center justify-between text-xs text-gray-400">
                    <span className="bg-gray-800 px-2 py-1 rounded">Cam {cam.id}</span>
                    {cam.status === 'online' && <span>{cam.fps || '24'} FPS</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Feed Sidebar */}
      <div className="w-full xl:w-96 glass-card flex flex-col h-[800px] xl:h-auto overflow-hidden">
        <div className="p-4 border-b border-gray-800/60 bg-gray-900/50">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-gray-400" />
            Recent Events
          </h3>
        </div>
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {latestImages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-500 gap-2">
              <EyeOff className="w-8 h-8" />
              <p>No recent events</p>
            </div>
          ) : (
            latestImages.map((img, i) => (
              <div key={i} className="flex gap-4 p-3 rounded-xl hover:bg-gray-800/50 transition-colors border border-transparent hover:border-gray-700/50">
                <div className="w-20 h-16 bg-gray-800 rounded-lg overflow-hidden shrink-0 border border-gray-700">
                  <img src={img.image_url} alt="violation" className="w-full h-full object-cover" />
                </div>
                <div className="flex-1 min-w-0 flex flex-col justify-center">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm truncate">{img.camera_name}</span>
                    <span className="text-xs text-gray-500 whitespace-nowrap ml-2">
                      {img.timestamp ? formatDistanceToNow(new Date(img.timestamp), { addSuffix: true }) : 'Just now'}
                    </span>
                  </div>
                  <div>
                    {img.violation_type === 'fire' && <span className="badge-fire">🔥 Fire</span>}
                    {img.violation_type === 'no_helmet' && <span className="badge-helmet">No Helmet</span>}
                    {img.violation_type === 'no_vest' && <span className="badge-vest">No Vest</span>}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
