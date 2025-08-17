/**
 * Gmail Cleaner Web Client
 * Handles UI interactions, WebSocket communication, and fuzzy search
 */

class GmailCleanerApp {
    constructor() {
        this.ws = null;
        this.domains = {};
        this.fuse = null;
        this.selectedDomains = new Set();
        this.isAuthenticated = false;
        this.isCollecting = false;
        this.isCleaning = false;
        
        this.initializeElements();
        this.initializeWebSocket();
        this.setupEventListeners();
    }
    
    initializeElements() {
        // Status elements
        this.authStatus = document.getElementById('auth-status');
        this.authBtn = document.getElementById('auth-btn');
        
        // Action buttons
        this.collectBtn = document.getElementById('collect-btn');
        this.previewBtn = document.getElementById('preview-btn');
        this.cleanupBtn = document.getElementById('cleanup-btn');
        
        // Progress elements
        this.progressSection = document.getElementById('progress-section');
        this.progressBar = document.getElementById('progress-bar');
        this.progressText = document.getElementById('progress-text');
        this.logContainer = document.getElementById('log-container');
        
        // Domains elements
        this.domainsSection = document.getElementById('domains-section');
        this.searchInput = document.getElementById('search-input');
        this.searchResultsCount = document.getElementById('search-results-count');
        this.domainsList = document.getElementById('domains-list');
        this.selectAllBtn = document.getElementById('select-all-btn');
        this.deselectAllBtn = document.getElementById('deselect-all-btn');
        this.selectedCount = document.getElementById('selected-count');
        
        // Results elements
        this.resultsSection = document.getElementById('results-section');
        this.resultsContent = document.getElementById('results-content');
    }
    
    initializeWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.logMessage('Connected to server', 'info');
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.logMessage('Disconnected from server', 'error');
            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.initializeWebSocket(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.logMessage('Connection error', 'error');
        };
    }
    
    setupEventListeners() {
        // Authentication
        this.authBtn.addEventListener('click', () => this.authenticate());
        
        // Collection
        this.collectBtn.addEventListener('click', () => this.collectDomains());
        
        // Cleanup
        this.previewBtn.addEventListener('click', () => this.previewCleanup());
        this.cleanupBtn.addEventListener('click', () => this.executeCleanup());
        
        // Search
        this.searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
        
        // Select controls
        this.selectAllBtn.addEventListener('click', () => this.selectAll());
        this.deselectAllBtn.addEventListener('click', () => this.deselectAll());
    }
    
    handleWebSocketMessage(message) {
        const { type, data } = message;
        
        switch (type) {
            case 'authenticated':
                this.handleAuthenticated(data);
                break;
            case 'collection_started':
                this.handleCollectionStarted(data);
                break;
            case 'thread_processed':
                this.handleThreadProcessed(data);
                break;
            case 'collection_completed':
                this.handleCollectionCompleted(data);
                break;
            case 'cleanup_started':
                this.handleCleanupStarted(data);
                break;
            case 'thread_analyzed':
                this.handleThreadAnalyzed(data);
                break;
            case 'would_delete':
                this.handleWouldDelete(data);
                break;
            case 'deleted':
                this.handleDeleted(data);
                break;
            case 'cleanup_completed':
                this.handleCleanupCompleted(data);
                break;
            case 'error':
                this.handleError(data);
                break;
            default:
                console.log('Unknown message type:', type, data);
        }
    }
    
    async authenticate() {
        this.authBtn.disabled = true;
        this.authBtn.textContent = 'Authenticating...';
        
        try {
            const response = await fetch('/auth', { method: 'POST' });
            const result = await response.json();
            
            if (response.ok) {
                this.isAuthenticated = true;
                this.updateUI();
                this.logMessage('Authentication successful', 'success');
            } else {
                throw new Error(result.detail || 'Authentication failed');
            }
        } catch (error) {
            this.logMessage(`Authentication failed: ${error.message}`, 'error');
        } finally {
            this.authBtn.disabled = false;
            this.authBtn.textContent = 'Connect Gmail';
        }
    }
    
    async collectDomains() {
        if (this.isCollecting) return;
        
        this.isCollecting = true;
        this.showProgress();
        this.collectBtn.disabled = true;
        this.collectBtn.textContent = 'Scanning...';
        
        try {
            const response = await fetch('/collect', { method: 'POST' });
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.detail || 'Collection failed');
            }
            
            // Data will be handled via WebSocket messages
        } catch (error) {
            this.logMessage(`Collection failed: ${error.message}`, 'error');
            this.hideProgress();
        } finally {
            this.isCollecting = false;
            this.collectBtn.disabled = false;
            this.collectBtn.textContent = 'Scan Inbox';
        }
    }
    
    async previewCleanup() {
        await this.performCleanup(true);
    }
    
    async executeCleanup() {
        if (!confirm('Are you sure you want to delete the selected domains? This action cannot be undone.')) {
            return;
        }
        await this.performCleanup(false);
    }
    
    async performCleanup(dryRun) {
        if (this.isCleaning) return;
        
        this.isCleaning = true;
        this.showProgress();
        
        const selectedDomains = Array.from(this.selectedDomains);
        
        try {
            const response = await fetch('/cleanup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    domains: selectedDomains,
                    dry_run: dryRun,
                    limit: null
                })
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.detail || 'Cleanup failed');
            }
            
            // Results will be handled via WebSocket messages
        } catch (error) {
            this.logMessage(`Cleanup failed: ${error.message}`, 'error');
            this.hideProgress();
        } finally {
            this.isCleaning = false;
        }
    }
    
    handleAuthenticated(data) {
        this.isAuthenticated = true;
        this.authStatus.textContent = 'Connected to Gmail';
        this.authStatus.className = 'text-green-600';
        this.updateUI();
    }
    
    handleCollectionStarted(data) {
        this.logMessage('Starting domain collection...', 'info');
        this.progressText.textContent = 'Scanning inbox threads...';
    }
    
    handleThreadProcessed(data) {
        const { thread_id, domain, subject, total_threads, unique_domains } = data;
        this.logMessage(`Thread ${thread_id}: ${domain} - "${subject}"`, 'info');
        this.progressText.textContent = `Processed ${total_threads} threads, found ${unique_domains} unique domains`;
        
        // Update progress bar (estimate based on thread count)
        const progress = Math.min((total_threads / 1000) * 100, 95);
        this.progressBar.style.width = `${progress}%`;
    }
    
    handleCollectionCompleted(data) {
        const { total_threads, unique_domains } = data;
        this.logMessage(`Collection complete: ${total_threads} threads, ${unique_domains} domains`, 'success');
        this.progressBar.style.width = '100%';
        this.progressText.textContent = 'Collection complete!';
        
        // Load domains from server
        this.loadDomains();
        
        setTimeout(() => {
            this.hideProgress();
            this.showDomains();
        }, 1000);
    }
    
    handleCleanupStarted(data) {
        const { domains_count, dry_run } = data;
        const mode = dry_run ? 'preview' : 'cleanup';
        this.logMessage(`Starting ${mode} for ${domains_count} domains...`, 'info');
        this.progressText.textContent = `${dry_run ? 'Previewing' : 'Cleaning'} selected domains...`;
    }
    
    handleThreadAnalyzed(data) {
        const { thread_id, subject, sender } = data;
        this.logMessage(`Analyzing: ${sender} - "${subject}"`, 'info');
    }
    
    handleWouldDelete(data) {
        const { subject, sender, message_count } = data;
        this.logMessage(`WOULD DELETE: ${sender} - "${subject}" (${message_count} msgs)`, 'warning');
    }
    
    handleDeleted(data) {
        const { subject, sender, message_count } = data;
        this.logMessage(`DELETED: ${sender} - "${subject}" (${message_count} msgs)`, 'success');
    }
    
    handleCleanupCompleted(data) {
        const { threads_processed, threads_deleted, messages_deleted, messages_kept } = data;
        this.logMessage(`Cleanup complete: ${threads_deleted}/${threads_processed} threads deleted`, 'success');
        
        this.hideProgress();
        this.showResults(data);
    }
    
    handleError(data) {
        this.logMessage(`Error: ${data.message}`, 'error');
        this.hideProgress();
    }
    
    async loadDomains() {
        try {
            const response = await fetch('/domains');
            const result = await response.json();
            
            if (response.ok) {
                this.domains = result.domains;
                this.setupFuzzySearch();
                this.renderDomains();
            }
        } catch (error) {
            this.logMessage(`Failed to load domains: ${error.message}`, 'error');
        }
    }
    
    setupFuzzySearch() {
        const searchData = Object.entries(this.domains).map(([domain, info]) => ({
            domain,
            count: info.count,
            subjects: info.sample_subjects.join(' ')
        }));
        
        this.fuse = new Fuse(searchData, {
            keys: ['domain', 'subjects'],
            threshold: 0.3,
            includeScore: true
        });
    }
    
    renderDomains(filteredDomains = null) {
        const domainsToRender = filteredDomains || Object.entries(this.domains);
        
        this.domainsList.innerHTML = '';
        
        domainsToRender.forEach(([domain, info]) => {
            const domainElement = this.createDomainElement(domain, info);
            this.domainsList.appendChild(domainElement);
        });
        
        this.updateSearchCount(domainsToRender.length);
        this.updateSelectionCount();
    }
    
    createDomainElement(domain, info) {
        const div = document.createElement('div');
        div.className = 'border border-gray-200 rounded-lg p-4 hover:bg-gray-50';
        div.dataset.domain = domain;
        
        const isSelected = this.selectedDomains.has(domain);
        
        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <input 
                        type="checkbox" 
                        class="domain-checkbox h-4 w-4 text-blue-600 border-gray-300 rounded"
                        ${isSelected ? 'checked' : ''}
                        data-domain="${domain}"
                    >
                    <div>
                        <div class="font-medium text-gray-900">${domain}</div>
                        <div class="text-sm text-gray-500">${info.count} threads</div>
                    </div>
                </div>
                <button class="expand-btn text-blue-500 hover:text-blue-700" data-domain="${domain}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                    </svg>
                </button>
            </div>
            <div class="subjects-list mt-3 hidden">
                <div class="text-sm text-gray-600 font-medium mb-2">Sample subjects:</div>
                ${info.sample_subjects.map(subject => `
                    <div class="text-sm text-gray-500 ml-4">• ${subject}</div>
                `).join('')}
            </div>
        `;
        
        // Add event listeners
        const checkbox = div.querySelector('.domain-checkbox');
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.selectedDomains.add(domain);
            } else {
                this.selectedDomains.delete(domain);
            }
            this.updateSelectionCount();
        });
        
        const expandBtn = div.querySelector('.expand-btn');
        const subjectsList = div.querySelector('.subjects-list');
        expandBtn.addEventListener('click', () => {
            subjectsList.classList.toggle('hidden');
            expandBtn.querySelector('svg').classList.toggle('rotate-180');
        });
        
        return div;
    }
    
    handleSearch(query) {
        if (!query.trim()) {
            this.renderDomains();
            this.searchResultsCount.textContent = 'Showing all domains';
            return;
        }
        
        const results = this.fuse.search(query);
        const filteredDomains = results.map(result => [result.item.domain, this.domains[result.item.domain]]);
        
        this.renderDomains(filteredDomains);
        this.searchResultsCount.textContent = `Showing ${filteredDomains.length} of ${Object.keys(this.domains).length} domains`;
    }
    
    selectAll() {
        // Get visible domains
        const visibleDomains = this.domainsList.querySelectorAll('.domain-checkbox');
        visibleDomains.forEach(checkbox => {
            checkbox.checked = true;
            this.selectedDomains.add(checkbox.dataset.domain);
        });
        this.updateSelectionCount();
    }
    
    deselectAll() {
        // Get visible domains
        const visibleDomains = this.domainsList.querySelectorAll('.domain-checkbox');
        visibleDomains.forEach(checkbox => {
            checkbox.checked = false;
            this.selectedDomains.delete(checkbox.dataset.domain);
        });
        this.updateSelectionCount();
    }
    
    updateSearchCount(visibleCount) {
        this.searchResultsCount.textContent = `Showing ${visibleCount} of ${Object.keys(this.domains).length} domains`;
    }
    
    updateSelectionCount() {
        this.selectedCount.textContent = this.selectedDomains.size;
        
        // Enable/disable cleanup buttons
        const hasSelection = this.selectedDomains.size > 0;
        this.previewBtn.disabled = !hasSelection;
        this.cleanupBtn.disabled = !hasSelection;
    }
    
    showProgress() {
        this.progressSection.classList.remove('hidden');
        this.domainsSection.classList.add('hidden');
        this.resultsSection.classList.add('hidden');
        this.logContainer.innerHTML = '<div class="text-sm text-gray-500">Starting...</div>';
    }
    
    hideProgress() {
        this.progressSection.classList.add('hidden');
    }
    
    showDomains() {
        this.domainsSection.classList.remove('hidden');
        this.updateUI();
    }
    
    showResults(data) {
        this.resultsSection.classList.remove('hidden');
        this.domainsSection.classList.add('hidden');
        
        const { threads_processed, threads_deleted, messages_deleted, messages_kept } = data;
        
        this.resultsContent.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-blue-50 p-4 rounded-lg">
                    <div class="text-2xl font-bold text-blue-600">${threads_processed}</div>
                    <div class="text-sm text-blue-800">Threads Processed</div>
                </div>
                <div class="bg-red-50 p-4 rounded-lg">
                    <div class="text-2xl font-bold text-red-600">${threads_deleted}</div>
                    <div class="text-sm text-red-800">Threads Deleted</div>
                </div>
                <div class="bg-red-50 p-4 rounded-lg">
                    <div class="text-2xl font-bold text-red-600">${messages_deleted}</div>
                    <div class="text-sm text-red-800">Messages Deleted</div>
                </div>
                <div class="bg-green-50 p-4 rounded-lg">
                    <div class="text-2xl font-bold text-green-600">${messages_kept}</div>
                    <div class="text-sm text-green-800">Messages Kept</div>
                </div>
            </div>
        `;
    }
    
    updateUI() {
        // Update button states based on current state
        this.collectBtn.disabled = !this.isAuthenticated || this.isCollecting;
        
        const hasCollectedDomains = Object.keys(this.domains).length > 0;
        const hasSelection = this.selectedDomains.size > 0;
        
        this.previewBtn.disabled = !hasCollectedDomains || !hasSelection || this.isCleaning;
        this.cleanupBtn.disabled = !hasCollectedDomains || !hasSelection || this.isCleaning;
    }
    
    logMessage(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const colors = {
            info: 'text-blue-600',
            success: 'text-green-600',
            warning: 'text-yellow-600',
            error: 'text-red-600'
        };
        
        const logEntry = document.createElement('div');
        logEntry.className = `text-sm ${colors[type]}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        this.logContainer.appendChild(logEntry);
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.gmailCleanerApp = new GmailCleanerApp();
});