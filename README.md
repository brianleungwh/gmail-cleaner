# Gmail Cleaner

A free, open source tool to declutter your Gmail inbox. Scan your inbox by sender domain and bulk delete thousands of promotional emails, newsletters, and spam in minutes.

**Your emails never leave your browser.** This app runs entirely client-side. No server processes your data.

[![CI](https://github.com/brianleungwh/gmail-cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/brianleungwh/gmail-cleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Svelte](https://img.shields.io/badge/svelte-5-orange.svg)

## Why build this?

I'm someone who lets junk emails pile up for years. Paid inbox cleaners exist, but I didn't want to pay. The free alternatives mostly use IMAP, which never cleaned my inbox as aggressively as I needed. So I built this tool using the Gmail API to do exactly what I wanted: scan my entire inbox by sender domain and nuke thousands of emails at once.

## Demo

https://github.com/user-attachments/assets/c0da139b-7612-4b28-bf40-eccda4eedcda

## Opinionated

This tool assumes you mark emails you want to keep -- whether by starring, letting Gmail mark them as important, or organizing with custom labels. Emails with any of these signals are automatically protected and won't appear in scan results. Everything else is fair game for cleanup.

This means you can safely select entire domains for deletion without worrying about losing emails you've already organized or marked as important.

## Features

- **Smart Domain Analysis** - Scan your entire inbox and group emails by sender domain
- **Visual Review** - See email counts and sample subjects for each domain before deleting
- **Safe Cleanup** - Preview mode lets you see what will be deleted before taking action
- **Protected Emails** - Automatically preserves starred, important, and labeled emails
- **Real-time Progress** - Live progress updates as you scan and clean
- **100% Client-Side** - Your Gmail token never leaves your browser. No server-side processing.

## How It Works

1. **Sign In** - Click "Sign in with Google" to grant temporary access
2. **Scan** - The tool scans your inbox and catalogs all sender domains
3. **Review** - Browse domains, see sample subjects, and select which ones to delete
4. **Preview** - Run a dry-run to see exactly what will be deleted
5. **Execute** - Move unwanted emails to trash in bulk

## Tech Stack

- **Svelte 5** - Reactive UI framework
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first styling
- **Google Identity Services (GIS)** - Browser-based OAuth
- **gapi.client** - Gmail API calls directly from the browser

## Security & Privacy

- **Client-side only** - All Gmail API calls go directly from your browser to Google's servers
- **No backend** - The app is a static site. There is no server to intercept your data
- **Token in memory** - Your access token lives only in browser memory and expires after ~1 hour
- **Open source** - Inspect every line of code yourself

## Setup for Development

### Prerequisites

You need a Google Cloud project with the Gmail API enabled and an OAuth client configured:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to "APIs & Services" > "Enable APIs and Services"
4. Search for and enable **Gmail API**
5. Go to "APIs & Services" > "Credentials"
6. Click "Create Credentials" > **API key** - note this key
7. Click "Create Credentials" > **OAuth client ID**
   - Application type: **Web application**
   - Authorized JavaScript origins: `http://localhost:5173` (for dev)
   - Authorized redirect URIs: `http://localhost:5173` (for dev)
8. Note the **Client ID**

### Install & Run

```bash
cd frontend

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your VITE_GOOGLE_CLIENT_ID and VITE_GOOGLE_API_KEY

# Install dependencies
npm install

# Start dev server
npm run dev
```

The app will be available at http://localhost:5173

### Run Tests

```bash
cd frontend
npm test
```

### Build for Production

```bash
cd frontend
npm run build
```

The built files will be in `frontend/dist/`. Deploy to any static host (GitHub Pages, Netlify, Vercel, etc.).

When deploying, add your production URL to the OAuth client's authorized JavaScript origins and redirect URIs.

## Project Structure

```
gmail-cleaner/
├── frontend/
│   ├── src/
│   │   ├── App.svelte                  # Main app component
│   │   ├── main.js                     # Entry point
│   │   └── lib/
│   │       ├── gmail/                  # Gmail API modules
│   │       │   ├── api.js              # Gmail REST API wrapper (via gapi)
│   │       │   ├── auth.js             # GIS OAuth + gapi initialization
│   │       │   ├── collector.js        # Domain scanning logic
│   │       │   ├── cleaner.js          # Email cleanup logic
│   │       │   ├── progressHandler.js  # Progress event -> store updates
│   │       │   └── __tests__/          # Vitest tests
│   │       ├── components/             # Svelte UI components
│   │       └── stores/                 # Svelte stores (state)
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .github/workflows/                  # CI pipeline
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Disclaimer

This tool modifies your Gmail inbox. Always:

- Use preview mode first
- Review selections carefully
- Keep backups of important emails
- Test with a small batch first

**Use at your own risk. The authors are not responsible for any data loss.**
