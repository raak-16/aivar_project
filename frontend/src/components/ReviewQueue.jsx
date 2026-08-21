import React from 'react';

function ReviewQueue({ reviews }) {
  return (
    <div className="panel">
      <h2>Human Review Queue</h2>
      <table>
        <thead>
          <tr>
            <th>Review</th>
            <th>Assigned</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {reviews && reviews.length > 0 ? (
            reviews.map((item, index) => (
              <tr key={index}>
                <td>{item.action_id || item.id}</td>
                <td>{item.assigned_to || 'N/A'}</td>
                <td>
                  <span className={`pill ${item.status === 'OPEN' ? 'confirm' : item.status === 'APPROVED' ? 'autonomous' : 'review'}`}>
                    {item.status}
                  </span>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="3" className="muted">No review tasks.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default ReviewQueue;
