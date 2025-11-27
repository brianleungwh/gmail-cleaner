# Gmail Cleaner

A web-based tool to help you declutter your Gmail inbox by identifying and removing emails from specific sender domains. Clean up thousands of promotional emails, newsletters, and spam in minutes!

[![CI](https://github.com/brianleungwh/gmail-cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/brianleungwh/gmail-cleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Svelte](https://img.shields.io/badge/svelte-5-orange.svg)

## Features

- 🔍 **Smart Domain Analysis** - Scan your entire inbox and group emails by sender domain
- 📊 **Visual Review** - See email counts and sample subjects for each domain before deleting
- 🔎 **Fuzzy Search** - Quickly find domains using intelligent search
- 🛡️ **Safe Cleanup** - Preview mode lets you see what will be deleted before taking action
- 🔐 **Protected Emails** - Automatically preserves starred, important, and labeled emails
- ⚡ **Real-time Progress** - Live WebSocket updates show progress as you scan and clean
- 🐳 **Docker Support** - One-command deployment with Docker Compose
- 🎨 **Modern UI** - Built with Svelte and Tailwind CSS for a smooth experience

## Screenshots

> *Screenshots coming soon*

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

### Infrastructure
- **Docker** - Containerized deployment
- **uv** - Fast Python package manager

## Prerequisites

Before you begin, you'll need:

1. **Google Cloud Console credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable the Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download the credentials as JSON

2. **Development Tools** (choose one):
   - **Docker** (recommended) - For containerized deployment
   - **Python 3.11+** and **Node.js 20+** - For local development

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

## Configuration

### Environment Variables

Create a `.env` file in the project root (optional):

```env
# OAuth Redirect URI (default: http://localhost:8000/oauth/callback)
OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback

# Maximum emails to process per batch
BATCH_SIZE=100

# Dry run mode (default: true)
DRY_RUN=true
```

### OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Enable APIs and Services"
4. Search for and enable "Gmail API"
5. Go to "Credentials" > "Create Credentials" > "OAuth client ID"
6. Choose "Desktop app" as the application type
7. Download the credentials JSON file
8. Upload this file in the web interface when you first run the app

**Important**: Add `http://localhost:8000/oauth/callback` to your authorized redirect URIs in the Google Cloud Console.

## Usage

### 1. Authenticate

1. Open the app in your browser (http://localhost:8000)
2. Upload your OAuth credentials JSON file
3. Click "Connect Gmail"
4. Authorize the app in the Google OAuth flow

### 2. Scan Your Inbox

1. Click "Scan Inbox"
2. Wait for the scan to complete (progress shown in real-time)
3. Review the list of domains found

### 3. Select Domains to Delete

1. Use the search box to find specific domains
2. Click checkboxes to select domains
3. Expand domains to see sample email subjects
4. Use "Select All" / "Deselect All" for bulk operations

### 4. Preview Changes

1. Click "Preview Cleanup" to see what will be deleted
2. Review the log to verify the selections
3. Check the results summary

### 5. Execute Cleanup

1. Click "Execute Cleanup"
2. Confirm the action
3. Wait for completion
4. Check your Gmail trash to verify

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
- **Trash Only** - Emails are moved to trash, not permanently deleted
- **No Tracking** - No analytics or external data collection

## Development

### Running Tests

```bash
# Backend tests
pytest

# Frontend tests
cd frontend
npm test
```

### Code Style

```bash
# Python formatting
black app/

# Python linting
ruff check app/

# Frontend formatting
cd frontend
npm run format
```

### Building for Production

```bash
# Build frontend
cd frontend
npm run build

# Build Docker image
docker build -t gmail-cleaner .

# Run production container
docker run -p 8000:8000 -v ./data:/app/data gmail-cleaner
```

## Troubleshooting

### "Not authenticated" error
- Make sure you've uploaded valid OAuth credentials
- Check that the redirect URI matches your Google Cloud Console settings
- Try deleting `data/token.json` and re-authenticating

### WebSocket connection fails
- Ensure both frontend and backend are running
- Check browser console for connection errors
- Verify firewall settings aren't blocking WebSocket connections

### OAuth redirect fails
- Verify the redirect URI in Google Cloud Console matches `http://localhost:8000/oauth/callback`
- Clear browser cookies and try again
- Check that the credentials file is valid JSON

### Docker build fails
- Ensure Docker is installed and running
- Try `docker-compose down -v` and rebuild
- Check that port 8000 is not already in use

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Roadmap

- [ ] Add Gmail filters creation based on domains
- [ ] Export domain lists to CSV/JSON
- [ ] Support for custom label-based cleanup
- [ ] Scheduled automatic cleanup
- [ ] Email analytics and insights
- [ ] Support for multiple Gmail accounts

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- UI powered by [Svelte](https://svelte.dev/) and [Tailwind CSS](https://tailwindcss.com/)
- Gmail integration via [Google APIs](https://developers.google.com/gmail/api)

## Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/brianleungwh/gmail-cleaner/issues) page
2. Create a new issue with detailed information
3. Include logs and error messages when applicable

## Disclaimer

This tool modifies your Gmail inbox. While it moves emails to trash (not permanent deletion) and protects important emails, always:

- Use preview mode first
- Review selections carefully
- Keep backups of important emails
- Test with a small batch first

**Use at your own risk. The authors are not responsible for any data loss.**

---

Made with ❤️ by the community
