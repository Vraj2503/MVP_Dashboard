import React from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * Reusable confirmation modal with cancel/confirm actions.
 * Used by Digests, Observability, and Alerts pages for destructive actions.
 */
export default function ConfirmModal({ title, message, onConfirm, onCancel, confirmLabel = 'Confirm', danger = true }) {
  return (
    <div className="confirm-modal-overlay" onClick={onCancel}>
      <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-modal-icon">
          <AlertTriangle size={28} color={danger ? 'var(--danger)' : 'var(--warning)'} />
        </div>
        <h3 className="confirm-modal-title">{title}</h3>
        <p className="confirm-modal-message">{message}</p>
        <div className="confirm-modal-actions">
          <button className="btn btn-secondary btn-base" onClick={onCancel}>
            Cancel
          </button>
          <button
            className={`btn btn-base ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
