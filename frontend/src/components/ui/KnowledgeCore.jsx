import React, { useEffect, useState } from 'react';
import './KnowledgeCore.css';

export default function KnowledgeCore() {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      // Calculate mouse position relative to center of screen for parallax
      const x = (e.clientX / window.innerWidth - 0.5) * 20;
      const y = (e.clientY / window.innerHeight - 0.5) * 20;
      setMousePos({ x, y });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="knowledge-core-container" style={{
      transform: `translate(${mousePos.x}px, ${mousePos.y}px)`
    }}>
      <div className="core-orbit">
        <div className="satellite satellite-1"></div>
      </div>
      <div className="core-orbit orbit-reverse">
        <div className="satellite satellite-2"></div>
      </div>
      <div className="core-sphere">
        <div className="core-grid"></div>
      </div>
    </div>
  );
}
