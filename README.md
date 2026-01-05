# Trading Bot Frontend (BotPanel)

Production-grade MVP Frontend for the High-Frequency Trading Bot, built with React, Vite, and Lightweight Charts.

## Prerequisites
- Node.js v20+
- Docker (optional for production build)

## Quick Start

### 1. Installation
\`\`\`bash
npm install
\`\`\`

### 2. Configuration
Copy the example environment file:
\`\`\`bash
cp .env.example .env
\`\`\`
- Set \`VITE_USE_MOCK=true\` to run without a backend.
- \`VITE_DEV_PROXY_TARGET\` defaults to \`http://127.0.0.1:3000\`. Adjust in \`.env\` if needed.

### 3. Development Mode
#### Frontend (Port 5173 -> Proxy 3000)
\`\`\`bash
npm run dev
\`\`\`
Access at: \`http://localhost:5173\`

#### Backend (Port 3000)
Run uvicorn with hot reload:
\`\`\`bash
# In /backend directory
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 3000
\`\`\`

### 4. Production Build
Builds the optimized static assets to \`dist/\`.
\`\`\`bash
npm run build
\`\`\`

## Docker & Deployment Notes

To run the frontend in a container (typically served via Nginx):

\`\`\`bash
# Build image
docker build -t bot-panel-frontend .

# Run container
docker run -d -p 80:80 bot-panel-frontend
\`\`\`

### Nginx Configuration Requirements
For production deployments behind Nginx:
1.  **API Proxy**: Ensure path \`/api\` is proxied to your backend service (e.g., \`proxy_pass http://backend:3000\`).
2.  **SSE Support**: Critical for real-time updates.
    - Set \`proxy_buffering off;\` for the API location.
    - Ensure timeouts are sufficient (e.g., \`proxy_read_timeout 3600s;\`).
3.  **Base URL**: The app expects \`VITE_API_URL=/api\` by default to leverage this same-origin proxying.

## Features
- **Real-time Charting**: TradingView Lightweight Charts with SSE streaming.
- **Signals Management**: Approve/Reject signals with optimistic updates.
- **Risk Control**: Configure bot risk parameters and start/stop trading.
- **Mock Mode**: Fully functional simulation mode for testing UI without backend.
- **T-Bank Integration**: Available via gRPC (requires `tbank_sandbox` profile).
