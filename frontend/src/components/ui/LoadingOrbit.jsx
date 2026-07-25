import React from 'react';
import './LoadingOrbit.css';

export default function LoadingOrbit() {
  return (
    <section className="loading-orbit-section glass-panel" aria-hidden="true">
      <div className="loading-header">
        <div className="mini-orbit-container">
          <div className="mini-core"></div>
          <div className="mini-orbit">
            <div className="mini-satellite"></div>
          </div>
        </div>
        <p>Searching company documents and generating a grounded answer...</p>
      </div>
      <div className="skeleton-container">
        <div className="skeleton-line"></div>
        <div className="skeleton-line"></div>
        <div className="skeleton-line short"></div>
      </div>
    </section>
  );
}
