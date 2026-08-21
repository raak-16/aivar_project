import React from 'react';

function MarketDisplay({ data, onSelectSymbol }) {
  if (!data || !data.symbols) {
    return (
      <div className="panel">
        <h2>Market Display</h2>
        <p className="muted">Loading market data...</p>
      </div>
    );
  }

  const getTrendClass = (direction) => {
    if (direction === 'bullish') return 'autonomous';
    if (direction === 'bearish') return 'review';
    return 'confirm';
  };

  const getChangeClass = (changePct) => {
    return Number(changePct) >= 0 ? 'positive' : 'negative';
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Live Market</h2>
        <span className="panel-tag">{data.count || 0} symbols</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Change %</th>
            <th>Signal</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {data.symbols.map((symbol, index) => (
            <tr key={index} onClick={() => onSelectSymbol(symbol.symbol)} style={{ cursor: 'pointer' }}>
              <td><strong>{symbol.symbol}</strong></td>
              <td>${Number(symbol.price).toFixed(2)}</td>
              <td className={getChangeClass(symbol.change_pct)}>
                {Number(symbol.change_pct) >= 0 ? '+' : ''}{Number(symbol.change_pct).toFixed(2)}%
              </td>
              <td>
                <span className={`pill ${getTrendClass(symbol.direction)}`}>
                  {symbol.direction}
                </span>
              </td>
              <td>{Number(symbol.confidence).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default MarketDisplay;
