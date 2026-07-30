import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Filter, ChevronLeft, ChevronRight, X, AlertTriangle, Shield, Check } from 'lucide-react';
import { format } from 'date-fns';

export default function Violations() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, size: 10 });
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ camera_id: '', violation_type: '', start_date: '', end_date: '' });
  const [page, setPage] = useState(1);
  const [modalImg, setModalImg] = useState(null);

  const fetchViolations = async () => {
    setLoading(true);
    try {
      const res = await api.getViolations({ ...filters, page, size: 10 });
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchViolations();
  }, [page]);

  const handleFilter = (e) => {
    e.preventDefault();
    setPage(1);
    fetchViolations();
  };

  const getBadge = (type) => {
    switch (type) {
      case 'fire': return <span className="badge-fire">🔥 Fire</span>;
      case 'no_helmet': return <span className="badge-helmet">No Helmet</span>;
      case 'no_vest': return <span className="badge-vest">No Vest</span>;
      default: return <span className="text-gray-400">{type}</span>;
    }
  };

  return (
    <div className="flex flex-col h-full gap-6">
      <div className="glass-card p-4">
        <form onSubmit={handleFilter} className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[150px]">
            <label className="block text-xs font-medium text-gray-400 mb-1">Camera ID</label>
            <input type="text" value={filters.camera_id} onChange={e => setFilters({ ...filters, camera_id: e.target.value })} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" placeholder="All" />
          </div>
          <div className="flex-1 min-w-[150px]">
            <label className="block text-xs font-medium text-gray-400 mb-1">Violation Type</label>
            <select value={filters.violation_type} onChange={e => setFilters({ ...filters, violation_type: e.target.value })} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
              <option value="">All Types</option>
              <option value="no_helmet">No Helmet</option>
              <option value="no_vest">No Vest</option>
              <option value="fire">Fire</option>
            </select>
          </div>
          <div className="flex-1 min-w-[150px]">
            <label className="block text-xs font-medium text-gray-400 mb-1">Start Date</label>
            <input type="date" value={filters.start_date} onChange={e => setFilters({ ...filters, start_date: e.target.value })} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="flex-1 min-w-[150px]">
            <label className="block text-xs font-medium text-gray-400 mb-1">End Date</label>
            <input type="date" value={filters.end_date} onChange={e => setFilters({ ...filters, end_date: e.target.value })} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => { setFilters({ camera_id: '', violation_type: '', start_date: '', end_date: '' }); setPage(1); }} className="btn-secondary">Reset</button>
            <button type="submit" className="btn-primary"><Filter className="w-4 h-4" /> Filter</button>
          </div>
        </form>
      </div>

      <div className="glass-card flex-1 flex flex-col overflow-hidden">
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-900/50 sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-4 px-6 table-header">ID</th>
                <th className="py-4 px-6 table-header">Date & Time</th>
                <th className="py-4 px-6 table-header">Camera</th>
                <th className="py-4 px-6 table-header">Violation Type</th>
                <th className="py-4 px-6 table-header">Confidence</th>
                <th className="py-4 px-6 table-header">Screenshot</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="6" className="p-8 text-center text-gray-500">Loading...</td></tr>
              ) : data.items?.length === 0 ? (
                <tr><td colSpan="6" className="p-8 text-center text-gray-500">No violations found</td></tr>
              ) : (
                data.items?.map((v) => (
                  <tr key={v.id} className="table-row">
                    <td className="py-3 px-6 text-sm text-gray-400">#{v.id}</td>
                    <td className="py-3 px-6 text-sm whitespace-nowrap">{v.timestamp ? format(new Date(v.timestamp), 'MMM dd, yyyy HH:mm:ss') : '-'}</td>
                    <td className="py-3 px-6 text-sm font-medium">{v.camera_id}</td>
                    <td className="py-3 px-6 text-sm">{getBadge(v.violation_type)}</td>
                    <td className="py-3 px-6 text-sm">{(v.confidence * 100).toFixed(1)}%</td>
                    <td className="py-3 px-6 text-sm">
                      {v.screenshot_path && (
                        <div className="w-12 h-8 bg-gray-800 rounded overflow-hidden cursor-pointer border border-gray-700 hover:border-gray-500" onClick={() => setModalImg(v)}>
                          <img src={v.screenshot_path} alt="screenshot" className="w-full h-full object-cover" />
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="p-4 border-t border-gray-800/60 bg-gray-900/30 flex items-center justify-between">
          <span className="text-sm text-gray-400">Showing page {data.page || 1}</span>
          <div className="flex gap-2">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="p-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 disabled:opacity-50"><ChevronLeft className="w-4 h-4" /></button>
            <button disabled={(data.items?.length || 0) < (data.size || 10)} onClick={() => setPage(p => p + 1)} className="p-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 disabled:opacity-50"><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      </div>

      {/* Modal */}
      {modalImg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setModalImg(null)}>
          <div className="glass-card max-w-4xl w-full overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-800/60 flex items-center justify-between bg-gray-900/50">
              <div className="flex items-center gap-4">
                <span className="font-semibold text-lg">Camera {modalImg.camera_id}</span>
                {getBadge(modalImg.violation_type)}
                <span className="text-gray-400 text-sm">{modalImg.timestamp ? format(new Date(modalImg.timestamp), 'PPpp') : ''}</span>
              </div>
              <button onClick={() => setModalImg(null)} className="p-1.5 text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-2 bg-black/50">
              <img src={modalImg.screenshot_path} alt="Full violation" className="w-full max-h-[70vh] object-contain rounded-lg" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
