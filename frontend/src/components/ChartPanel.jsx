import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler, TimeScale } from 'chart.js';
import { Line } from 'react-chartjs-2';
import annotationPlugin from 'chartjs-plugin-annotation';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler, TimeScale, annotationPlugin);

function ChartPanel({ symbol, onSymbolChange, onTrade, marketData }) {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [model, setModel] = useState('Loading forecast');
  const [note, setNote] = useState('');
  const [actualPrice, setActualPrice] = useState('--');
  const [predictedPrice, setPredictedPrice] = useState('--');
  const [priceDelta, setPriceDelta] = useState('--');
  const [quoteTime, setQuoteTime] = useState('--');
  const [tradeResult, setTradeResult] = useState(null);
  const [tradeLoading, setTradeLoading] = useState(false);

  const chartRef = useRef(null);

  const loadChart = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/chart?symbol=${encodeURIComponent(symbol)}`);
      
      if (!response.ok) {
        throw new Error('Failed to load chart data');
      }
      
      const data = await response.json();
      
      // Get live price from market data
      const liveSymbol = marketData?.symbols?.find(s => s.symbol === symbol);
      const livePrice = liveSymbol?.price || data.actual[data.actual.length - 1]?.close;
      
      // Update comparison strip
      if (data.prediction && data.prediction.length > 0) {
        const forecast = data.prediction[data.prediction.length - 1];
        const forecastPrice = Number(forecast.close);
        const currentPrice = Number(livePrice);
        
        setActualPrice(`$${Number(livePrice).toFixed(4)}`);
        setPredictedPrice(`$${Number(forecastPrice).toFixed(4)} @ ${new Date(forecast.time).toLocaleTimeString()}`);
        
        const delta = forecastPrice - currentPrice;
        const deltaPct = (delta / currentPrice * 100).toFixed(2);
        setPriceDelta(`${delta >= 0 ? '+' : ''}$${Math.abs(delta).toFixed(4)} (${delta >= 0 ? '+' : ''}${deltaPct}%)`);
        setQuoteTime(new Date().toLocaleTimeString());
      } else {
        setActualPrice(`$${Number(livePrice).toFixed(4)}`);
        setPredictedPrice('--');
        setPriceDelta('--');
        setQuoteTime(new Date().toLocaleTimeString());
      }
      
      setModel(`${data.model.toUpperCase()} • ${data.source.toUpperCase()}`);
      setNote(data.model === 'kronos'
        ? 'Blue: Actual historical prices. Amber dashed: Kronos forecast. Shaded region: Prediction period.'
        : 'Blue: Actual prices. Amber dashed: Forecast. Shaded region: Prediction period.');
      
      // Prepare chart data
      const actual = data.actual || [];
      const predicted = data.prediction || [];
      const labels = [...actual, ...predicted].map(point => new Date(point.time).toLocaleString());
      
      const actualData = actual.map(point => Number(point.close));
      const lastActual = actual.length > 0 ? actualData[actualData.length - 1] : null;
      const actualTimestamps = actual.map(point => new Date(point.time));
      
      const predictionData = predicted.map(point => Number(point.close));
      const predictionTimestamps = predicted.map(point => new Date(point.time));
      
      // Create datasets - showing BOTH actual and predicted on the same chart
      const datasets = [
        {
          label: `${symbol} Actual Price`,
          data: actualData,
          borderColor: '#7dd3fc',
          backgroundColor: 'rgba(125, 211, 252, 0.1)',
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.18,
          fill: false,
        },
        {
          label: `${symbol} ${data.model} Forecast`,
          data: predictionData,
          borderColor: '#fbbf24',
          backgroundColor: 'rgba(251, 191, 36, 0.2)',
          pointRadius: 3,
          borderWidth: 2,
          borderDash: [7, 5],
          tension: 0.18,
          spanGaps: true,
          fill: true,
        }
      ];
      
      // Store timestamps for annotations
      const chartDataWithTimestamps = {
        labels,
        datasets,
        actualTimestamps,
        predictionTimestamps,
        actualCount: actual.length,
        predictionCount: predicted.length,
      };
      
      setChartData(chartDataWithTimestamps);
      
    } catch (err) {
      setError(err.message);
      setModel('CHART UNAVAILABLE');
      setNote('Unable to load chart data. Live quotes will continue updating.');
    } finally {
      setLoading(false);
    }
  }, [symbol, marketData]);

  useEffect(() => {
    loadChart();
  }, [loadChart]);

  const handleSymbolChange = (e) => {
    const newSymbol = e.target.value;
    onSymbolChange(newSymbol);
  };

  const handleTrade = async () => {
    if (!symbol) return;
    
    setTradeLoading(true);
    setTradeResult(null);
    
    try {
      const result = await onTrade(symbol);
      setTradeResult(result);
      
      // Reload chart after a short delay
      setTimeout(() => {
        loadChart();
      }, 1000);
    } finally {
      setTradeLoading(false);
    }
  };

  const getDeltaClass = () => {
    if (!priceDelta || priceDelta.includes('--')) return '';
    return priceDelta.includes('+') ? 'positive' : 'negative';
  };

  return (
    <div className="panel chart-panel">
      <div className="panel-header">
        <h2>Actual vs Forecast</h2>
        <div className="chart-toolbar">
          <label className="panel-tag" htmlFor="chart-symbol">Asset</label>
          <select 
            id="chart-symbol" 
            value={symbol} 
            onChange={handleSymbolChange}
          >
            {marketData?.symbols?.map((s) => (
              <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
            )) || <option value="BTC-USD">BTC-USD</option>}
          </select>
          <button 
            id="paper-trade" 
            type="button" 
            onClick={handleTrade}
            disabled={tradeLoading}
          >
            {tradeLoading ? 'Trading...' : 'Trade with Kronos'}
          </button>
          <span id="chart-model" className="panel-tag">{model}</span>
        </div>
      </div>
      
      <div className="comparison-strip">
        <div className="comparison-item">
          <div className="label">Actual live price</div>
          <div id="actual-price" className="reading">{actualPrice}</div>
        </div>
        <div className="comparison-item">
          <div className="label">Kronos target</div>
          <div id="predicted-price" className="reading">{predictedPrice}</div>
        </div>
        <div className="comparison-item">
          <div className="label">Predicted difference</div>
          <div id="price-delta" className={`reading ${getDeltaClass()}`}>{priceDelta}</div>
        </div>
        <div className="comparison-item">
          <div className="label">Quote timestamp</div>
          <div id="quote-time" className="reading">{quoteTime}</div>
        </div>
      </div>
      
      <div className="chart-wrap">
        {loading ? (
          <div style={{ 
            position: 'absolute', 
            top: '50%', 
            left: '50%', 
            transform: 'translate(-50%, -50%)',
            color: 'var(--muted)' 
          }}>
            Loading chart...
          </div>
        ) : error ? (
          <div style={{ 
            position: 'absolute', 
            top: '50%', 
            left: '50%', 
            transform: 'translate(-50%, -50%)',
            color: 'var(--red)' 
          }}>
            {error}
          </div>
        ) : chartData ? (
          <Line 
            ref={chartRef}
            data={{
              labels: chartData.labels,
              datasets: chartData.datasets
            }}
            options={{
              responsive: true,
              maintainAspectRatio: false,
              animation: false,
              interaction: {
                mode: 'index',
                intersect: false,
              },
              plugins: {
                legend: {
                  position: 'top',
                  labels: {
                    color: '#dffcf6',
                    font: { family: 'Consolas', size: 11 },
                    padding: 15,
                    usePointStyle: true,
                    pointStyle: 'circle'
                  }
                },
                tooltip: {
                  backgroundColor: 'rgba(7, 19, 15, 0.95)',
                  titleColor: '#dffcf6',
                  bodyColor: '#dffcf6',
                  borderColor: 'rgba(94, 234, 212, 0.3)',
                  borderWidth: 1,
                  displayColors: true,
                  callbacks: {
                    label: (context) => {
                      let label = context.dataset.label || '';
                      if (label) {
                        label += ': ';
                      }
                      if (context.parsed.y !== null) {
                        label += `$${context.parsed.y.toFixed(2)}`;
                      }
                      return label;
                    }
                  }
                },
                annotation: chartData.predictionCount > 0 ? {
                  annotations: {
                    forecastStart: {
                      type: 'line',
                      xMin: chartData.actualCount,
                      xMax: chartData.actualCount,
                      borderColor: 'rgba(251, 191, 36, 0.5)',
                      borderWidth: 2,
                      borderDash: [5, 5],
                      label: {
                        content: 'Forecast begins',
                        enabled: true,
                        position: 'top',
                        backgroundColor: 'rgba(251, 191, 36, 0.1)',
                        color: '#fbbf24',
                        font: { family: 'Consolas', size: 10 }
                      }
                    },
                    forecastRegion: {
                      type: 'box',
                      xMin: chartData.actualCount,
                      xMax: chartData.actualCount + chartData.predictionCount,
                      backgroundColor: 'rgba(251, 191, 36, 0.05)',
                      borderColor: 'rgba(251, 191, 36, 0.2)',
                      borderWidth: 1,
                      label: {
                        content: 'Kronos Forecast',
                        enabled: true,
                        position: { x: 'start', y: 'start' },
                        backgroundColor: 'rgba(251, 191, 36, 0.9)',
                        color: '#0d1c18',
                        font: { family: 'Consolas', size: 10, weight: 'bold' }
                      }
                    }
                  }
                } : {},
              },
              scales: {
                x: {
                  type: 'category',
                  ticks: { color: '#8fb8ad', maxTicksLimit: 8, font: { family: 'Consolas', size: 10 } },
                  grid: { color: 'rgba(143,184,173,.1)' }
                },
                y: {
                  ticks: { 
                    color: '#8fb8ad', 
                    font: { family: 'Consolas', size: 10 },
                    callback: (value) => `$${value.toFixed(2)}`
                  },
                  grid: { color: 'rgba(143,184,173,.1)' }
                }
              }
            }}
          />
        ) : null}
      </div>
      
      <p className="muted chart-note">{note}</p>
      {tradeResult && (
        <p className="muted chart-note">
          Trade: {tradeResult.status} - {tradeResult.governance?.combined?.autonomy_level || 'N/A'}
        </p>
      )}
    </div>
  );
}

export default ChartPanel;
