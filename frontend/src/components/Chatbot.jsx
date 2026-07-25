import { useState, useRef, useEffect } from 'react';
import { askQuestion } from '../services/api';
import './Chatbot.css';

// Import our new UI components
import SpaceBackground from './ui/SpaceBackground';
import KnowledgeCore from './ui/KnowledgeCore';
import QuestionPanel from './ui/QuestionPanel';
import AnswerCard from './ui/AnswerCard';
import SourceCard from './ui/SourceCard';
import LoadingOrbit from './ui/LoadingOrbit';
import ErrorBanner from './ui/ErrorBanner';

const EXAMPLE_QUESTIONS = [
  "How many days can a hybrid employee work remotely each week?",
  "What are the core working hours for remote employees?",
  "What food is served in the cafeteria on Friday?"
];

const MAX_QUESTION_LENGTH = 500;
const MAX_RECENT_QUESTIONS = 5;

export default function Chatbot({ user, onLogout }) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState('');
  const [recentQuestions, setRecentQuestions] = useState([]);
  const [highlightedSource, setHighlightedSource] = useState(null);
  
  const inputRef = useRef(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('recentQuestions');
      if (stored) {
        setRecentQuestions(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load recent questions:", e);
    }
  }, []);

  const saveRecentQuestion = (q) => {
    try {
      const updated = [q, ...recentQuestions.filter(item => item !== q)].slice(0, MAX_RECENT_QUESTIONS);
      setRecentQuestions(updated);
      localStorage.setItem('recentQuestions', JSON.stringify(updated));
    } catch (e) {
      console.error("Failed to save recent questions:", e);
    }
  };

  const handleClearHistory = () => {
    setRecentQuestions([]);
    localStorage.removeItem('recentQuestions');
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    if (val.length <= MAX_QUESTION_LENGTH) {
      setQuestion(val);
    }
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  };

  const handleClear = () => {
    setQuestion('');
    setResponse(null);
    setError('');
    setHighlightedSource(null);
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.focus();
    }
  };

  const handleExampleClick = (example) => {
    setQuestion(example.substring(0, MAX_QUESTION_LENGTH));
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.style.height = 'auto';
        inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
        inputRef.current.focus();
      }
    }, 0);
  };

  const handleSubmit = async () => {
    if (!question.trim() || loading || question.length > MAX_QUESTION_LENGTH) return;
    
    setLoading(true);
    setError('');
    setResponse(null);
    setHighlightedSource(null);
    saveRecentQuestion(question.trim());
    
    try {
      const data = await askQuestion(question);
      setResponse(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const scrollToSource = (e, sourceNumber) => {
    e.preventDefault();
    const el = document.getElementById(`source-card-${sourceNumber}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightedSource(Number(sourceNumber));
      
      setTimeout(() => {
        setHighlightedSource((current) => current === Number(sourceNumber) ? null : current);
      }, 2000);
    }
  };

  const getInitials = (name) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
  };

  return (
    <>
      <SpaceBackground />
      <KnowledgeCore />
      
      <div className="chatbot-container">
        <header className="chatbot-header">
          <div className="header-top">
            <div className="header-content">
              <div className="header-icon">✦</div>
              <h1>Northstar AI</h1>
            </div>
            {user && (
              <div className="user-profile">
                <div className="user-avatar">{getInitials(user.full_name)}</div>
                <div className="user-info">
                  <span className="user-name">{user.full_name}</span>
                  <span className="user-email">{user.email}</span>
                </div>
                <button className="btn-logout" onClick={onLogout} aria-label="Logout">
                  Logout
                </button>
              </div>
            )}
          </div>
          <p>Your intelligent gateway to company knowledge</p>
        </header>

        <main className="chatbot-main">
          <QuestionPanel
            question={question}
            loading={loading}
            maxLen={MAX_QUESTION_LENGTH}
            inputRef={inputRef}
            recentQuestions={recentQuestions}
            exampleQuestions={EXAMPLE_QUESTIONS}
            handleInputChange={handleInputChange}
            handleKeyDown={handleKeyDown}
            handleClear={handleClear}
            handleSubmit={handleSubmit}
            handleExampleClick={handleExampleClick}
            handleClearHistory={handleClearHistory}
          />

          <div aria-live="polite" className="sr-only" style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}>
            {loading ? "Searching company documents and generating an answer..." : error ? `Error: ${error}` : response ? "Answer generated successfully." : ""}
          </div>

          <ErrorBanner 
            error={error} 
            onRetry={handleSubmit} 
            disabled={loading || question.length > MAX_QUESTION_LENGTH} 
          />

          {loading && <LoadingOrbit />}

          {response && !loading && (
            <section className="response-section">
              <AnswerCard 
                response={response} 
                scrollToSource={scrollToSource} 
              />

              {response.sources && response.sources.length > 0 && (
                <div className="sources-section glass-panel">
                  <h3 className="sources-title">Sources ({response.sources.length})</h3>
                  <div className="sources-grid">
                    {response.sources.map((src, idx) => (
                      <SourceCard 
                        key={idx} 
                        src={src} 
                        isHighlighted={highlightedSource === src.source_number}
                      />
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </>
  );
}
