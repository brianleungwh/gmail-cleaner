# Contributing to Gmail Cleaner

First off, thank you for considering contributing to Gmail Cleaner! It's people like you that make this tool better for everyone.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When creating a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (code snippets, screenshots, etc.)
- **Describe the behavior you observed and what you expected**
- **Include your environment details** (OS, Node version, browser)
- **Include relevant logs and error messages**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Explain why this enhancement would be useful**
- **List any examples of similar features in other tools** (if applicable)

### Pull Requests

1. Fork the repo and create your branch from `main`
2. Make your changes following our coding standards
3. Test your changes thoroughly
4. Update documentation as needed
5. Write or update tests for your changes
6. Ensure all tests pass
7. Submit your pull request

## Development Setup

### Prerequisites

- Node.js 20+
- A Google Cloud project with Gmail API enabled (see README for setup)

### Setting Up Your Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/brianleungwh/gmail-cleaner.git
   cd gmail-cleaner
   ```

2. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your VITE_GOOGLE_CLIENT_ID and VITE_GOOGLE_API_KEY
   ```

4. **Start the dev server**
   ```bash
   npm run dev
   ```

5. **Access the app** at http://localhost:5173

## Coding Standards

### JavaScript/Svelte

- Use ES6+ features
- Use const/let instead of var
- Write component-based, reusable code
- Use Svelte stores for global state
- Follow Svelte best practices
- Use Tailwind utility classes for styling

### Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - A new feature
- `fix:` - A bug fix
- `docs:` - Documentation only changes
- `style:` - Changes that don't affect code meaning (whitespace, formatting)
- `refactor:` - Code change that neither fixes a bug nor adds a feature
- `perf:` - Performance improvement
- `test:` - Adding or updating tests
- `chore:` - Changes to build process or auxiliary tools

## Testing

```bash
cd frontend

# Run all tests
npm test

# Run tests in watch mode
npm run test:watch
```

## Project Structure

```
gmail-cleaner/
├── frontend/
│   ├── src/
│   │   ├── App.svelte                  # Main app layout
│   │   ├── main.js                     # Entry point
│   │   └── lib/
│   │       ├── gmail/                  # Gmail API modules
│   │       │   ├── api.js              # gapi.client.gmail wrapper
│   │       │   ├── auth.js             # GIS + gapi initialization
│   │       │   ├── collector.js        # Domain collection logic
│   │       │   ├── cleaner.js          # Email cleanup logic
│   │       │   ├── progressHandler.js  # Progress -> store updates
│   │       │   └── __tests__/          # Vitest unit tests
│   │       ├── components/             # Svelte UI components
│   │       └── stores/                 # Svelte stores
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .github/workflows/ci.yml
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

## Questions?

Feel free to:
- Open an issue for discussion
- Join our community discussions
- Reach out to maintainers

Thank you for contributing!
