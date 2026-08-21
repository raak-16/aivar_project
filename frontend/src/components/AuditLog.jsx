import React from 'react';

function AuditLog({ logs }) {
  return (
    <div className="panel">
      <h2>Audit Log</h2>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Decision</th>
            <th>Risk</th>
          </tr>
        </thead>
        <tbody>
          {logs && logs.length > 0 ? (
            logs.map((log, index) => (
              <tr key={index}>
                <td className="audit">{log.timestamp?.slice(0, 19) || 'N/A'}</td>
                <td>{log.decision || 'N/A'}</td>
                <td>{log.risk_score?.toFixed(4) || log.risk || 'N/A'}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="3" className="muted">No audit records yet.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default AuditLog;
