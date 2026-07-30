import React, { useState, useEffect } from 'react';
import { FileDown, FileText, Calendar, Loader2, Table } from 'lucide-react';
import { api } from '../services/api';
import { format } from 'date-fns';

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [date, setDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [generating, setGenerating] = useState(false);

  const fetchReports = async () => {
    try {
      const res = await api.listReports();
      setReports(res.reports || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleGenerate = async () => {
    if (!date) return;
    setGenerating(true);
    try {
      await api.generateReport(date);
      await fetchReports();
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card p-6 flex items-center gap-4">
          <div className="bg-blue-500/20 p-4 rounded-xl border border-blue-500/30">
            <FileText className="w-8 h-8 text-blue-400" />
          </div>
          <div>
            <h3 className="text-2xl font-bold text-gray-100">{reports.length}</h3>
            <p className="text-gray-400">Total Reports Generated</p>
          </div>
        </div>
        <div className="glass-card p-6 flex items-center gap-4">
          <div className="bg-purple-500/20 p-4 rounded-xl border border-purple-500/30">
            <Calendar className="w-8 h-8 text-purple-400" />
          </div>
          <div>
            <h3 className="text-2xl font-bold text-gray-100">90 Days</h3>
            <p className="text-gray-400">Data Retention Period</p>
          </div>
        </div>
      </div>

      <div className="glass-card p-6">
        <h3 className="text-lg font-semibold mb-4 border-b border-gray-800/60 pb-4">Generate New Report</h3>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-400 mb-2">Select Date</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <button onClick={handleGenerate} disabled={generating || !date} className="btn-primary py-2.5 px-6 h-[42px]">
            {generating ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileText className="w-5 h-5" />}
            {generating ? 'Generating...' : 'Generate Report'}
          </button>
        </div>
      </div>

      <div className="glass-card overflow-hidden">
        <div className="p-4 border-b border-gray-800/60 bg-gray-900/50">
          <h3 className="text-lg font-semibold">Available Reports</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-900/30">
              <tr>
                <th className="py-4 px-6 table-header">Report Date</th>
                <th className="py-4 px-6 table-header">Status</th>
                <th className="py-4 px-6 table-header text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 ? (
                <tr><td colSpan="3" className="p-8 text-center text-gray-500">No reports generated yet.</td></tr>
              ) : (
                reports.map((r, i) => (
                  <tr key={i} className="table-row">
                    <td className="py-4 px-6 text-sm font-medium">{r.date}</td>
                    <td className="py-4 px-6">
                      <div className="flex gap-2">
                        {r.has_pdf && <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded text-xs">PDF</span>}
                        {r.has_excel && <span className="bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-1 rounded text-xs">Excel</span>}
                      </div>
                    </td>
                    <td className="py-4 px-6 flex justify-end gap-3">
                      {r.has_pdf && (
                        <a href={api.downloadPdf(r.date)} download target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-lg border border-gray-700 transition-colors">
                          <FileDown className="w-4 h-4 text-red-400" /> PDF
                        </a>
                      )}
                      {r.has_excel && (
                        <a href={api.downloadExcel(r.date)} download target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-lg border border-gray-700 transition-colors">
                          <Table className="w-4 h-4 text-green-400" /> Excel
                        </a>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
