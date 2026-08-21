import React, { useState, useEffect, useCallback } from 'react';
import { io } from 'socket.io-client';
import MarketDisplay from './components/MarketDisplay';
import Watchlist from './components/Watchlist';
import PaperPortfolio from './components/PaperPortfolio';
import ChartPanel from './components/ChartPanel';
import GraduatedAutonomyPanel from './components/GraduatedAutonomyPanel';
import FinancialResearch from './components/FinancialResearch';
import ActionsQueue from './components/ActionsQueue';
import ConfirmationQueue from './components/ConfirmationQueue';
import ReviewQueue from './components/ReviewQueue';
import AuditLog from './components/AuditLog';
import TopBar from './components/TopBar';
import SummaryCards from './components/SummaryCards';
import MarketForecastOverview from './components/MarketForecastOverview';
import './styles/index.css';

const SOCKET_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:5000' 
  : window.location.origin;

function App() {
  const [socket, setSocket] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState('BTC-USD');
  const [paperPortfolio, setPaperPortfolio] = useState(null);
  const [marketOverview, setMarketOverview] = useState({});
  const [actions, setActions] = useState([]);
  const [confirmations, setConfirmations] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [activeStrategy, setActiveStrategy] = useState('adaptive');
  const [currentDate, setCurrentDate] = useState(new Date().toISOString().split('T')[0]);
  const [kronosStatus, setKronosStatus] = useState('warming');
  const [feedStatus, setFeedStatus] = useState('Live feed connecting');
  const [demoScenarios, setDemoScenarios] = useState([]);

  // Initialize Socket.IO connection
  useEffect(() => {
    const newSocket = io(SOCKET_URL, {
      withCredentials: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });
    
    newSocket.on('connect', () => {
      setFeedStatus('LIVE • KRONOS ' + (kronosStatus || 'READY').toUpperCase());
      newSocket.emit('request_market');
    });
    
    newSocket.on('disconnect', () => {
      setFeedStatus('Disconnected - Reconnecting...');
    });
    
    newSocket.on('market_update', (payload) => {
      if (payload && payload.symbols) {
        setMarketData(payload);
        setWatchlist(payload.symbols);
        setKronosStatus(payload.kronos_status || 'ready');
      }
    });
    
    newSocket.on('autonomy_status', (data) => {
      // Handle autonomy status updates
      console.log('Autonomy status:', data);
    });
    
    setSocket(newSocket);
    
    return () => {
      newSocket.disconnect();
    };
  }, [kronosStatus]);

  // Load initial data
  const loadInitialData = useCallback(async () => {
    try {
      const [marketRes, portfolioRes, actionsRes, confirmationsRes, reviewsRes, logsRes, scenariosRes] = await Promise.all([
        fetch('/api/market'),
        fetch('/'),
        fetch('/api/decisions'),
        fetch('/api/confirmations'),
        fetch('/reviews'),
        fetch('/audit'),
        fetch('/api/demo/scenarios'),
      ]);
      
      const marketData = await marketRes.json();
      const logsData = await logsRes.json();
      const scenariosData = await scenariosRes.json();
      
      setMarketData(marketData);
      setWatchlist(marketData.symbols || []);
      setDemoScenarios(scenariosData.scenarios || []);
      setLogs(logsData.logs || []);
      
      // Note: Portfolio and other data will be loaded via initial page render
      // For now, use placeholder data
    } catch (error) {
      console.error('Failed to load initial data:', error);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Handle chart symbol change
  const handleSymbolChange = (symbol) => {
    setSelectedSymbol(symbol);
  };

  // Handle running a demo scenario
  const handleRunDemo = useCallback(async (scenarioId) => {
    try {
      const response = await fetch(`/api/demo/${scenarioId}`);
      if (response.ok) {
        const result = await response.json();
        // Update autonomy panel with demo results
        return result;
      }
    } catch (error) {
      console.error('Demo failed:', error);
    }
    return null;
  }, []);

  // Handle governance evaluation
  const handleEvaluateAction = useCallback(async (action) => {
    try {
      const response = await fetch('/api/governance/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.error('Evaluation failed:', error);
    }
    return null;
  }, []);

  // Handle running financial research
  const handleRunResearch = useCallback(async (symbol, tradeDate) => {
    try {
      const response = await fetch('/api/financial-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, trade_date: tradeDate }),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.error('Research failed:', error);
    }
    return null;
  }, []);

  // Handle paper trade execution
  const handlePaperTrade = useCallback(async (symbol) => {
    try {
      const response = await fetch('/api/paper-trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.error('Paper trade failed:', error);
    }
    return null;
  }, []);

  return (
    <div className="app-container">
      <TopBar 
        feedStatus={feedStatus} 
        kronosStatus={kronosStatus}
      />
      
      <SummaryCards summary={summary} />
      
      <GraduatedAutonomyPanel 
        onRunDemo={handleRunDemo}
        demoScenarios={demoScenarios}
        onEvaluate={handleEvaluateAction}
      />
      
      <div className="main-grid">
        <div className="left-column">
          <Watchlist 
            items={watchlist} 
            onSelectSymbol={handleSymbolChange}
          />
          
          <PaperPortfolio data={paperPortfolio} />
          
          <MarketForecastOverview overview={marketOverview} />
        </div>
        
        <div className="right-column">
          <MarketDisplay 
            data={marketData} 
            onSelectSymbol={handleSymbolChange}
          />
          
          <ChartPanel 
            symbol={selectedSymbol}
            onSymbolChange={handleSymbolChange}
            onTrade={handlePaperTrade}
            marketData={marketData}
          />
        </div>
      </div>
      
      <div className="secondary-grid">
        <FinancialResearch 
          symbols={Object.keys(marketOverview)} 
          onRunResearch={handleRunResearch}
          currentDate={currentDate}
        />
      </div>
      
      <div className="tertiary-grid">
        <ActionsQueue actions={actions} />
        <ConfirmationQueue confirmations={confirmations} />
      </div>
      
      <div className="tertiary-grid">
        <ReviewQueue reviews={reviews} />
        <AuditLog logs={logs} />
      </div>
    </div>
  );
}

export default App;
