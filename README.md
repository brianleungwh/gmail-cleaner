# Gmail Cleaner

An open source tool that runs locally on your machine to help you declutter your Gmail inbox. Scan your inbox by sender domain and bulk delete thousands of promotional emails, newsletters, and spam in minutes.

[![CI](https://github.com/brianleungwh/gmail-cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/brianleungwh/gmail-cleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Svelte](https://img.shields.io/badge/svelte-5-orange.svg)

## Why build this?

I'm someone who lets junk emails pile up for years. Paid inbox cleaners exist, but I didn't want to pay. The free alternatives mostly use IMAP, which never cleaned my inbox as aggressively as I needed. So I built this tool using the Gmail API to do exactly what I wanted: scan my entire inbox by sender domain and nuke thousands of emails at once.

## Screencast

> Screencast placeholder

## Opinionated

This tool assumes you mark emails you want to keep — whether by starring, letting Gmail mark them as important, or organizing with custom labels. Emails with any of these signals are automatically protected and won't appear in scan results. Everything else is fair game for cleanup.

This means you can safely select entire domains for deletion without worrying about losing emails you've already organized or marked as important.

## Prerequisites

#### OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one. If creating a new project, you can name it whatever you want.
3. Navigate to "APIs & Services" > "Enable APIs and Services"
4. Search for and enable "Gmail API"
5. Go to "Credentials" > "Create Credentials" > "OAuth client ID"
6. Choose "Desktop app" as the application type
7. Download the credentials JSON file
8. Upload this file in the web interface when you first run the app


## Quick Start with Docker

The easiest way to get started:

```bash
# Clone the repository
git clone https://github.com/brianleungwh/gmail-cleaner.git
cd gmail-cleaner

# Start the application
docker-compose up --build

# Open your browser
open http://localhost:8000
```

The app will be available at http://localhost:8000. Upload your credentials file and start cleaning!

## Features

- 🔍 **Smart Domain Analysis** - Scan your entire inbox and group emails by sender domain
- 📊 **Visual Review** - See email counts and sample subjects for each domain before deleting
- 🛡️ **Safe Cleanup** - Preview mode lets you see what will be deleted before taking action
- 🔐 **Protected Emails** - Automatically preserves starred, important, and labeled emails
- ⚡ **Real-time Progress** - Live WebSocket updates show progress as you scan and clean
- 🐳 **Docker Support** - One-command deployment with Docker Compose


## How It Works

1. **Authenticate** - Upload your Google OAuth credentials to securely connect to Gmail
2. **Scan** - The tool scans your inbox and catalogs all sender domains
3. **Review** - Browse domains, see sample subjects, and select which ones to delete
4. **Preview** - Run a dry-run to see exactly what will be deleted
5. **Execute** - Move unwanted emails to trash in bulk

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Google Gmail API** - Secure Gmail access
- **WebSockets** - Real-time progress updates
- **Python 3.11+** - Type hints and async/await

### Frontend
- **Svelte** - Reactive UI framework
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first styling
- **Fuse.js** - Fuzzy search


## Local Development Setup

### 1. Backend Setup

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python dependencies
uv pip install -e .

# Start the FastAPI server
uv run python -m uvicorn app.main:app --reload
```

The backend will be available at http://localhost:8000

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend dev server will be available at http://localhost:5173

For production builds:

```bash
cd frontend
npm run build
```

This builds the frontend to `app/static/` for FastAPI to serve.




## Project Structure

```
gmail-cleaner/
├── app/                      # Backend application
│   ├── main.py              # FastAPI app with endpoints
│   ├── gmail_service.py     # Gmail API integration
│   └── static/              # Built frontend files (generated)
├── frontend/                # Frontend application
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/  # Svelte components
│   │   │   └── stores/      # State management
│   │   ├── App.svelte       # Main app component
│   │   └── main.js          # Entry point
│   ├── package.json
│   └── vite.config.js
├── data/                    # Credentials storage (gitignored)
├── docker-compose.yml       # Docker Compose configuration
├── Dockerfile               # Multi-stage Docker build
├── pyproject.toml          # Python dependencies
└── README.md               # This file
```

## API Endpoints

- `GET /` - Serve the web application
- `GET /health` - Health check endpoint
- `GET /auth/status` - Check authentication status
- `POST /auth/upload` - Upload OAuth credentials
- `GET /oauth/callback` - OAuth callback handler
- `POST /collect` - Start domain collection
- `POST /cleanup` - Execute cleanup (with dry_run option)
- `GET /domains` - Get collected domains
- `WebSocket /ws` - Real-time progress updates

## Security & Privacy

- **OAuth 2.0** - Secure authentication via Google
- **Local Storage** - Credentials stored locally, never sent to external servers
- **Read-Only Inbox** - Only modifies emails you explicitly select
- **Protected Emails** - Starred, important, and labeled emails are automatically protected
- **No Tracking** - No analytics or external data collection

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/brianleungwh/gmail-cleaner/issues) page
2. Create a new issue with detailed information
3. Include logs and error messages when applicable

## Disclaimer

This tool modifies your Gmail inbox. Always:

- Use preview mode first
- Review selections carefully
- Keep backups of important emails
- Test with a small batch first

**Use at your own risk. The authors are not responsible for any data loss.**

---

