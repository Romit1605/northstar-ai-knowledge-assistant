import React from 'react';
import './ErrorBanner.css';

export default function ErrorBanner({ error, onRetry, disabled }) {
  if (!error) return null;
  
  return (
    <div className="error-banner glass-panel" role="alert">
      <div className="error-content">
        <strong>Connection Error:</strong> {error}
        <p className="error-explanation">
          The AI service may have reached a temporary quota or rate limit. 
          Your question has been saved. Please wait a moment and try again.
        </p>
      </div>
      <button className="btn btn-retry" onClick={onRetry} disabled={disabled}>
        Retry
      </button>
    </div>
  );
}
