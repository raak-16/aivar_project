import React, { useState, useEffect } from 'react';

function GraduatedAutonomyPanel({ onRunDemo, demoScenarios, onEvaluate }) {
  const [autonomyData, setAutonomyData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRunDemo = async (scenarioId) => {
    setLoading(true);
    try {
      const result = await onRunDemo(scenarioId);
      if (result) {
        setAutonomyData({
          decision: result.governance_risk?.autonomy_level || result.autonomy_decision?.level,
          riskScore: result.governance_risk?.score || result.autonomy_decision?.risk_score,
          riskLevel: result.governance_risk?.level || result.autonomy_decision?.risk_level,
          breakdown: result.governance_risk?.breakdown || result.breakdown,
          autonomyLevel: result.governance_risk?.autonomy_level || result.autonomy_decision?.level,
          signal: result.scenario?.name || 'Demo',
          symbol: result.scenario?.symbol || '-',
          quantity: result.scenario?.quantity || '-',
          confidence: result.scenario?.confidence || 0.75,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  // Determine autonomy level class
  const getAutonomyLevelClass = (level) => {
    const baseClass = 'autonomy-level-text';
    if (level === 'autonomous') return `${baseClass} autonomy-level-autonomous`;
    if (level === 'confirmation') return `${baseClass} autonomy-level-confirmation`;
    if (level === 'review') return `${baseClass} autonomy-level-review`;
    return baseClass;
  };

  // Get autonomy reason based on level
  const getAutonomyReason = (level) => {
    switch (level) {
      case 'autonomous':
        return 'Low-risk action. System will execute automatically.';
      case 'confirmation':
        return 'Medium-risk action. User confirmation required.';
      case 'review':
        return 'High-risk action. Human review required before execution.';
      default:
        return 'System ready. Waiting for proposals.';
    }
  };

  // Render buttons based on autonomy level
  const renderAutonomyButtons = (level) => {
    switch (level) {
      case 'autonomous':
        return <button className="open-review-button" disabled>✓ EXECUTED AUTONOMOUSLY</button>;
      case 'confirmation':
        return (
          <div className="confirm-buttons">
            <button className="confirm-btn" onClick={() => alert('Confirmation approved!')}>APPROVE</button>
            <button className="confirm-btn danger" onClick={() => alert('Confirmation rejected!')}>REJECT</button>
          </div>
        );
      case 'review':
        return <button className="open-review-button" onClick={() => alert('Opening human review queue...')}>OPEN REVIEW</button>;
      default:
        return null;
    }
  };

  return (
    <div className="autonomy-panel">
      <div className="autonomy-header">
        <h2 className="autonomy-title">Graduated Autonomy</h2>
        <div className="autonomy-demo-buttons">
          <button 
            className="demo-button" 
            onClick={() => handleRunDemo('demo_low')}
            disabled={loading}
          >
            Demo: LOW
          </button>
          <button 
            className="demo-button" 
            onClick={() => handleRunDemo('demo_medium')}
            disabled={loading}
          >
            Demo: MEDIUM
          </button>
          <button 
            className="demo-button" 
            onClick={() => handleRunDemo('demo_high')}
            disabled={loading}
          >
            Demo: HIGH
          </button>
        </div>
      </div>
      <div id="autonomy-display">
        <div className="autonomy-content">
          <div className="autonomy-action-display" id="autonomy-action">
            <div className="action-row">
              <span className="action-label">Action</span>
              <span className="action-value" id="autonomy-action-value">
                {autonomyData?.decision || '-'}
              </span>
            </div>
            <div className="action-row">
              <span className="action-label">Symbol</span>
              <span className="action-value" id="autonomy-symbol">
                {autonomyData?.symbol || '-'}
              </span>
            </div>
            <div className="action-row">
              <span className="action-label">Quantity</span>
              <span className="action-value" id="autonomy-quantity">
                {autonomyData?.quantity || '-'}
              </span>
            </div>
            <div className="action-row">
              <span className="action-label">Trading Signal</span>
              <span className="action-value" id="autonomy-signal">
                {autonomyData?.signal || '-'}
              </span>
            </div>
            <div className="action-row">
              <span className="action-label">Confidence</span>
              <span className="action-value" id="autonomy-confidence">
                {autonomyData?.confidence ? `${(autonomyData.confidence * 100).toFixed(0)}%` : '-'}
              </span>
            </div>
          </div>
          
          <div className="metric-box">
            <h3>Governance Risk</h3>
            <div className="risk-meter">
              <div 
                className="risk-fill" 
                id="risk-meter-fill" 
                style={{ width: `${(autonomyData?.riskScore || 0) * 100}%` }}
              ></div>
            </div>
            <p className="muted" id="risk-meter-label" style={{ margin: '12px 0 0' }}>
              Risk score: {autonomyData?.riskScore ? autonomyData.riskScore.toFixed(4) : '0.0000'} ({autonomyData?.riskLevel || 'UNKNOWN'})
            </p>
          </div>
          
          <div className="risk-factors">
            <div className="risk-factor">
              <div className="risk-factor-label">Reversibility</div>
              <div className="risk-factor-value" id="risk-reversibility">
                {autonomyData?.breakdown?.reversibility ? autonomyData.breakdown.reversibility.toFixed(4) : '0.0000'}
              </div>
            </div>
            <div className="risk-factor">
              <div className="risk-factor-label">Data Scope</div>
              <div className="risk-factor-value" id="risk-data-scope">
                {autonomyData?.breakdown?.data_scope ? autonomyData.breakdown.data_scope.toFixed(4) : '0.0000'}
              </div>
            </div>
            <div className="risk-factor">
              <div className="risk-factor-label">Regulatory</div>
              <div className="risk-factor-value" id="risk-regulatory">
                {autonomyData?.breakdown?.regulatory ? autonomyData.breakdown.regulatory.toFixed(4) : '0.0000'}
              </div>
            </div>
            <div className="risk-factor">
              <div className="risk-factor-label">Confidence Risk</div>
              <div className="risk-factor-value" id="risk-confidence">
                {autonomyData?.breakdown?.confidence_risk ? autonomyData.breakdown.confidence_risk.toFixed(4) : '0.0000'}
              </div>
            </div>
          </div>
          
          <div className="autonomy-level-display">
            <div 
              className={getAutonomyLevelClass(autonomyData?.autonomyLevel || 'autonomous')}
              id="autonomy-level-text"
            >
              {(autonomyData?.autonomyLevel || 'AUTONOMOUS').toUpperCase()}
            </div>
            <div className="autonomy-reason" id="autonomy-reason">
              {getAutonomyReason(autonomyData?.autonomyLevel)}
            </div>
            <div id="autonomy-buttons">
              {renderAutonomyButtons(autonomyData?.autonomyLevel)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default GraduatedAutonomyPanel;
