// src/components/ChatWindow.jsx

import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { supabase } from '../lib/supabaseClient';
import ApprovalCard from './ApprovalCard';
import ToolActivityCard from './ToolActivityCard';
import '../styles/chat.css';

const API_URL = import.meta.env.VITE_API_URL;

function ChatWindow({ sessionId, onMessageSent, onDocumentUploaded }) {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // null | 'uploading' | 'success' | 'duplicate' | 'error'
  const [pendingApproval, setPendingApproval] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadHistory();
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pendingApproval, uploadStatus]);

  useEffect(() => {
    if (uploadStatus === 'success' || uploadStatus === 'duplicate') {
      const timer = setTimeout(() => setUploadStatus(null), 2500);
      return () => clearTimeout(timer);
    }
  }, [uploadStatus]);

  async function authHeader() {
    const { data: { session } } = await supabase.auth.getSession();
    return { Authorization: `Bearer ${session?.access_token}` };
  }

  async function loadHistory() {
    try {
      const headers = await authHeader();
      const res = await fetch(`${API_URL}/chat/${sessionId}/history`, { headers });
      if (res.ok) setMessages(await res.json());
    } catch {
      // starts empty on failure
    }
  }

  async function revealTextGradually(fullText) {
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
    const words = fullText.split(' ');
    let shown = '';

    for (const word of words) {
      shown += (shown ? ' ' : '') + word;
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: shown };
        return updated;
      });
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
  }

  async function handleSend() {
    if (!message.trim() || loading) return;

    const userText = message;
    setMessage('');
    setLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: userText }]);

    try {
      const headers = await authHeader();
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText, session_id: sessionId }),
      });

      if (!res.ok) throw new Error('Server error ' + res.status);
      const data = await res.json();

      if (data.status === 'waiting_for_approval') {
        setPendingApproval(data.details);
      } else {
        await revealTextGradually(data.answer);
        onMessageSent?.();
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error: ' + error.message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleApprovalDecision(approved) {
    setLoading(true);
    try {
      const headers = await authHeader();
      const res = await fetch(`${API_URL}/approve`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, approved }),
      });
      const data = await res.json();

      await revealTextGradually(data.answer);
      setPendingApproval(null);
      onMessageSent?.();
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Error: ' + error.message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus('uploading');
    try {
      const headers = await authHeader();
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', sessionId);

      const res = await fetch(`${API_URL}/documents/upload`, {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!res.ok) throw new Error('Upload failed');
      const data = await res.json();

      if (data.duplicate) {
        setUploadStatus('duplicate');
      } else {
        setUploadStatus('success');
        onDocumentUploaded?.(); // triggers the sidebar's docsRefreshKey bump
      }
    } catch (error) {
      setUploadStatus('error');
    } finally {
      e.target.value = '';
    }
  }

  return (
    <div className="ops-chat-container">
      <div className="ops-messages">
        {messages.length === 0 && !pendingApproval && (
          <div className="ops-welcome">
            <h2>Ops Assistant</h2>
            <p>Ask about a client, run a calculation, search company docs, or draft an email.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={msg.role === 'user' ? 'ops-message user' : 'ops-message assistant'}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
          </div>
        ))}

        {pendingApproval && (
          <ApprovalCard
            draftEmail={pendingApproval.draft_email}
            onApprove={() => handleApprovalDecision(true)}
            onReject={() => handleApprovalDecision(false)}
            loading={loading}
          />
        )}

        {loading && !pendingApproval && <ToolActivityCard status="thinking" />}

        {uploadStatus === 'uploading' && (
          <div className="ops-upload-status uploading">
            <i className="ti ti-loader-2 ops-activity-spin" style={{ fontSize: '14px' }} />
            Uploading document…
          </div>
        )}
        {uploadStatus === 'success' && (
          <div className="ops-upload-status success">
            <i className="ti ti-circle-check" style={{ fontSize: '14px' }} />
            Document uploaded successfully
          </div>
        )}
        {uploadStatus === 'duplicate' && (
          <div className="ops-upload-status duplicate">
            <i className="ti ti-alert-circle" style={{ fontSize: '14px' }} />
            This document is already in this chat's knowledge base
          </div>
        )}
        {uploadStatus === 'error' && (
          <div className="ops-upload-status error">
            <i className="ti ti-x" style={{ fontSize: '14px' }} />
            Upload failed — try again
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="ops-input-area">
        <button
          className="ops-upload-pin"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading || uploadStatus === 'uploading' || !!pendingApproval}
          title="Upload a document to the knowledge base"
        >
          <i className="ti ti-paperclip" style={{ fontSize: '16px' }} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleFileUpload}
          hidden
        />

        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask something…"
          disabled={loading || !!pendingApproval}
        />
        <button onClick={handleSend} disabled={loading || !!pendingApproval}>
          {loading ? 'Thinking…' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default ChatWindow;