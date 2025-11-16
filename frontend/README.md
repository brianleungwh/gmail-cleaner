# Gmail Cleaner Frontend

This is the Svelte + Vite frontend for the Gmail Cleaner application.

## Tech Stack

- **Svelte** - Reactive UI framework
- **Vite** - Fast build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Fuse.js** - Fuzzy search library

## Project Structure

```
frontend/
├── src/
│   ├── lib/
│   │   ├── components/       # Svelte components
│   │   │   ├── ActionButtons.svelte
│   │   │   ├── AuthSection.svelte
│   │   │   ├── DomainItem.svelte
│   │   │   ├── DomainSection.svelte
│   │   │   ├── Header.svelte
│   │   │   ├── ProgressSection.svelte
│   │   │   └── ResultsSection.svelte
│   │   └── stores/           # Svelte stores
│   │       ├── appState.js   # Global app state
│   │       └── websocket.js  # WebSocket connection
│   ├── App.svelte            # Main app component
│   ├── app.css               # Global CSS with Tailwind
│   └── main.js               # Entry point
├── public/                   # Static assets
├── index.html                # HTML template
├── package.json              # Dependencies
├── vite.config.js            # Vite configuration
├── tailwind.config.js        # Tailwind configuration
└── postcss.config.js         # PostCSS configuration
```

## Development

### Prerequisites

- Node.js 20+
- npm

### Install Dependencies

```bash
cd frontend
npm install
```

### Development Server

Run the Vite dev server with hot reload and API proxy:

```bash
npm run dev
```

This will:
- Start the dev server on http://localhost:5173
- Proxy API requests to http://localhost:8000 (FastAPI backend)
- Enable hot module replacement (HMR)

**Make sure the FastAPI backend is running on port 8000!**

### Build for Production

Build the frontend for production:

```bash
npm run build
```

This will:
- Compile Svelte components to optimized JavaScript
- Process Tailwind CSS
- Bundle and minify all assets
- Output to `../app/static/` for FastAPI to serve

### Preview Production Build

Preview the production build locally:

```bash
npm run preview
```

## Development Workflow

### Working with FastAPI Backend

1. Start the FastAPI backend:
   ```bash
   cd ..
   uv run python -m uvicorn app.main:app --reload
   ```

2. In a separate terminal, start the Vite dev server:
   ```bash
   cd frontend
   npm run dev
   ```

3. Open http://localhost:5173 in your browser

The Vite dev server will proxy all API requests to the FastAPI backend on port 8000.

### Building for FastAPI

When you're ready to deploy or test with FastAPI serving the frontend:

1. Build the frontend:
   ```bash
   npm run build
   ```

2. Start FastAPI:
   ```bash
   uv run python -m uvicorn app.main:app --reload
   ```

3. Open http://localhost:8000 in your browser

FastAPI will serve the built static files from `app/static/`.

## State Management

The app uses Svelte stores for state management:

- **appState.js** - Contains all global app state (auth, domains, progress, etc.)
- **websocket.js** - Manages WebSocket connection for real-time updates

## Components

- **Header** - App title and description
- **AuthSection** - OAuth authentication flow with credentials upload
- **ActionButtons** - Scan, Preview, and Execute cleanup buttons
- **ProgressSection** - Progress bar and live log messages
- **DomainSection** - Domain list with fuzzy search and selection
- **DomainItem** - Individual domain card with expandable subjects
- **ResultsSection** - Cleanup results summary

## WebSocket Integration

The app connects to the FastAPI WebSocket endpoint (`/ws`) to receive real-time updates during:
- Domain collection
- Cleanup operations
- Progress updates

## Styling

The app uses Tailwind CSS for styling. The configuration includes:
- Custom indeterminate progress bar animation
- Responsive design
- Utility-first approach

To customize styles, edit:
- `tailwind.config.js` - Tailwind configuration
- `src/app.css` - Global styles and custom utilities

## Docker

The frontend is built as part of the Docker image using a multi-stage build:

1. **Stage 1 (frontend-builder)** - Builds the frontend with Node.js
2. **Stage 2 (python app)** - Copies built assets to FastAPI app

See `../Dockerfile` for details.
