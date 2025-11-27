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
- **Include your environment details** (OS, Python version, Node version, browser)
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

- Python 3.11+
- Node.js 20+
- uv (Python package manager)
- Docker (optional)

### Setting Up Your Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/brianleungwh/gmail-cleaner.git
   cd gmail-cleaner
   ```

2. **Install backend dependencies**
   ```bash
   uv pip install -e .
   ```

3. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   ```

4. **Set up pre-commit hooks** (optional but recommended)
   ```bash
   # Install pre-commit
   pip install pre-commit

   # Install hooks
   pre-commit install
   ```

### Running the Development Environment

1. **Start the backend**
   ```bash
   uv run python -m uvicorn app.main:app --reload
   ```

2. **Start the frontend** (in a separate terminal)
   ```bash
   cd frontend
   npm run dev
   ```

3. **Access the app**
   - Frontend dev server: http://localhost:5173
   - Backend API: http://localhost:8000

## Coding Standards

### Python (Backend)

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use type hints for function arguments and return values
- Use async/await for I/O operations
- Write docstrings for classes and functions
- Keep functions focused and small (single responsibility)

**Example:**
```python
async def get_threads_batch(
    self,
    page_token: Optional[str] = None,
    batch_size: int = 100
) -> tuple[List[ThreadInfo], Optional[str]]:
    """Fetch a batch of threads and their messages for processing.

    Args:
        page_token: Token for pagination
        batch_size: Number of threads to fetch

    Returns:
        Tuple of (list of threads, next page token)
    """
    # Implementation...
```

**Code formatting:**
```bash
# Format code with black
black app/

# Lint with ruff
ruff check app/
```

### JavaScript/Svelte (Frontend)

- Use ES6+ features
- Use const/let instead of var
- Write component-based, reusable code
- Use Svelte stores for global state
- Follow Svelte best practices
- Use Tailwind utility classes for styling

**Example:**
```svelte
<script>
  import { someStore } from '../stores/appState';

  export let domain;
  export let info;

  let expanded = false;

  function toggleExpand() {
    expanded = !expanded;
  }
</script>

<div class="border rounded-lg p-4">
  <!-- Component template -->
</div>
```

**Code formatting:**
```bash
cd frontend

# Format code with prettier (if configured)
npm run format

# Lint
npm run lint
```

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

**Examples:**
```
feat: add CSV export for domain lists
fix: resolve WebSocket reconnection issue
docs: update installation instructions
refactor: simplify domain filtering logic
```

## Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_gmail_service.py
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run tests in watch mode
npm test -- --watch
```

### Integration Tests

```bash
# Test the full stack
docker-compose up --build
# Test manually in browser or with E2E tests
```

## Documentation

- Update README.md if adding new features
- Add docstrings to new functions and classes
- Update API documentation for new endpoints
- Add comments for complex logic
- Update frontend/README.md for frontend changes

## Project Structure

Understanding the project structure will help you navigate the codebase:

```
gmail-cleaner/
├── app/                      # Backend
│   ├── main.py              # FastAPI routes and app
│   ├── gmail_service.py     # Gmail API logic
│   └── static/              # Built frontend
├── frontend/                # Frontend
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/  # Svelte components
│   │   │   └── stores/      # State management
│   │   └── App.svelte       # Main component
│   └── vite.config.js       # Build config
├── tests/                   # Backend tests
└── docker-compose.yml       # Docker config
```

## Release Process

1. Update version in `pyproject.toml` and `frontend/package.json`
2. Update CHANGELOG.md
3. Create a new GitHub release
4. Tag the release with version number (e.g., `v1.0.0`)
5. Build and push Docker image

## Questions?

Feel free to:
- Open an issue for discussion
- Join our community discussions
- Reach out to maintainers

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- GitHub contributors page

Thank you for contributing! 🎉
