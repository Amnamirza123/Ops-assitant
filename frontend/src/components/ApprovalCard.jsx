// src/components/ApprovalCard.jsx

import '../styles/chat.css';

function ApprovalCard({ draftEmail, onApprove, onReject, loading }) {
  return (
    <div className="ops-approval-card">
      <div className="ops-approval-header">
        <i className="ti ti-mail-fast" style={{ fontSize: '16px' }} />
        <span>Waiting for your approval</span>
      </div>

      <p className="ops-approval-subtext">
        The assistant drafted this email and won't send it until you decide.
      </p>

      <div className="ops-approval-draft">
        {draftEmail}
      </div>

      <div className="ops-approval-actions">
        <button
          className="ops-approve-btn"
          onClick={onApprove}
          disabled={loading}
        >
          <i className="ti ti-check" style={{ fontSize: '14px' }} /> Approve & send
        </button>
        <button
          className="ops-reject-btn"
          onClick={onReject}
          disabled={loading}
        >
          <i className="ti ti-x" style={{ fontSize: '14px' }} /> Reject
        </button>
      </div>
    </div>
  );
}

export default ApprovalCard;