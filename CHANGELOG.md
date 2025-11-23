# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Modern Svelte + Vite frontend with component-based architecture
- Real-time WebSocket updates for scanning and cleanup progress
- Fuzzy search for domain filtering using Fuse.js
- Docker support with multi-stage builds
- Comprehensive documentation and contributing guidelines

### Changed
- Migrated frontend from vanilla HTML/JS to Svelte
- Improved state management with Svelte stores
- Updated styling with Tailwind CSS
- Enhanced OAuth flow with in-app credentials upload

### Fixed
- WebSocket reconnection handling
- Progress bar accuracy during inbox scanning
- Domain list rendering performance

## [1.0.0] - YYYY-MM-DD

### Added
- Initial release
- FastAPI backend with Gmail API integration
- OAuth 2.0 authentication flow
- Domain-based email collection and analysis
- Preview mode (dry run) for safe cleanup
- Bulk email deletion with domain selection
- Protected email detection (starred, important, labeled)
- Real-time progress tracking
- WebSocket support for live updates

### Security
- OAuth 2.0 secure authentication
- Local credential storage
- No external data transmission

[Unreleased]: https://github.com/yourusername/gmail-cleaner/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/gmail-cleaner/releases/tag/v1.0.0
