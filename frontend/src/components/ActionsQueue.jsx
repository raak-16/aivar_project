import React from 'react';

function ActionsQueue({ actions }) {
  const getStatusClass = (status) => {
    if (status === 'EXECUTED') return 'autonomous';
    if (status === 'PENDING_CONFIRMATION' || status === 'CONFIRMED' || status === 'REJECTED') return 'confirm';
    return 'review';
  };

  return (
    <div className="panel">
      <h2>Recent Actions</h2>
      <table>
        <thead>
          <tr>
            <th>Trade</th>
            <th>Symbol</th>
            <th>Risk</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {actions && actions.length > 0 ? (
            actions.map((action, index) => (
              <tr key={index}>
                <td>{action.action_type || action.type}</td>
                <td>{action.symbol}</td>
                <td>{action.risk_score?.toFixed(4) || action.risk || 'N/A'}</td>
                <td>
                  <span className={`pill ${getStatusClass(action.status)}`}>
                    {action.status}
                  </span>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="4" className="muted">No actions found.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default ActionsQueue;
