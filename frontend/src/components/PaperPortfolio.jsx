import React from 'react';

function PaperPortfolio({ data }) {
  if (!data) {
    return (
      <div className="panel">
        <h2>$100 Paper Portfolio</h2>
        <p className="muted">Loading portfolio data...</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>$100 Paper Portfolio</h2>
      <p>
        <strong>Cash:</strong> ${Number(data.cash).toFixed(2)} &nbsp; 
        <strong>Holdings:</strong> ${Number(data.holdings_value).toFixed(2)} &nbsp; 
        <strong>Equity:</strong> ${Number(data.equity).toFixed(2)}
      </p>
      
      {data.positions && data.positions.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Quantity</th>
              <th>Market value</th>
            </tr>
          </thead>
          <tbody>
            {data.positions.map((position, index) => (
              <tr key={index}>
                <td>{position.symbol}</td>
                <td>{Number(position.quantity).toFixed(8)}</td>
                <td>${Number(position.market_value).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">No positions yet. Kronos will use 25% of available cash when it is bullish.</p>
      )}
      
      {data.trades && data.trades.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <h3 style={{ color: 'var(--muted)', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 8px' }}>
            Paper Trade History
          </h3>
          <table>
            <thead>
              <tr>
                <th>Action</th>
                <th>Signal</th>
                <th>Notional</th>
              </tr>
            </thead>
            <tbody>
              {data.trades.map((trade, index) => (
                <tr key={index}>
                  <td>{trade.action} {trade.symbol}</td>
                  <td>{trade.signal_direction}</td>
                  <td>${Number(trade.notional).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default PaperPortfolio;
