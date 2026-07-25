import React from 'react';
import './QuestionPanel.css';

export default function QuestionPanel({
  question,
  loading,
  maxLen,
  inputRef,
  recentQuestions,
  exampleQuestions,
  handleInputChange,
  handleKeyDown,
  handleClear,
  handleSubmit,
  handleExampleClick,
  handleClearHistory
}) {
  const isError = question.length >= maxLen;

  return (
    <section className="input-section glass-panel">
      <div className="input-wrapper">
        <textarea
          ref={inputRef}
          className={`question-input ${isError ? 'input-error' : ''}`}
          placeholder="Ask a question... (Shift+Enter for new line)"
          value={question}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={1}
          maxLength={maxLen}
          aria-label="Question input"
        />
        
        {isError && (
          <div className="validation-message">Question must be {maxLen} characters or fewer.</div>
        )}
        
        <span className={`char-counter ${isError ? 'limit-reached' : ''}`}>
          {question.length}/{maxLen}
        </span>
      </div>

      <div className="action-buttons">
        <button 
          className="btn btn-clear" 
          onClick={handleClear}
          disabled={loading || !question}
          aria-label="Clear chat"
        >
          Clear
        </button>
        <button 
          className="btn btn-ask" 
          onClick={handleSubmit}
          disabled={loading || !question.trim() || isError}
          aria-label="Ask question"
        >
          {loading ? 'Asking...' : 'Ask'}
        </button>
      </div>

      <div className="chips-section">
        <div className="chips-header">
          <span>Example Questions</span>
        </div>
        <div className="example-chips">
          {exampleQuestions.map((ex, idx) => (
            <button 
              key={idx} 
              className="example-chip" 
              onClick={() => handleExampleClick(ex)}
              disabled={loading}
            >
              {ex}
            </button>
          ))}
        </div>
        
        {recentQuestions.length > 0 && (
          <>
            <div className="chips-header" style={{ marginTop: '1.25rem' }}>
              <span>Recent Questions</span>
              <button className="clear-history-btn" onClick={handleClearHistory} disabled={loading}>
                Clear history
              </button>
            </div>
            <div className="example-chips">
              {recentQuestions.map((req, idx) => (
                <button 
                  key={`req-${idx}`} 
                  className="example-chip" 
                  onClick={() => handleExampleClick(req)}
                  disabled={loading}
                  title={req}
                >
                  {req.length > 60 ? req.substring(0, 60) + '...' : req}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
