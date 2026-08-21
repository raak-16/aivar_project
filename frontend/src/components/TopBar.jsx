import React from 'react';

function TopBar({ feedStatus, kronosStatus }) {
  return (
    <div className="topbar">
      <div className="title-wrap">
        <span className="terminal-dot"></span>
        <h1>Graduated Autonomy Engine</h1>
      </div>
      <div className="nav">
        <span id="feed-status" className="live-status">
          {feedStatus || 'Live feed connecting'}
        </span>
        <a href="/">Overview</a>
        <a href="/confirmations">Confirmations</a>
        <a href="/reviews">Review Queue</a>
        <a href="/strategies">Strategies</a>
        <a href="/audit">Audit Log</a>
      </div>
    </div>
  );
}

export default TopBar;
