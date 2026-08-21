import React from 'react';

function ConfirmationQueue({ confirmations }) {
  return (
    <div className="panel">
      <h2>Confirmation Queue</h2>
      <table>
        <thead>
          <tr>
            <th>Action</th>
            <th>Risk</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {confirmations && confirmations.length > 0 ? (
            confirmations.map((item, index) => (
              <tr key={index}>
                <td>{(item.action_type || item.type)?.toUpperCase()} {item.quantity} {item.symbol}</td>
                <td>{item.risk_score?.toFixed(4) || item.risk || 'N/A'}</td>
                <td>
                  <form className="inline" method="post" action="/confirmations">
                    <input type="hidden" name="action_id" value={item.action_id || item.id} />
                    <button type="submit" name="decision" value="approve">Approve</button>
                    <button type="submit" name="decision" value="reject" className="danger">Reject</button>
                  </form>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="3" className="muted">No confirmations waiting.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default ConfirmationQueue;
