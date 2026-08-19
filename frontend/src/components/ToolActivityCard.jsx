// src/components/ToolActivityCard.jsx

import '../styles/chat.css';

const TOOL_META = {
  calculator: { icon: 'ti-calculator', label: 'Calculating' },
  client_lookup: { icon: 'ti-database-search', label: 'Looking up client' },
  rag_search: { icon: 'ti-file-search', label: 'Searching knowledge base' },
  draft_email: { icon: 'ti-mail', label: 'Drafting email' },
  thinking: { icon: 'ti-loader-2', label: 'Thinking' },
};

function ToolActivityCard({ status, toolName }) {
  const meta = TOOL_META[toolName] || TOOL_META[status] || TOOL_META.thinking;

  return (
    <div className="ops-activity-card">
      <i className={`ti ${meta.icon} ops-activity-spin`} style={{ fontSize: '15px' }} />
      <span>{meta.label}…</span>
    </div>
  );
}

export default ToolActivityCard;