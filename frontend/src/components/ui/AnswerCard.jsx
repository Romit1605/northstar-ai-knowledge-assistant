import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './AnswerCard.css';

export default function AnswerCard({ response, scrollToSource }) {
  if (!response) return null;

  // Pre-process the answer text to convert raw [1] into Markdown links [1](#source-card-1)
  const preprocessMarkdown = (text) => {
    if (!text) return "";
    return text.replace(/\[(\d+)\]/g, '[$1](#source-card-$1)');
  };

  return (
    <div className="answer-card glass-panel">
      <h2 className="user-question-display">{response.question}</h2>
      
      <div className="answer-text">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ node, ...props }) => {
              const isSourceLink = props.href && props.href.startsWith('#source-card-');
              if (isSourceLink) {
                const num = props.href.split('-').pop();
                return (
                  <a 
                    href={props.href}
                    className="citation-link"
                    onClick={(e) => scrollToSource(e, num)}
                    aria-label={`Go to source ${num}`}
                  >
                    {num}
                  </a>
                );
              }
              return <a {...props} target="_blank" rel="noopener noreferrer" />;
            }
          }}
        >
          {preprocessMarkdown(response.answer)}
        </ReactMarkdown>
      </div>
      
      <div className="metadata">
        <span className={`badge ${response.sufficient_context ? 'badge-success' : 'badge-danger'}`}>
          {response.sufficient_context ? 'Grounded Answer' : 'No Context Found'}
        </span>
        <span className="badge badge-info">{response.model}</span>
        <span className="badge badge-info">{(response.response_time_ms / 1000).toFixed(1)} seconds</span>
      </div>
    </div>
  );
}
