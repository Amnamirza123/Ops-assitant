// src/components/Sidebar.jsx

import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import '../styles/sidebar.css';

const API_URL = import.meta.env.VITE_API_URL;

function Sidebar({ activeSessionId, onSelectSession, onNewChat, onSessionDeleted, refreshKey, onOpenClients, docsRefreshKey }) {
  const [sessions, setSessions] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    loadSessions();
  }, [refreshKey]);

  useEffect(() => {
    loadDocuments();
  }, [docsRefreshKey, activeSessionId]);

  async function authHeader() {
    const { data: { session } } = await supabase.auth.getSession();
    return { Authorization: `Bearer ${session?.access_token}` };
  }

  async function loadSessions() {
    setLoading(true);
    try {
      const headers = await authHeader();
      const res = await fetch(`${API_URL}/chat/sessions`, { headers });
      if (res.ok) setSessions(await res.json());
    } catch {
      // stays empty on failure
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments() {
    try {
      const headers = await authHeader();
      const res = await fetch(`${API_URL}/documents?session_id=${activeSessionId}`, { headers });
      if (res.ok) setDocuments(await res.json());
    } catch {
      // stays empty on failure
    }
  }

  async function handleDeleteDocument(e, docId) {
    e.stopPropagation();
    const confirmed = window.confirm('Remove this document from the knowledge base?');
    if (!confirmed) return;

    setDocuments((prev) => prev.filter((d) => d.id !== docId));

    try {
      const headers = await authHeader();
      await fetch(`${API_URL}/documents/${docId}`, { method: 'DELETE', headers });
    } catch {
      loadDocuments();
    }
  }

  function startEditing(e, session) {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditValue(session.title || '');
  }

  async function saveRename(sessionId) {
    const title = editValue.trim();
    setEditingId(null);
    if (!title) return;

    setSessions((prev) =>
      prev.map((s) => (s.session_id === sessionId ? { ...s, title } : s))
    );

    try {
      const headers = await authHeader();
      await fetch(`${API_URL}/chat/${sessionId}/rename`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
    } catch {
      loadSessions();
    }
  }

  async function handleDelete(e, session) {
    e.stopPropagation();
    const confirmed = window.confirm(`Delete "${session.title}"? This can't be undone.`);
    if (!confirmed) return;

    setSessions((prev) => prev.filter((s) => s.session_id !== session.session_id));

    try {
      const headers = await authHeader();
      await fetch(`${API_URL}/chat/${session.session_id}`, {
        method: 'DELETE',
        headers,
      });
    } catch {
      loadSessions();
      return;
    }

    if (session.session_id === activeSessionId) {
      onSessionDeleted();
    }
  }

  return (
    <div className="ops-sidebar">
      <div className="ops-sidebar-top">
        <div className="ops-sidebar-brand">
          <div className="ops-sidebar-mark">
            <i className="ti ti-hexagon" style={{ fontSize: '16px' }} />
          </div>
          <span>Ops Assistant</span>
        </div>

        <button className="ops-new-chat-btn" onClick={onNewChat}>
          <i className="ti ti-plus" style={{ fontSize: '14px' }} /> New chat
        </button>

        <button className="ops-clients-btn" onClick={onOpenClients}>
          <i className="ti ti-users" style={{ fontSize: '14px' }} /> Clients
        </button>
      </div>

      <div className="ops-session-list">
        <p className="ops-section-label">Chats</p>
        {loading && <p className="ops-sidebar-hint">Loading…</p>}
        {!loading && sessions.length === 0 && (
          <p className="ops-sidebar-hint">No previous chats yet.</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={
              s.session_id === activeSessionId
                ? 'ops-session-item active'
                : 'ops-session-item'
            }
            onClick={() => editingId !== s.session_id && onSelectSession(s.session_id)}
          >
            {editingId === s.session_id ? (
              <input
                className="ops-session-rename-input"
                value={editValue}
                autoFocus
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={() => saveRename(s.session_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveRename(s.session_id);
                  if (e.key === 'Escape') setEditingId(null);
                }}
              />
            ) : (
              <>
                <span className="ops-session-title">{s.title || 'New conversation'}</span>
                <span className="ops-session-actions">
                  <button className="ops-icon-btn" title="Rename" onClick={(e) => startEditing(e, s)}>
                    <i className="ti ti-pencil" style={{ fontSize: '12px' }} />
                  </button>
                  <button className="ops-icon-btn" title="Delete" onClick={(e) => handleDelete(e, s)}>
                    <i className="ti ti-trash" style={{ fontSize: '12px' }} />
                  </button>
                </span>
              </>
            )}
          </div>
        ))}

        {documents.length > 0 && (
          <>
            <p className="ops-section-label">Knowledge base</p>
            {documents.map((doc) => (
              <div key={doc.id} className="ops-doc-item">
                <i className="ti ti-file-text" style={{ fontSize: '13px' }} />
                <span className="ops-doc-name">{doc.filename}</span>
                <button
                  className="ops-icon-btn"
                  title="Delete"
                  onClick={(e) => handleDeleteDocument(e, doc.id)}
                >
                  <i className="ti ti-trash" style={{ fontSize: '12px' }} />
                </button>
              </div>
            ))}
          </>
        )}
      </div>

      <button className="ops-logout-btn" onClick={() => supabase.auth.signOut()}>
        <i className="ti ti-logout" style={{ fontSize: '14px' }} /> Log out
      </button>
    </div>
  );
}

export default Sidebar;