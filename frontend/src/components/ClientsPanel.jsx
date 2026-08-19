// src/components/ClientsPanel.jsx

import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import '../styles/clients.css';

const API_URL = import.meta.env.VITE_API_URL;

function ClientsPanel({ onClose }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState('');

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('active');
  const [notes, setNotes] = useState('');
  const [department, setDepartment] = useState('');
  const [salary, setSalary] = useState('');
  const [experience, setExperience] = useState('');
  const [role, setRole] = useState('');
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadClients();
  }, []);

  async function authHeader() {
    const { data: { session } } = await supabase.auth.getSession();
    return { Authorization: `Bearer ${session?.access_token}` };
  }

  async function loadClients() {
    setLoading(true);
    try {
      const headers = await authHeader();
      const res = await fetch(`${API_URL}/clients`, { headers });
      if (res.ok) setClients(await res.json());
    } finally {
      setLoading(false);
    }
  }

  async function handleAddClient(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setAdding(true);

    try {
      const headers = await authHeader();
      await fetch(`${API_URL}/clients`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          email: email || null,
          status,
          notes: notes || null,
          role: role || null,
          experience: experience || null,
          department: department || null,
          salary: salary || null,
        }),
      });
      setName('');
      setEmail('');
      setStatus('active');
      setNotes('');
      setRole('');
      setExperience('');
      setDepartment('');
      setSalary('');
      loadClients();
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(clientId) {
    const headers = await authHeader();
    await fetch(`${API_URL}/clients/${clientId}`, { method: 'DELETE', headers });
    setClients((prev) => prev.filter((c) => c.id !== clientId));
  }

  async function handleFileImport(e) {
    const file = e.target.files[0];
    if (!file) return;

    setImporting(true);
    setImportMessage('');

    try {
      const headers = await authHeader();
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_URL}/clients/import`, {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!res.ok) throw new Error('Import failed');
      const data = await res.json();
      setImportMessage(`Imported ${data.imported} client${data.imported === 1 ? '' : 's'}.`);
      loadClients();
    } catch (err) {
      setImportMessage('Import failed: ' + err.message);
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  }

  return (
    <div className="ops-clients-overlay">
      <div className="ops-clients-panel">
        <div className="ops-clients-header">
          <h2>Clients</h2>
          <button className="ops-icon-btn" onClick={onClose}>
            <i className="ti ti-x" style={{ fontSize: '16px' }} />
          </button>
        </div>

        <div className="ops-clients-import">
          <label className="ops-import-label">
            <i className="ti ti-upload" style={{ fontSize: '14px' }} />
            {importing ? 'Importing…' : 'Import CSV or XLSX'}
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={handleFileImport}
              disabled={importing}
              hidden
            />
          </label>
          {importMessage && <p className="ops-import-message">{importMessage}</p>}
        </div>

        <form className="ops-add-client-form" onSubmit={handleAddClient}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Client name"
            required
          />
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email (optional)"
          />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Role (optional)"
          />
          <input
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            placeholder="Department (optional)"
          />
          <input
            value={experience}
            onChange={(e) => setExperience(e.target.value)}
            placeholder="Experience (optional, e.g. 3 years)"
          />
          <input
            value={salary}
            onChange={(e) => setSalary(e.target.value)}
            placeholder="Salary (optional)"
          />
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes (optional)"
          />
          <button type="submit" disabled={adding}>
            {adding ? 'Adding…' : 'Add client'}
          </button>
        </form>

        <div className="ops-clients-list">
          {loading && <p className="ops-sidebar-hint">Loading…</p>}
          {!loading && clients.length === 0 && (
            <p className="ops-sidebar-hint">No clients yet — add one or import a file.</p>
          )}
          {clients.map((c) => (
            <div key={c.id} className="ops-client-row">
              <div>
                <p className="ops-client-name">{c.name}</p>
                <p className="ops-client-meta">
                  {c.email || 'no email'} · {c.status}
                  {c.department && ` · ${c.department}`}
                  {c.role && ` · ${c.role}`}
                  {c.experience && ` · ${c.experience} exp`}
                  {c.salary && ` · ${c.salary}`}
                </p>
              </div>
              <button className="ops-icon-btn" onClick={() => handleDelete(c.id)}>
                <i className="ti ti-trash" style={{ fontSize: '13px' }} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default ClientsPanel;