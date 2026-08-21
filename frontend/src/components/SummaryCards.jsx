import React from 'react';

function SummaryCards({ summary }) {
  const cards = [
    { label: 'Total Actions', value: summary?.total_actions || 0 },
    { label: 'Pending Confirmations', value: summary?.pending_confirmations || 0 },
    { label: 'Open Reviews', value: summary?.open_reviews || 0 },
    { label: 'Latest Decision', value: summary?.latest_log?.decision || 'n/a' },
  ];

  return (
    <div className="cards">
      {cards.map((card, index) => (
        <div className="card" key={index}>
          <h3>{card.label}</h3>
          <div className="value muted">
            {typeof card.value === 'number' ? card.value : card.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export default SummaryCards;
