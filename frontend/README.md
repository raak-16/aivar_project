# Graduated Autonomy Engine - React Frontend

This directory contains the React frontend for the Graduated Autonomy Engine. It uses Vite for fast development and building.

## Prerequisites

- Node.js 18+ installed
- npm or yarn installed

## Installation

1. Navigate to the frontend directory:

```bash
cd graduated-autonomy/frontend
```

2. Install dependencies:

```bash
npm install
```

## Development Mode

Run the development server with hot-reloading:

```bash
npm run dev
```

This will start the frontend on `http://localhost:3000` with a proxy to the Flask backend on `http://localhost:5000`.

**Important:** Make sure the Flask backend is running on port 5000 before starting the frontend.

## Production Build

Build the frontend for production:

```bash
npm run build
```

This will create the optimized production build in the `../templates/react` directory, which Flask will serve.

## Using with Flask

The frontend is configured to work with the Flask backend in two ways:

### 1. Development Mode (Recommended)

- Run Flask backend: `python -m src.web_app`
- Run React frontend: `npm run dev`
- Access: `http://localhost:3000`

### 2. Production Mode

- Build React: `npm run build`
- Run Flask backend: `python -m src.web_app`
- Access: `http://localhost:5000` (Flask will serve the built React files)

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build locally
- `npm run lint` - Run ESLint

## Project Structure

```
frontend/
├── public/           # Static files
├── src/
│   ├── components/  # React components
│   ├── services/    # API and Socket.IO services (future)
│   ├── styles/      # CSS styles
│   ├── App.jsx       # Main app component
│   ├── main.jsx     # Entry point
│   └── index.css    # Global styles
├── index.html       # HTML template
├── package.json     # Dependencies
├── vite.config.js   # Vite configuration
└── README.md
```

## Components

- `TopBar.jsx` - Header with navigation
- `SummaryCards.jsx` - Summary statistics cards
- `GraduatedAutonomyPanel.jsx` - Main autonomy dashboard with demo buttons
- `MarketDisplay.jsx` - Live market data table
- `Watchlist.jsx` - Watchlist of symbols
- `ChartPanel.jsx` - Interactive chart with Kronos forecast
- `PaperPortfolio.jsx` - Paper trading portfolio
- `MarketForecastOverview.jsx` - Market forecast table
- `FinancialResearch.jsx` - TradingAgents research interface
- `ActionsQueue.jsx` - Recent actions table
- `ConfirmationQueue.jsx` - User confirmation queue
- `ReviewQueue.jsx` - Human review queue
- `AuditLog.jsx` - Audit log table

## Socket.IO Integration

The frontend connects to Socket.IO on the Flask backend for real-time market updates. The connection is established automatically when the app loads.

## API Routes

All API routes are proxied through `/api/*` to `http://localhost:5000` in development mode.

## Styling

The frontend uses a dark green terminal theme that matches the original design. All styles are in `src/styles/index.css`.

## Environment Variables

The frontend uses the following logic for API endpoints:

- In development: Proxies to `http://localhost:5000`
- In production: Uses the same origin as the page

No additional environment variables are required.
