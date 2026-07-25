import React from 'react';
import './SpaceBackground.css';

export default function SpaceBackground() {
  return (
    <div className="space-background">
      <div className="stars stars-small"></div>
      <div className="stars stars-medium"></div>
      <div className="stars stars-large"></div>
      <div className="galaxy-glow"></div>
      <div className="galaxy-glow-secondary"></div>
    </div>
  );
}
