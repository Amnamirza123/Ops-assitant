// src/App.jsx

import { useState, useEffect } from 'react';
import { supabase } from './lib/supabaseClient';
import LoginForm from './components/LoginForm';
import RegisterForm from './components/RegisterForm';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import ClientsPanel from './components/ClientsPanel';
import './styles/index.css';

function App() {
  const [session, setSession] = useState(null);
  const [showRegister, setShowRegister] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sessionId, setSessionId] = useState(() => {
    const stored = localStorage.getItem('ops_active_session_id');
    if (stored) return stored;
    const newId = crypto.randomUUID();
    localStorage.setItem('ops_active_session_id', newId);
    return newId;
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [showClients, setShowClients] = useState(false);
  const [docsRefreshKey, setDocsRefreshKey] = useState(0);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

        const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, newSession) => {
        if (_event === 'SIGNED_OUT') {
          localStorage.removeItem('ops_active_session_id');
        }
        setSession(newSession);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  function handleNewChat() {
    const newId = crypto.randomUUID();
    localStorage.setItem('ops_active_session_id', newId);
    setSessionId(newId);
  }

  function handleSelectSession(id) {
    localStorage.setItem('ops_active_session_id', id);
    setSessionId(id);
  }

  function handleMessageSent() {
    setRefreshKey((k) => k + 1);
  }

  if (loading) {
    return <div className="app-loading">Loading…</div>;
  }

  if (!session) {
    return showRegister ? (
      <RegisterForm onSwitchToLogin={() => setShowRegister(false)} />
    ) : (
      <LoginForm onSwitchToRegister={() => setShowRegister(true)} />
    );
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onSessionDeleted={handleNewChat}
        refreshKey={refreshKey}
        docsRefreshKey={docsRefreshKey}
        onOpenClients={() => setShowClients(true)}
      />
      <ChatWindow
        sessionId={sessionId}
        onMessageSent={handleMessageSent}
        onDocumentUploaded={() => setDocsRefreshKey((k) => k + 1)}
      />

      {showClients && <ClientsPanel onClose={() => setShowClients(false)} />}
    </div>
  );
}

export default App;