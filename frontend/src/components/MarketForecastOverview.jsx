import React from 'react';

function MarketForecastOverview({ overview }) {
  if (!overview || Object.keys(overview).length === 0) {
    return null;
  }

  const getTrendClass = (direction) => {
    if (direction === 'bullish') return 'autonomous';
    if (direction === 'bearish') return 'review';
    return 'confirm';
  };

  return (
    <div className="panel" style={{ marginBottom: '20px' }}>
      <h2>Market Forecast Overview</h2>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Direction</th>
            <th>Expected Return</th>
            <th>Confidence</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(overview).map(([symbol, item]) => (
            <tr key={symbol}>
              <td>{symbol}</td>
              <td>
                <span className={`pill ${getTrendClass(item.direction)}`}>
                  {item.direction}
                </span>
              </td>
              <td>{Number(item.expected_return).toFixed(4)}</td>
              <td>{Number(item.confidence).toFixed(4)}</td>
              <td>{item.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default MarketForecastOverview;
