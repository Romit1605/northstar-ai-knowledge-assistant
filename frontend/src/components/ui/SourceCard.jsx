import React from 'react';
import './SourceCard.css';

export default function SourceCard({ src, isHighlighted }) {
  // 3D tilt effect on mouse move
  const handleMouseMove = (e) => {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    const rotateX = ((y - centerY) / centerY) * -5;
    const rotateY = ((x - centerX) / centerX) * 5;
    
    card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-2px)`;
  };
  
  const handleMouseLeave = (e) => {
    e.currentTarget.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)';
  };

  return (
    <div 
      id={`source-card-${src.source_number}`}
      className={`source-card glass-panel ${isHighlighted ? 'highlighted' : ''}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div className="source-header">
        <span className="source-number">[{src.source_number}]</span>
        <span className="source-relevance">
          {Math.round(src.relevance_score * 100)}% Match
        </span>
      </div>
      <h4 className="source-title">{src.title}</h4>
      <div className="source-doc">{src.document_name}</div>
      <p className="source-excerpt">"{src.excerpt}"</p>
    </div>
  );
}
