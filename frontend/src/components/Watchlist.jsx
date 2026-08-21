import React from 'react';

function Watchlist({ items, onSelectSymbol }) {
  const getTrendClass = (direction) => {
    if (direction === 'bullish') return 'autonomous';
    if (direction === 'bearish') return 'review';
    return 'confirm';
  };

  const getChangeClass = (changePct) => {
    return Number(changePct) >= 0 ? 'positive' : 'negative';
  };

  const getChangeSign = (changePct) => {
    return Number(changePct) >= 0 ? '+' : '';
  };

  return (
    <div className="panel watchlist-panel">
      <div className="panel-header">
        <h2>Watchlist</h2>
        <span id="market-timestamp" className="panel-tag">CRYPTO • LIVE</span>
      </div>
      <table className="watchlist-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Change</th>
            <th>Trend</th>
          </tr>
        </thead>
        <tbody>
          {items.length > 0 ? (
            items.map((item, index) => (
              <tr key={index} onClick={() => onSelectSymbol(item.symbol)} style={{ cursor: 'pointer' }}>
                <td><strong>{item.symbol}</strong></td>
                <td>${Number(item.price).toFixed(2)}</td>
                <td className={getChangeClass(item.change_pct)}>
                  {getChangeSign(item.change_pct)}{Number(item.change_pct).toFixed(2)}%
                </td>
                <td>
                  <span className={`pill ${getTrendClass(item.direction)}`}>
                    {item.direction}
                  </span>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="4" className="muted">Loading watchlist...</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default Watchlist;
