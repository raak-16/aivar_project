import React, { useState, useCallback } from 'react';

function FinancialResearch({ symbols, onRunResearch, currentDate }) {
  const [selectedSymbol, setSelectedSymbol] = useState(symbols[0] || 'BTC-USD');
  const [tradeDate, setTradeDate] = useState(currentDate);
  const [researchStatus, setResearchStatus] = useState('');
  const [researchResult, setResearchResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRunResearch = useCallback(async () => {
    if (!selectedSymbol) {
      setResearchStatus('Please select a symbol.');
      return;
    }

    setLoading(true);
    setResearchStatus('Running TradingAgents research pipeline...');
    setResearchResult(null);

    try {
      const result = await onRunResearch(selectedSymbol, tradeDate);
      
      if (result && result.analysis) {
        setResearchStatus('Research completed.');
        setResearchResult(result);
      } else {
        setResearchStatus('No analysis returned.');
      }
    } catch (error) {
      setResearchStatus(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol, tradeDate, onRunResearch]);

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleRunResearch();
    }
  };

  const getSignalClass = (signal) => {
    if (signal === 'BUY' || signal === 'bullish') return 'autonomous';
    if (signal === 'SELL' || signal === 'bearish') return 'review';
    return 'confirm';
  };

  return (
    <div className="panel" style={{ marginBottom: '20px' }}>
      <div className="panel-header">
        <h2>Multi-Agent Financial Research</h2>
        <span className="panel-tag">TradingAgents • Read-Only</span>
      </div>
      <div className="muted" style={{ marginBottom: '14px', fontSize: '12px' }}>
        Run the local TradingAgents research pipeline (Market, News, Fundamentals analysts) using yfinance data. No Reddit, Polymarket, or FRED. No trades are executed automatically.
      </div>
      
      <div id="financial-research-form" style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '14px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label htmlFor="research-symbol" className="panel-tag" style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Symbol</label>
          <select 
            id="research-symbol" 
            value={selectedSymbol} 
            onChange={(e) => setSelectedSymbol(e.target.value)}
            style={{ width: '180px' }}
          >
            {symbols.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label htmlFor="research-date" className="panel-tag" style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Trade Date</label>
          <input 
            type="date" 
            id="research-date" 
            value={tradeDate}
            onChange={(e) => setTradeDate(e.target.value)}
            onKeyPress={handleKeyPress}
            style={{ 
              width: '180px', 
              background: 'rgba(17, 32, 27, 0.95)', 
              color: 'var(--text)', 
              border: '1px solid var(--line)', 
              padding: '8px', 
              fontFamily: 'inherit' 
            }}
          />
        </div>
        <button 
          id="run-research" 
          type="button" 
          onClick={handleRunResearch}
          disabled={loading}
          style={{ height: '40px', padding: '0 16px' }}
        >
          {loading ? 'Running...' : 'Run Research'}
        </button>
      </div>
      
      <div id="research-status" className="muted" style={{ marginBottom: '12px', fontSize: '12px', color: researchStatus.includes('Error') ? 'var(--red)' : 'var(--blue)' }}>
        {researchStatus}
      </div>
      
      {researchResult && researchResult.analysis && (
        <div id="research-result">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '14px', marginBottom: '14px' }}>
            <div className="metric-box">
              <h3>Recommendation</h3>
              <div id="recommendation-value" className="value" style={{ fontSize: '24px' }}>
                {researchResult.analysis.final_trade_decision || researchResult.analysis.signal || 'N/A'}
              </div>
            </div>
            <div className="metric-box">
              <h3>Signal</h3>
              <div id="signal-value" className={`value pill ${getSignalClass(researchResult.analysis.signal)}`} style={{ fontSize: '24px' }}>
                {researchResult.analysis.signal || 'N/A'}
              </div>
            </div>
            <div className="metric-box">
              <h3>Asset Type</h3>
              <div id="asset-type-value" className="value muted" style={{ fontSize: '18px' }}>
                {(researchResult.analysis.asset_type || 'unknown').toUpperCase()}
              </div>
            </div>
          </div>
          
          <div id="trader-plan" style={{ background: 'var(--panel)', border: '1px solid var(--line)', padding: '14px', marginBottom: '14px' }}>
            <h3 style={{ margin: '0 0 10px', color: 'var(--muted)', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Trader Plan</h3>
            <div id="trader-plan-content" className="muted" style={{ fontSize: '13px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
              {researchResult.analysis.trader_plan || 'No plan generated.'}
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
            <div className="metric-box">
              <h3>Market Report</h3>
              <div id="market-report" className="muted" style={{ fontSize: '12px', lineHeight: '1.5', whiteSpace: 'pre-wrap', maxHeight: '200px', overflowY: 'auto' }}>
                {(researchResult.analysis.reports?.market) || (researchResult.analysis.market_report || 'No market report.')}
              </div>
            </div>
            <div className="metric-box">
              <h3>Fundamentals Report</h3>
              <div id="fundamentals-report" className="muted" style={{ fontSize: '12px', lineHeight: '1.5', whiteSpace: 'pre-wrap', maxHeight: '200px', overflowY: 'auto' }}>
                {(researchResult.analysis.reports?.fundamentals) || (researchResult.analysis.fundamentals_report || 'No fundamentals report.')}
              </div>
            </div>
            <div className="metric-box">
              <h3>News Report</h3>
              <div id="news-report" className="muted" style={{ fontSize: '12px', lineHeight: '1.5', whiteSpace: 'pre-wrap', maxHeight: '200px', overflowY: 'auto' }}>
                {(researchResult.analysis.reports?.news) || (researchResult.analysis.news_report || 'No news report.')}
              </div>
            </div>
          </div>
          
          {/* Display governance info if available */}
          {researchResult.analysis.governance && (
            <div className="metric-box" style={{ marginTop: '14px' }}>
              <h3>Governance Assessment</h3>
              <p className="muted">
                <strong>Risk Score:</strong> {researchResult.analysis.governance.risk_score?.toFixed(4) || 'N/A'} <br />
                <strong>Risk Level:</strong> {researchResult.analysis.governance.risk_level || 'N/A'} <br />
                <strong>Autonomy Level:</strong> {researchResult.analysis.governance.autonomy_level || 'N/A'} <br />
                <strong>Decision:</strong> {researchResult.analysis.governance.decision || 'N/A'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default FinancialResearch;
