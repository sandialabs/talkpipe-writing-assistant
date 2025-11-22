class WritingAssistant {
    constructor() {
        this.sections = [];
        this.currentSectionIndex = -1;
        this.documentText = '';
        this.documentTitle = '';
        this.currentFilename = null;
        this.autoSaveTimer = null;
        this.lastSaveTime = null;
        this.isPerformingSyncSave = false;
        // Authentication is handled via JWT tokens in localStorage (set by login page)
        // Initialize with saved defaults from localStorage or hardcoded fallbacks
        this.documentMetadata = {
            writing_style: localStorage.getItem('writingStyle') || 'formal',
            target_audience: localStorage.getItem('targetAudience') || '',
            tone: localStorage.getItem('tone') || 'neutral',
            background_context: localStorage.getItem('backgroundContext') || '',
            generation_directive: localStorage.getItem('generationDirective') || '',
            word_limit: localStorage.getItem('wordLimit') || null,
            source: localStorage.getItem('generationSource') || '',
            model: localStorage.getItem('generationModel') || ''
        };

        // Environment variables
        this.environmentVariables = this.loadEnvironmentVariables();

        // Undo/Redo system
        this.undoStack = [];
        this.redoStack = [];
        this.maxUndoSteps = 100;
        this.lastUndoState = null;
        this.undoTimer = null;
        this.undoDelay = 1000; // 1 second delay before saving undo state
        this.isUndoRedoOperation = false;

        // Debounce timer for parseSections (performance optimization)
        this.parseSectionsTimer = null;
        this.parseSectionsDelay = 150; // 150ms debounce delay

        this.init();
    }

    async init() {
        try {
            console.log('WritingAssistant: Starting initialization...');

            console.log('WritingAssistant: Setting up event listeners...');
            this.setupEventListeners();

            console.log('WritingAssistant: Loading metadata...');
            this.loadMetadata();

            console.log('WritingAssistant: Loading server config...');
            // Check server configuration
            await this.loadServerConfig();

            console.log('WritingAssistant: Loading user preferences...');
            // Load user preferences from server (per-user defaults)
            await this.loadUserPreferences();

            console.log('WritingAssistant: Applying saved AI settings...');
            // Apply saved AI settings to the initial document
            await this.applySavedAISettings();

            console.log('WritingAssistant: Loading existing document...');
            this.loadExistingDocument();

            console.log('WritingAssistant: Setting up modals...');
            this.setupModals();

            console.log('WritingAssistant: Updating filename display...');
            // Initialize filename display
            this.updateFilenameDisplay();

            console.log('WritingAssistant: Setting up auto-save...');
            // Setup auto-save and page exit handlers
            this.setupAutoSave();
            this.setupPageExitHandler();

            console.log('WritingAssistant: Initializing dark mode...');
            // Initialize dark mode
            this.initializeDarkMode();

            console.log('WritingAssistant: Initialization complete!');
        } catch (error) {
            console.error('WritingAssistant: Initialization failed:', error);
            throw error;
        }
    }

    // Helper method to get fetch options with authentication headers
    getAuthFetchOptions(options = {}) {
        const token = window.getAuthToken ? window.getAuthToken() : localStorage.getItem('access_token');
        if (token) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${token}`
            };
        }
        return options;
    }

    // Helper method for authenticated GET requests
    async authFetch(url, options = {}) {
        return fetch(url, this.getAuthFetchOptions(options));
    }

    async loadServerConfig() {
        try {
            const response = await this.authFetch('/config');
            const config = await response.json();
            this.allowCustomEnvVars = config.allow_custom_env_vars;
            console.log('Server config loaded:', config);
        } catch (error) {
            console.error('Error loading server config:', error);
            // Default to allowing env vars if we can't reach the server
            this.allowCustomEnvVars = true;
        }
    }

    setupEventListeners() {
        const titleInput = document.getElementById('document-title');
        const documentTextarea = document.getElementById('document-text');
        const useSuggestionBtn = document.getElementById('use-suggestion-btn');

        // Document title
        titleInput.addEventListener('input', () => this.handleTitleChange());

        // Document text editing and cursor tracking
        documentTextarea.addEventListener('input', () => this.handleDocumentTextChange());
        documentTextarea.addEventListener('click', () => this.handleCursorChange());
        // Only handle cursor change for navigation keys (not regular typing)
        documentTextarea.addEventListener('keyup', (e) => {
            const navigationKeys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
                                    'Home', 'End', 'PageUp', 'PageDown'];
            if (navigationKeys.includes(e.key)) {
                this.handleCursorChange();
            }
        });

        // Mode button controls (Ideas, Rewrite, Improve, Proofread)
        // Prevent buttons from stealing focus from the editor
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('mousedown', (e) => e.preventDefault());
            btn.addEventListener('click', () => {
                const mode = btn.getAttribute('data-mode');
                this.generateSuggestionForCurrentSection(mode);
            });
        });

        // Use suggestion button - also prevent focus steal
        useSuggestionBtn.addEventListener('mousedown', (e) => e.preventDefault());
        useSuggestionBtn.addEventListener('click', () => this.useSuggestion());

        // Initialize undo/redo system
        this.initializeUndoRedo();

        // Initialize hotkey system
        this.initializeHotkeys();

        // File menu dropdown
        document.getElementById('file-menu-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleFileMenu();
        });

        // Header controls (dropdown items)
        document.getElementById('new-document-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.showNewDocumentModal();
        });
        document.getElementById('save-document-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.saveDocumentToServer();
        });
        document.getElementById('save-as-document-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.showSaveAsModal();
        });
        document.getElementById('load-document-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.showLoadDocumentModal();
        });
        document.getElementById('import-document-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.importDocumentFromFile();
        });
        document.getElementById('export-document-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.exportDocumentToFile();
        });
        document.getElementById('create-snapshot-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.createSnapshot();
        });
        document.getElementById('revert-snapshot-btn').addEventListener('click', (e) => {
            e.preventDefault();
            this.hideFileMenu();
            this.showRevertSnapshotModal();
        });
        document.getElementById('file-input').addEventListener('change', (e) => this.handleFileImport(e));
        document.getElementById('copy-document-btn').addEventListener('click', () => this.copyDocumentToClipboard());
        // Editor copy button (if it exists)
        const editorCopyBtn = document.getElementById('copy-document-btn-editor');
        if (editorCopyBtn) {
            editorCopyBtn.addEventListener('click', () => this.copyDocumentToClipboard());
        }
        document.getElementById('settings-btn').addEventListener('click', () => this.showSettingsModal());

        // Close dropdown when clicking outside
        document.addEventListener('click', () => this.hideFileMenu());

        // Resize handle
        this.setupResizeHandle();

        // Dark mode toggle
        document.getElementById('dark-mode-toggle').addEventListener('click', () => this.toggleDarkMode());

        // Environment variables
        document.getElementById('add-env-var-btn').addEventListener('click', () => this.addEnvironmentVariableRow());
    }

    setupModals() {
        // Settings modal
        const settingsModal = document.getElementById('settings-modal');
        const closeSettingsBtn = document.getElementById('close-settings-modal');
        const saveToDocumentBtn = document.getElementById('save-to-document-btn');
        const saveAsDefaultBtn = document.getElementById('save-as-default-btn');
        const resetMetadataBtn = document.getElementById('reset-metadata-btn');
        const saveGenerationSettingsBtn = document.getElementById('save-generation-settings-btn');

        closeSettingsBtn?.addEventListener('click', () => this.hideSettingsModal());
        saveToDocumentBtn?.addEventListener('click', () => this.saveToDocument());
        saveAsDefaultBtn?.addEventListener('click', () => this.saveAsDefault());
        resetMetadataBtn?.addEventListener('click', () => this.resetMetadata());
        saveGenerationSettingsBtn?.addEventListener('click', () => this.saveGenerationSettings());

        // Settings tabs
        const settingsTabBtns = document.querySelectorAll('.settings-tab-btn');
        settingsTabBtns.forEach(btn => {
            btn.addEventListener('click', (e) => this.switchSettingsTab(e.target.dataset.settingsTab));
        });

        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) this.hideSettingsModal();
        });

        // Add Enter key handler for Settings modal
        settingsModal.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                // Don't trigger if we're in a textarea (allow normal line breaks)
                if (e.target.tagName === 'TEXTAREA') {
                    return;
                }
                e.preventDefault();
                // Save settings based on which tab is active
                const activeTab = document.querySelector('.settings-tab-content.active');
                if (activeTab && activeTab.id === 'metadata-settings') {
                    this.saveMetadata();
                } else if (activeTab && activeTab.id === 'generation-settings') {
                    this.saveGenerationSettings();
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.hideSettingsModal();
            }
        });

        // Load document modal
        const loadDocumentModal = document.getElementById('load-document-modal');
        const closeLoadModalBtn = document.getElementById('close-load-modal');
        const closeLoadModalFooterBtn = document.getElementById('close-load-modal-footer');
        const refreshDocumentsBtn = document.getElementById('refresh-documents-btn');

        closeLoadModalBtn.addEventListener('click', () => this.hideLoadDocumentModal());
        closeLoadModalFooterBtn.addEventListener('click', () => this.hideLoadDocumentModal());
        refreshDocumentsBtn.addEventListener('click', () => this.loadDocumentsList());

        loadDocumentModal.addEventListener('click', (e) => {
            if (e.target === loadDocumentModal) this.hideLoadDocumentModal();
        });

        // Add Enter key handler for Load Document modal
        loadDocumentModal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                this.hideLoadDocumentModal();
            }
        });

        // New document modal
        const newDocumentModal = document.getElementById('new-document-modal');
        const closeNewDocumentBtn = document.getElementById('close-new-document-modal');
        const cancelNewDocumentBtn = document.getElementById('cancel-new-document-btn');
        const createNewDocumentBtn = document.getElementById('create-new-document-btn');

        closeNewDocumentBtn.addEventListener('click', () => this.hideNewDocumentModal());
        cancelNewDocumentBtn.addEventListener('click', () => this.hideNewDocumentModal());
        createNewDocumentBtn.addEventListener('click', () => this.createNewDocument());

        newDocumentModal.addEventListener('click', (e) => {
            if (e.target === newDocumentModal) this.hideNewDocumentModal();
        });

        // Add Enter key handler for New Document modal
        newDocumentModal.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                // Don't trigger if we're in the textarea (allow normal line breaks)
                if (e.target.tagName === 'TEXTAREA') {
                    return;
                }
                e.preventDefault();
                this.createNewDocument();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.hideNewDocumentModal();
            }
        });

        // Save As modal
        const saveAsModal = document.getElementById('save-as-modal');
        const closeSaveAsBtn = document.getElementById('close-save-as-modal');
        const cancelSaveAsBtn = document.getElementById('cancel-save-as-btn');
        const confirmSaveAsBtn = document.getElementById('confirm-save-as-btn');

        closeSaveAsBtn.addEventListener('click', () => this.hideSaveAsModal());
        cancelSaveAsBtn.addEventListener('click', () => this.hideSaveAsModal());
        confirmSaveAsBtn.addEventListener('click', () => this.saveDocumentAs());

        saveAsModal.addEventListener('click', (e) => {
            if (e.target === saveAsModal) this.hideSaveAsModal();
        });

        // Add Enter key handler for Save As modal
        saveAsModal.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.saveDocumentAs();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.hideSaveAsModal();
            }
        });

        // Revert to Snapshot modal
        const revertSnapshotModal = document.getElementById('revert-snapshot-modal');
        const closeRevertSnapshotBtn = document.getElementById('close-revert-snapshot-modal');
        const closeRevertSnapshotFooterBtn = document.getElementById('close-revert-snapshot-footer');

        closeRevertSnapshotBtn.addEventListener('click', () => this.hideRevertSnapshotModal());
        closeRevertSnapshotFooterBtn.addEventListener('click', () => this.hideRevertSnapshotModal());

        revertSnapshotModal.addEventListener('click', (e) => {
            if (e.target === revertSnapshotModal) this.hideRevertSnapshotModal();
        });

        // Add Escape key handler for Revert to Snapshot modal
        revertSnapshotModal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                this.hideRevertSnapshotModal();
            }
        });
    }

    setupResizeHandle() {
        const resizeHandle = document.getElementById('resize-handle');
        const editorMain = document.querySelector('.editor-main');
        let isResizing = false;
        let startX = 0;
        let startWidths = [];

        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;

            // Get current computed styles
            const computedStyle = window.getComputedStyle(editorMain);
            const currentColumns = computedStyle.gridTemplateColumns.split(' ');

            // Parse current column widths
            startWidths = currentColumns.map(width => {
                if (width.endsWith('fr')) {
                    return parseFloat(width);
                } else if (width.endsWith('px')) {
                    return parseFloat(width);
                } else {
                    return 0;
                }
            });

            // Add visual feedback
            resizeHandle.classList.add('dragging');
            document.body.classList.add('no-select');

            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            const deltaX = e.clientX - startX;
            const containerWidth = editorMain.offsetWidth;

            // Convert pixel movement to fraction change
            const fractionChange = (deltaX / containerWidth) * (startWidths[0] + startWidths[2]);

            // Calculate new fractions
            let leftFraction = startWidths[0] + fractionChange;
            let rightFraction = startWidths[2] - fractionChange;

            // Enforce minimum sizes (0.5fr minimum for each side)
            leftFraction = Math.max(0.5, Math.min(leftFraction, startWidths[0] + startWidths[2] - 0.5));
            rightFraction = Math.max(0.5, Math.min(rightFraction, startWidths[0] + startWidths[2] - 0.5));

            // Ensure they add up to the original total
            const total = leftFraction + rightFraction;
            const originalTotal = startWidths[0] + startWidths[2];
            if (total !== originalTotal) {
                const ratio = originalTotal / total;
                leftFraction *= ratio;
                rightFraction *= ratio;
            }

            // Update grid template
            editorMain.style.gridTemplateColumns = `${leftFraction}fr 4px ${rightFraction}fr`;

            e.preventDefault();
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                resizeHandle.classList.remove('dragging');
                document.body.classList.remove('no-select');
            }
        });

        // Handle escape key to cancel resize
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isResizing) {
                isResizing = false;
                resizeHandle.classList.remove('dragging');
                document.body.classList.remove('no-select');

                // Reset to original columns
                editorMain.style.gridTemplateColumns = `${startWidths[0]}fr 4px ${startWidths[2]}fr`;
            }
        });
    }

    handleDocumentTextChange() {
        const textarea = document.getElementById('document-text');
        this.documentText = textarea.value;

        // Save undo state if this wasn't an undo/redo operation
        if (!this.isUndoRedoOperation) {
            this.scheduleUndoStateSave();
        }

        // Debounce parseSections to avoid expensive operations on every keystroke
        // Note: handleCursorChange is called after parseSections completes, not here,
        // to avoid UI flickering due to stale section positions
        this.scheduleParseSections();
    }

    scheduleParseSections() {
        // Clear existing timer
        if (this.parseSectionsTimer) {
            clearTimeout(this.parseSectionsTimer);
        }

        // Schedule parseSections after delay
        this.parseSectionsTimer = setTimeout(() => {
            this.parseSections();
        }, this.parseSectionsDelay);
    }

    handleTitleChange() {
        const titleInput = document.getElementById('document-title');
        this.documentTitle = titleInput.value;
        // All state managed in browser only
    }

    // Calculate text similarity ratio between two strings (0.0 to 1.0)
    // Uses a simple character-based approach for performance
    calculateTextSimilarity(text1, text2) {
        if (!text1 || !text2) return 0;
        if (text1 === text2) return 1;

        const str1 = text1.trim().toLowerCase();
        const str2 = text2.trim().toLowerCase();

        if (str1 === str2) return 1;
        if (str1.length === 0 && str2.length === 0) return 1;
        if (str1.length === 0 || str2.length === 0) return 0;

        // Cheap length pre-filter: if one string is more than 2x the length of
        // the other, similarity can't exceed 0.5 (our threshold), so skip Levenshtein
        const minLen = Math.min(str1.length, str2.length);
        const maxLen = Math.max(str1.length, str2.length);
        if (maxLen > 2 * minLen) {
            return minLen / maxLen; // Return upper bound (actual similarity is lower)
        }

        // Use Levenshtein distance for accurate similarity calculation
        const distance = this.levenshteinDistance(str1, str2);
        const similarity = 1 - (distance / maxLen);

        return similarity;
    }

    // Calculate Levenshtein distance between two strings
    levenshteinDistance(str1, str2) {
        const len1 = str1.length;
        const len2 = str2.length;

        // Create a matrix to store distances
        const matrix = Array(len1 + 1).fill(null).map(() => Array(len2 + 1).fill(0));

        // Initialize first row and column
        for (let i = 0; i <= len1; i++) matrix[i][0] = i;
        for (let j = 0; j <= len2; j++) matrix[0][j] = j;

        // Calculate distances
        for (let i = 1; i <= len1; i++) {
            for (let j = 1; j <= len2; j++) {
                const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
                matrix[i][j] = Math.min(
                    matrix[i - 1][j] + 1,      // deletion
                    matrix[i][j - 1] + 1,      // insertion
                    matrix[i - 1][j - 1] + cost // substitution
                );
            }
        }

        return matrix[len1][len2];
    }

    parseSections() {
        const text = this.documentText;
        const oldSections = [...this.sections]; // Save previous sections
        this.sections = [];

        if (!text.trim()) {
            this.updateSectionInfo();
            return;
        }

        // Track which old sections have been matched to prevent reusing suggestions
        const matchedOldSectionIndices = new Set();

        // Split by double newlines (blank lines)
        const rawSections = text.split(/\n\s*\n/);
        let currentPos = 0;

        rawSections.forEach((sectionText, index) => {
            const trimmed = sectionText.trim();
            if (trimmed) {
                // Find the actual position of this section in the text
                const sectionStart = text.indexOf(sectionText, currentPos);
                const sectionEnd = sectionStart + sectionText.length;
                currentPos = sectionEnd;

                // Create new section object
                const newSection = {
                    id: `section-${index}`,
                    text: trimmed,
                    startPos: sectionStart,
                    endPos: sectionEnd,
                    generated_text: ''
                };

                // Try to preserve generated_text from previous sections
                // Optimization: Try index-based matching first (most common case during typing)
                let matchingOldSectionIndex = -1;

                // Step 1: Try matching at the same index first (fast path for normal editing)
                if (index < oldSections.length &&
                    !matchedOldSectionIndices.has(index) &&
                    oldSections[index].generated_text) {
                    const oldSection = oldSections[index];
                    const originalText = oldSection.original_text || oldSection.text;
                    const similarity = this.calculateTextSimilarity(originalText, trimmed);
                    if (similarity > 0.5) {
                        matchingOldSectionIndex = index;
                    }
                }

                // Step 2: Fall back to searching all old sections only if index-based match failed
                if (matchingOldSectionIndex === -1) {
                    matchingOldSectionIndex = oldSections.findIndex((oldSection, oldIndex) => {
                        // Skip the index we already checked
                        if (oldIndex === index) {
                            return false;
                        }
                        // Skip sections that have already been matched to another new section
                        if (matchedOldSectionIndices.has(oldIndex)) {
                            return false;
                        }
                        // Skip sections without generated text
                        if (!oldSection.generated_text) {
                            return false;
                        }
                        // Calculate similarity between ORIGINAL text and new text
                        const originalText = oldSection.original_text || oldSection.text;
                        const similarity = this.calculateTextSimilarity(originalText, trimmed);
                        return similarity > 0.5;
                    });
                }

                if (matchingOldSectionIndex !== -1) {
                    const matchingOldSection = oldSections[matchingOldSectionIndex];
                    newSection.generated_text = matchingOldSection.generated_text;
                    // Also preserve the original text so we continue comparing against it
                    newSection.original_text = matchingOldSection.original_text || matchingOldSection.text;
                    // Mark this old section as matched so it won't be reused for other new sections
                    matchedOldSectionIndices.add(matchingOldSectionIndex);
                }

                this.sections.push(newSection);
            }
        });

        this.updateSectionInfo();
        // Update cursor/suggestion panel after sections are rebuilt
        this.handleCursorChange();
    }

    handleCursorChange() {
        const textarea = document.getElementById('document-text');
        const cursorPos = textarea.selectionStart;

        // Find which section the cursor is in
        let newSectionIndex = -1;
        for (let i = 0; i < this.sections.length; i++) {
            const section = this.sections[i];
            if (cursorPos >= section.startPos && cursorPos <= section.endPos) {
                newSectionIndex = i;
                break;
            }
        }

        if (newSectionIndex !== this.currentSectionIndex) {
            this.currentSectionIndex = newSectionIndex;
            this.updateSuggestionPanel();
        }
    }

    updateSectionInfo() {
        const infoElement = document.getElementById('current-section-info');
        if (this.sections.length === 0) {
            infoElement.textContent = 'No sections detected';
        } else {
            infoElement.textContent = `${this.sections.length} section${this.sections.length === 1 ? '' : 's'} detected`;
        }
    }

    updateSuggestionPanel() {
        const suggestionText = document.getElementById('suggestion-text');
        const modeButtons = document.querySelectorAll('.mode-btn');
        const useSuggestionBtn = document.getElementById('use-suggestion-btn');
        const infoElement = document.getElementById('current-section-info');

        if (this.currentSectionIndex === -1 || this.sections.length === 0) {
            suggestionText.textContent = 'Position your cursor in a section above to see AI suggestions for that section.';
            modeButtons.forEach(btn => btn.disabled = true);
            useSuggestionBtn.disabled = true;
            infoElement.textContent = 'No section selected';
        } else {
            const currentSection = this.sections[this.currentSectionIndex];
            const sectionNum = this.currentSectionIndex + 1;
            infoElement.textContent = `Section ${sectionNum} of ${this.sections.length} selected`;

            // Mode buttons are always enabled when a section is selected
            modeButtons.forEach(btn => btn.disabled = false);

            if (currentSection.generated_text) {
                suggestionText.textContent = currentSection.generated_text;
                useSuggestionBtn.disabled = false;
            } else {
                suggestionText.textContent = 'Click a mode button below to get AI suggestions for this section.';
                useSuggestionBtn.disabled = true;
            }
        }
    }

    async generateSuggestionForCurrentSection(mode = 'ideas') {
        if (this.currentSectionIndex === -1 || this.sections.length === 0) {
            this.showMessage('Please position your cursor in a section first', 'error');
            return;
        }

        const currentSection = this.sections[this.currentSectionIndex];
        const suggestionText = document.getElementById('suggestion-text');
        const modeButtons = document.querySelectorAll('.mode-btn');
        const activeButton = document.querySelector(`.mode-btn[data-mode="${mode}"]`);

        // Show loading state
        modeButtons.forEach(btn => btn.disabled = true);
        if (activeButton) {
            activeButton.classList.add('generating');
        }
        suggestionText.textContent = 'Generating AI suggestion...';

        try {
            // Get context (collect from multiple sections to reach 2000 characters)
            let prevContext = '';
            let nextContext = '';

            // Collect previous context (going backwards from current section)
            for (let i = this.currentSectionIndex - 1; i >= 0 && prevContext.length < 2000; i--) {
                const sectionText = this.sections[i].text;
                prevContext = sectionText + (prevContext ? '\n\n' + prevContext : '');
            }

            // Collect next context (going forwards from current section)
            for (let i = this.currentSectionIndex + 1; i < this.sections.length && nextContext.length < 2000; i++) {
                const sectionText = this.sections[i].text;
                nextContext = nextContext + (nextContext ? '\n\n' : '') + sectionText;
            }

            const title = document.getElementById('document-title').value || '';

            const formData = new FormData();
            formData.append('user_text', currentSection.text);
            formData.append('title', title);
            formData.append('prev_paragraph', prevContext);
            formData.append('next_paragraph', nextContext);
            formData.append('generation_mode', mode);

            // Send metadata with each request - read current values from form fields
            formData.append('writing_style', document.getElementById('writing-style')?.value || this.documentMetadata.writing_style || 'formal');
            formData.append('target_audience', document.getElementById('target-audience')?.value || this.documentMetadata.target_audience || '');
            formData.append('tone', document.getElementById('tone')?.value || this.documentMetadata.tone || 'neutral');
            formData.append('background_context', document.getElementById('background-context')?.value || this.documentMetadata.background_context || '');
            formData.append('generation_directive', document.getElementById('generation-directive')?.value || this.documentMetadata.generation_directive || '');
            // Only append word_limit if it has a value (to avoid sending empty string for Optional[int])
            const wordLimitValue = document.getElementById('word-limit')?.value || this.documentMetadata.word_limit;
            if (wordLimitValue) {
                formData.append('word_limit', wordLimitValue);
            }
            formData.append('source', document.getElementById('ai-source')?.value || this.documentMetadata.source || '');
            formData.append('model', document.getElementById('ai-model')?.value || this.documentMetadata.model || '');

            // Send environment variables as JSON (only if allowed by server)
            if (this.allowCustomEnvVars) {
                formData.append('environment_variables', JSON.stringify(this.environmentVariables));
            } else {
                formData.append('environment_variables', '{}');
            }

            const response = await this.authFetch('/generate-text', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.generated_text) {
                currentSection.generated_text = result.generated_text;
                // Store the original text that the suggestion was generated for
                currentSection.original_text = currentSection.text;
                this.updateSuggestionPanel();
                this.showMessage('AI suggestion generated successfully!', 'success');
            } else {
                throw new Error('No generated text received');
            }

        } catch (error) {
            console.error('Error generating suggestion:', error);
            this.showMessage('Error generating suggestion. Please try again.', 'error');
            suggestionText.textContent = 'Error generating suggestion. Please try again.';
        } finally {
            // Re-enable all mode buttons
            modeButtons.forEach(btn => btn.disabled = false);
            if (activeButton) {
                activeButton.classList.remove('generating');
            }
        }
    }


    useSuggestion() {
        if (this.currentSectionIndex === -1 || this.sections.length === 0) {
            return;
        }

        const currentSection = this.sections[this.currentSectionIndex];
        if (!currentSection.generated_text) {
            this.showMessage('No suggestion to use. Generate one first.', 'error');
            return;
        }

        const textarea = document.getElementById('document-text');

        // Save undo state before making changes
        this.saveUndoState();

        const beforeSection = this.documentText.substring(0, currentSection.startPos);
        const afterSection = this.documentText.substring(currentSection.endPos);

        // Clean the generated text to prevent extra blank lines
        const cleanGeneratedText = currentSection.generated_text.trim();

        // Calculate new cursor position (end of the replaced section)
        const newCursorPos = beforeSection.length + cleanGeneratedText.length;

        // Replace the current section with the suggestion
        const newText = beforeSection + cleanGeneratedText + afterSection;
        
        // Mark this as a programmatic change to avoid creating another undo state
        this.isUndoRedoOperation = true;
        textarea.value = newText;
        this.isUndoRedoOperation = false;

        // Set cursor position to end of the replaced section
        textarea.focus();
        textarea.setSelectionRange(newCursorPos, newCursorPos);

        // Update internal state - this will preserve suggestions for other sections
        this.documentText = newText;
        this.parseSections();

        // Update the current section index to match the new structure
        // Since we just replaced text, we want to stay in the same logical section
        for (let i = 0; i < this.sections.length; i++) {
            if (newCursorPos >= this.sections[i].startPos && newCursorPos <= this.sections[i].endPos) {
                this.currentSectionIndex = i;
                break;
            }
        }

        this.updateSuggestionPanel();
        this.showMessage('Suggestion applied successfully!', 'success');
    }

    async loadExistingDocument() {
        try {
            // Initialize with empty document since all state is in browser
            const titleInput = document.getElementById('document-title');
            const textarea = document.getElementById('document-text');

            this.documentTitle = '';
            this.documentText = '';

            titleInput.value = '';
            textarea.value = '';

            this.parseSections();
            this.handleCursorChange();
            
            // Reset undo history for new document
            this.clearUndoHistory();
        } catch (error) {
            console.error('Error initializing document:', error);
        }
    }

    // updateTitle method removed - all state managed in browser

    // Modal management methods
    showSettingsModal() {
        const modal = document.getElementById('settings-modal');
        modal.classList.add('show');
        // Always load the current document's settings into the form when modal opens
        // This ensures the form displays the current state accurately
        this.loadCurrentDocumentToSettingsForm();

        // Show/hide environment variables section based on server config
        const envVarsSection = document.querySelector('.settings-section h4');
        if (envVarsSection && envVarsSection.textContent === 'Environment Variables') {
            const envVarsSectionParent = envVarsSection.parentElement;
            if (this.allowCustomEnvVars) {
                envVarsSectionParent.style.display = '';
                // Render environment variables
                this.renderEnvironmentVariables();
            } else {
                envVarsSectionParent.style.display = 'none';
            }
        }
    }

    hideSettingsModal() {
        const modal = document.getElementById('settings-modal');
        modal.classList.remove('show');
    }

    showDocumentsModal() {
        const modal = document.getElementById('documents-modal');
        modal.classList.add('show');
        this.loadDocumentsList();
    }

    hideDocumentsModal() {
        const modal = document.getElementById('documents-modal');
        modal.classList.remove('show');
    }

    showNewDocumentModal() {
        const modal = document.getElementById('new-document-modal');
        modal.classList.add('show');
        document.getElementById('new-document-title').value = '';
        document.getElementById('new-document-outline').value = '';
        document.getElementById('new-document-title').focus();
    }

    hideNewDocumentModal() {
        const modal = document.getElementById('new-document-modal');
        modal.classList.remove('show');
    }

    showSaveAsModal() {
        const modal = document.getElementById('save-as-modal');
        modal.classList.add('show');
        document.getElementById('save-as-filename').value = this.documentTitle || '';
        document.getElementById('save-as-filename').focus();
    }

    hideSaveAsModal() {
        const modal = document.getElementById('save-as-modal');
        modal.classList.remove('show');
    }

    showRevertSnapshotModal() {
        if (!this.currentFilename) {
            this.showMessage('Please save the document first before reverting to a snapshot', 'info');
            return;
        }

        const modal = document.getElementById('revert-snapshot-modal');
        modal.classList.add('show');
        this.loadSnapshotsList();
    }

    hideRevertSnapshotModal() {
        const modal = document.getElementById('revert-snapshot-modal');
        modal.classList.remove('show');
    }

    async loadSnapshotsList() {
        const listContainer = document.getElementById('snapshots-list');

        try {
            const response = await this.authFetch(`/documents/snapshots/${this.currentFilename}`);
            const result = await response.json();

            if (result.status === 'success' && result.snapshots.length > 0) {
                listContainer.innerHTML = result.snapshots.map(snapshot => {
                    const date = new Date(snapshot.modified);
                    const dateStr = date.toLocaleString();
                    return `
                        <div class="document-item">
                            <div class="document-info">
                                <div class="document-name">${snapshot.filename}</div>
                                <div class="document-meta">Modified: ${dateStr} | Size: ${(snapshot.size / 1024).toFixed(2)} KB</div>
                            </div>
                            <button class="btn btn-primary btn-small revert-snapshot-item" data-snapshot="${snapshot.filename}">
                                Revert to This
                            </button>
                        </div>
                    `;
                }).join('');

                // Add event listeners to revert buttons
                document.querySelectorAll('.revert-snapshot-item').forEach(btn => {
                    btn.addEventListener('click', () => this.revertToSnapshot(btn.dataset.snapshot));
                });
            } else {
                listContainer.innerHTML = '<p class="no-documents">No snapshots available for this document.</p>';
            }
        } catch (error) {
            console.error('Error loading snapshots:', error);
            listContainer.innerHTML = '<p class="error">Error loading snapshots</p>';
        }
    }

    async revertToSnapshot(snapshotFilename) {
        try {
            const response = await this.authFetch(`/documents/snapshot/load/${snapshotFilename}`);
            const result = await response.json();

            if (result.status === 'success') {
                // Load the snapshot data into the current document
                const doc = result.document;

                // Keep the current filename (don't change it)
                const currentFilename = this.currentFilename;

                // Load the document content
                this.documentTitle = doc.title || '';
                this.documentText = doc.content || '';
                document.getElementById('document-title').value = this.documentTitle;
                document.getElementById('document-text').value = this.documentText;

                // Load metadata if present
                if (doc.metadata) {
                    document.getElementById('writing-style').value = doc.metadata.writing_style || 'formal';
                    document.getElementById('target-audience').value = doc.metadata.target_audience || '';
                    document.getElementById('tone').value = doc.metadata.tone || 'neutral';
                    document.getElementById('background-context').value = doc.metadata.background_context || '';
                    document.getElementById('generation-directive').value = doc.metadata.generation_directive || '';
                    document.getElementById('word-limit').value = doc.metadata.word_limit || '';
                    document.getElementById('ai-source').value = doc.metadata.source || '';
                    document.getElementById('ai-model').value = doc.metadata.model || '';
                }

                // Restore the current filename
                this.currentFilename = currentFilename;

                // Update sections and UI
                this.handleDocumentTextChange();
                this.hideRevertSnapshotModal();
                this.showMessage(`Reverted to snapshot: ${snapshotFilename}`, 'success');
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error reverting to snapshot:', error);
            this.showMessage('Error reverting to snapshot', 'error');
        }
    }

    switchSettingsTab(tabName) {
        const tabButtons = document.querySelectorAll('.settings-tab-btn');
        const tabContents = document.querySelectorAll('.settings-tab-content');

        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));

        document.querySelector(`[data-settings-tab="${tabName}"]`).classList.add('active');
        document.getElementById(`${tabName}-settings`).classList.add('active');
    }

    async loadMetadata() {
        try {
            // Load AI settings from localStorage
            const savedSource = localStorage.getItem('generationSource') || '';
            const savedModel = localStorage.getItem('generationModel') || '';

            const sourceElement = document.getElementById('ai-source');
            const modelElement = document.getElementById('ai-model');
            if (sourceElement) sourceElement.value = savedSource;
            if (modelElement) modelElement.value = savedModel;

            // Load writing settings from localStorage or use defaults
            const writingStyle = localStorage.getItem('writingStyle') || 'formal';
            const targetAudience = localStorage.getItem('targetAudience') || '';
            const tone = localStorage.getItem('tone') || 'neutral';
            const backgroundContext = localStorage.getItem('backgroundContext') || '';
            const generationDirective = localStorage.getItem('generationDirective') || '';
            const wordLimit = localStorage.getItem('wordLimit') || '';

            document.getElementById('writing-style').value = writingStyle;
            document.getElementById('target-audience').value = targetAudience;
            document.getElementById('tone').value = tone;
            document.getElementById('background-context').value = backgroundContext;
            document.getElementById('generation-directive').value = generationDirective;
            document.getElementById('word-limit').value = wordLimit;

            // Initialize documentMetadata with current settings
            this.documentMetadata = {
                writing_style: writingStyle,
                target_audience: targetAudience,
                tone: tone,
                background_context: backgroundContext,
                generation_directive: generationDirective,
                word_limit: wordLimit || null,
                source: savedSource,
                model: savedModel
            };
        } catch (error) {
            console.error('Error loading metadata:', error);
        }
    }

    async saveToDocument() {
        const metadata = {
            source: document.getElementById('ai-source').value,
            model: document.getElementById('ai-model').value,
            writing_style: document.getElementById('writing-style').value,
            target_audience: document.getElementById('target-audience').value,
            tone: document.getElementById('tone').value,
            background_context: document.getElementById('background-context').value,
            generation_directive: document.getElementById('generation-directive').value,
            word_limit: document.getElementById('word-limit').value || null
        };

        // Update the document's metadata only
        this.documentMetadata = {
            writing_style: metadata.writing_style,
            target_audience: metadata.target_audience,
            tone: metadata.tone,
            background_context: metadata.background_context,
            generation_directive: metadata.generation_directive,
            word_limit: metadata.word_limit,
            source: metadata.source,
            model: metadata.model
        };

        // Settings saved to document (no server call needed - sent with each generation request)
        this.showMessage('Settings saved to document!', 'success');
    }

    async saveAsDefault() {
        const preferences = {
            source: document.getElementById('ai-source').value,
            model: document.getElementById('ai-model').value,
            writing_style: document.getElementById('writing-style').value,
            target_audience: document.getElementById('target-audience').value,
            tone: document.getElementById('tone').value,
            background_context: document.getElementById('background-context').value,
            generation_directive: document.getElementById('generation-directive').value,
            word_limit: document.getElementById('word-limit').value || null,
            environment_variables: this.environmentVariables || {}
        };

        try {
            // Save to server (per-user preferences)
            const response = await this.authFetch('/user/preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ preferences })
            });

            const result = await response.json();

            if (result.status === 'success') {
                // Also update localStorage as cache
                localStorage.setItem('generationSource', preferences.source);
                localStorage.setItem('generationModel', preferences.model);
                localStorage.setItem('writingStyle', preferences.writing_style);
                localStorage.setItem('targetAudience', preferences.target_audience);
                localStorage.setItem('tone', preferences.tone);
                localStorage.setItem('backgroundContext', preferences.background_context);
                localStorage.setItem('generationDirective', preferences.generation_directive);
                localStorage.setItem('wordLimit', preferences.word_limit || '');
                localStorage.setItem('environmentVariables', JSON.stringify(preferences.environment_variables));

                this.showMessage('Settings saved as default for your account!', 'success');
            } else {
                this.showMessage('Error saving preferences: ' + result.message, 'error');
            }
        } catch (error) {
            console.error('Error saving preferences:', error);
            this.showMessage('Error saving preferences', 'error');
        }
    }

    async loadUserPreferences() {
        try {
            const response = await this.authFetch('/user/preferences');
            const result = await response.json();

            if (result.status === 'success') {
                const prefs = result.preferences || {};

                // Always set localStorage with either user preferences or defaults
                // This ensures we don't keep the previous user's settings
                localStorage.setItem('generationSource', prefs.source || '');
                localStorage.setItem('generationModel', prefs.model || '');
                localStorage.setItem('writingStyle', prefs.writing_style || 'formal');
                localStorage.setItem('targetAudience', prefs.target_audience || '');
                localStorage.setItem('tone', prefs.tone || 'neutral');
                localStorage.setItem('backgroundContext', prefs.background_context || '');
                localStorage.setItem('generationDirective', prefs.generation_directive || '');
                localStorage.setItem('wordLimit', prefs.word_limit || '');

                // Load environment variables (default to empty object if user hasn't saved any)
                const envVars = prefs.environment_variables || {};
                localStorage.setItem('environmentVariables', JSON.stringify(envVars));
                this.environmentVariables = envVars;

                // Reload metadata to apply server preferences
                this.loadMetadata();

                console.log('User preferences loaded from server');
            }
        } catch (error) {
            console.error('Error loading user preferences:', error);
            // On error, reset to defaults to avoid keeping previous user's settings
            localStorage.setItem('generationSource', '');
            localStorage.setItem('generationModel', '');
            localStorage.setItem('writingStyle', 'formal');
            localStorage.setItem('targetAudience', '');
            localStorage.setItem('tone', 'neutral');
            localStorage.setItem('backgroundContext', '');
            localStorage.setItem('generationDirective', '');
            localStorage.setItem('wordLimit', '');
            localStorage.setItem('environmentVariables', '{}');
            this.environmentVariables = {};
            this.loadMetadata();
        }
    }

    // Legacy method for backward compatibility
    async saveMetadata() {
        // Default to saving to document only
        await this.saveToDocument();
    }

    async resetMetadata() {
        // Load saved defaults from localStorage into the form
        const savedSource = localStorage.getItem('generationSource') || '';
        const savedModel = localStorage.getItem('generationModel') || '';
        const savedWritingStyle = localStorage.getItem('writingStyle') || 'formal';
        const savedTargetAudience = localStorage.getItem('targetAudience') || '';
        const savedTone = localStorage.getItem('tone') || 'neutral';
        const savedBackgroundContext = localStorage.getItem('backgroundContext') || '';
        const savedGenerationDirective = localStorage.getItem('generationDirective') || '';
        const savedWordLimit = localStorage.getItem('wordLimit') || '';

        document.getElementById('ai-source').value = savedSource;
        document.getElementById('ai-model').value = savedModel;
        document.getElementById('writing-style').value = savedWritingStyle;
        document.getElementById('target-audience').value = savedTargetAudience;
        document.getElementById('tone').value = savedTone;
        document.getElementById('background-context').value = savedBackgroundContext;
        document.getElementById('generation-directive').value = savedGenerationDirective;
        document.getElementById('word-limit').value = savedWordLimit;

        this.showMessage('Form reset to saved defaults!', 'success');
    }

    async saveGenerationSettings() {
        const source = document.getElementById('ai-source').value;
        const model = document.getElementById('ai-model').value;

        // Save environment variables first (updates this.environmentVariables)
        this.saveEnvironmentVariables();

        // Save hotkey settings
        this.saveHotkeySettings();

        // Get current metadata settings from localStorage
        const writingStyle = localStorage.getItem('writingStyle') || 'formal';
        const targetAudience = localStorage.getItem('targetAudience') || '';
        const tone = localStorage.getItem('tone') || 'neutral';
        const backgroundContext = localStorage.getItem('backgroundContext') || '';
        const generationDirective = localStorage.getItem('generationDirective') || '';
        const wordLimit = localStorage.getItem('wordLimit') || null;

        const preferences = {
            source: source,
            model: model,
            writing_style: writingStyle,
            target_audience: targetAudience,
            tone: tone,
            background_context: backgroundContext,
            generation_directive: generationDirective,
            word_limit: wordLimit,
            environment_variables: this.environmentVariables || {}
        };

        try {
            // Save to server (per-user preferences)
            const response = await this.authFetch('/user/preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ preferences })
            });

            const result = await response.json();

            if (result.status === 'success') {
                // Also update localStorage as cache
                localStorage.setItem('generationSource', source);
                localStorage.setItem('generationModel', model);

                // Update document metadata with current source and model
                this.documentMetadata.source = source;
                this.documentMetadata.model = model;

                this.showMessage('AI settings, environment variables, and hotkeys saved successfully!', 'success');
            } else {
                this.showMessage('Error saving settings: ' + result.message, 'error');
            }
        } catch (error) {
            console.error('Error saving generation settings:', error);
            this.showMessage('Error saving settings', 'error');
        }
    }

    applySavedAISettings() {
        // No server call needed - metadata is sent with each generation request
        // This method kept for compatibility but does nothing
    }

    loadCurrentDocumentToSettingsForm() {
        // Always merge document metadata with localStorage values
        // This ensures we show the most up-to-date settings
        const savedSource = localStorage.getItem('generationSource') || '';
        const savedModel = localStorage.getItem('generationModel') || '';
        const savedWritingStyle = localStorage.getItem('writingStyle') || 'formal';
        const savedTargetAudience = localStorage.getItem('targetAudience') || '';
        const savedTone = localStorage.getItem('tone') || 'neutral';
        const savedBackgroundContext = localStorage.getItem('backgroundContext') || '';
        const savedGenerationDirective = localStorage.getItem('generationDirective') || '';
        const savedWordLimit = localStorage.getItem('wordLimit') || '';

        // Use document metadata if available, otherwise use localStorage (saved defaults)
        const fields = [
            { id: 'writing-style', value: (this.documentMetadata?.writing_style || savedWritingStyle) },
            { id: 'target-audience', value: (this.documentMetadata?.target_audience || savedTargetAudience) },
            { id: 'tone', value: (this.documentMetadata?.tone || savedTone) },
            { id: 'background-context', value: (this.documentMetadata?.background_context || savedBackgroundContext) },
            { id: 'generation-directive', value: (this.documentMetadata?.generation_directive || savedGenerationDirective) },
            { id: 'word-limit', value: (this.documentMetadata?.word_limit || savedWordLimit) },
            { id: 'ai-source', value: (this.documentMetadata?.source || savedSource) },
            { id: 'ai-model', value: (this.documentMetadata?.model || savedModel) }
        ];

        fields.forEach(field => {
            const element = document.getElementById(field.id);
            if (element) {
                element.value = field.value;
                // Trigger change event to ensure UI updates
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });

        // Also load hotkey settings
        this.loadHotkeySettings();
    }

    restoreDocumentMetadata(documentData) {
        // Restore metadata from document if available
        if (documentData.metadata) {
            this.documentMetadata = {
                writing_style: documentData.metadata.writing_style || 'formal',
                target_audience: documentData.metadata.target_audience || '',
                tone: documentData.metadata.tone || 'neutral',
                background_context: documentData.metadata.background_context || '',
                generation_directive: documentData.metadata.generation_directive || '',
                word_limit: documentData.metadata.word_limit || null,
                source: documentData.metadata.source || '',
                model: documentData.metadata.model || ''
            };

            // Update the UI form fields AND the settings modal if it's open
            // Use setTimeout to ensure DOM updates are processed
            setTimeout(() => {
                this.loadCurrentDocumentToSettingsForm();
            }, 10);
        }
    }

    restoreSavedSections(savedSections) {
        // If no saved sections, nothing to restore
        if (!savedSections || !Array.isArray(savedSections)) {
            return;
        }

        // Match saved sections with current sections by text content
        // This handles cases where the text might have minor formatting changes
        for (let i = 0; i < this.sections.length && i < savedSections.length; i++) {
            const currentSection = this.sections[i];
            const savedSection = savedSections[i];

            // If the section text matches (approximately), restore the generated_text
            if (savedSection && savedSection.generated_text) {
                const currentText = currentSection.text;
                const savedText = savedSection.text || '';

                // Calculate similarity between current and saved section text
                const similarity = this.calculateTextSimilarity(currentText, savedText);

                // Keep suggestion if more than 50% of the text is the same
                if (similarity > 0.5) {
                    currentSection.generated_text = savedSection.generated_text;
                }
            }
        }
    }

    // Undo/Redo System
    initializeUndoRedo() {
        const textarea = document.getElementById('document-text');
        
        // Save initial state
        this.saveUndoState();
        
        // Handle keyboard shortcuts
        textarea.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                if (e.key === 'z' && !e.shiftKey) {
                    e.preventDefault();
                    this.undo();
                } else if ((e.key === 'y') || (e.key === 'z' && e.shiftKey)) {
                    e.preventDefault();
                    this.redo();
                }
            }
        });
        
        // Save undo state on focus loss (when user clicks away)
        textarea.addEventListener('blur', () => {
            this.saveUndoState();
        });
    }
    
    scheduleUndoStateSave() {
        // Clear existing timer
        if (this.undoTimer) {
            clearTimeout(this.undoTimer);
        }
        
        // Schedule save after delay
        this.undoTimer = setTimeout(() => {
            this.saveUndoState();
        }, this.undoDelay);
    }
    
    saveUndoState() {
        const textarea = document.getElementById('document-text');
        const currentState = {
            text: textarea.value,
            selectionStart: textarea.selectionStart,
            selectionEnd: textarea.selectionEnd,
            timestamp: Date.now()
        };
        
        // Don't save if the text hasn't changed
        if (this.lastUndoState && this.lastUndoState.text === currentState.text) {
            return;
        }
        
        // Add to undo stack
        this.undoStack.push(currentState);
        
        // Limit stack size
        if (this.undoStack.length > this.maxUndoSteps) {
            this.undoStack.shift();
        }
        
        // Clear redo stack when new state is saved
        this.redoStack = [];

        this.lastUndoState = currentState;
    }
    
undo() {
        if (this.undoStack.length < 2) {
            this.showMessage('Nothing to undo', 'info');
            return;
        }

        const textarea = document.getElementById('document-text');

        // Move current state to redo stack
        const currentState = {
            text: textarea.value,
            selectionStart: textarea.selectionStart,
            selectionEnd: textarea.selectionEnd,
            timestamp: Date.now()
        };
        this.redoStack.push(currentState);

        // Remove current state from undo stack
        this.undoStack.pop();

        // Get previous state
        const previousState = this.undoStack[this.undoStack.length - 1];

        // Store the cursor position before any changes
        const targetStart = previousState.selectionStart;
        const targetEnd = previousState.selectionEnd;

        // Apply previous state with the flag set
        this.isUndoRedoOperation = true;
        textarea.value = previousState.text;
        this.documentText = previousState.text;

        // Update sections first
        this.parseSections();

        // Safari-specific cursor restoration using multiple animation frames
        const restoreCursor = () => {
            textarea.focus();
            
            // Force Safari to update its internal state
            if (textarea.setSelectionRange) {
                // Set to end first, then to desired position (Safari workaround)
                textarea.setSelectionRange(textarea.value.length, textarea.value.length);
                
                // Use setTimeout with 0 delay to ensure Safari processes the previous operation
                setTimeout(() => {
                    textarea.setSelectionRange(targetStart, targetEnd);
                    
                    // Ensure cursor is visible by scrolling it into view
                    const textBeforeCursor = textarea.value.substring(0, targetStart);
                    const lines = textBeforeCursor.split('\n').length;
                    const lineHeight = parseInt(window.getComputedStyle(textarea).lineHeight) || 20;
                    const scrollTop = Math.max(0, (lines - 5) * lineHeight);
                    
                    // Store current scroll position
                    const currentScroll = textarea.scrollTop;
                    
                    // Only scroll if necessary
                    if (Math.abs(currentScroll - scrollTop) > lineHeight * 2) {
                        textarea.scrollTop = scrollTop;
                    }
                    
                    // Final cursor position check after a delay
                    requestAnimationFrame(() => {
                        // Double-check cursor position for Safari
                        if (textarea.selectionStart !== targetStart || textarea.selectionEnd !== targetEnd) {
                            textarea.setSelectionRange(targetStart, targetEnd);
                        }
                        
                        this.isUndoRedoOperation = false;
                        this.handleCursorChange();
                    });
                }, 0);
            } else {
                // Fallback for older browsers
                this.isUndoRedoOperation = false;
                this.handleCursorChange();
            }
        };

        // Use double requestAnimationFrame for Safari compatibility
        requestAnimationFrame(() => {
            requestAnimationFrame(restoreCursor);
        });

        // Limit redo stack size
        if (this.redoStack.length > this.maxUndoSteps) {
            this.redoStack.shift();
        }

        this.showMessage('Undo applied', 'success');
    }
        
    redo() {
        if (this.redoStack.length === 0) {
            this.showMessage('Nothing to redo', 'info');
            return;
        }

        const textarea = document.getElementById('document-text');

        // Get next state from redo stack
        const nextState = this.redoStack.pop();

        // Save current state to undo stack
        const currentState = {
            text: textarea.value,
            selectionStart: textarea.selectionStart,
            selectionEnd: textarea.selectionEnd,
            timestamp: Date.now()
        };
        this.undoStack.push(currentState);

        // Apply next state
        this.isUndoRedoOperation = true;
        textarea.value = nextState.text;
        this.documentText = nextState.text;

        // Update sections first
        this.parseSections();

        // Use requestAnimationFrame to ensure DOM has updated before restoring cursor
        // This is especially important for Safari which may lose cursor position otherwise
        requestAnimationFrame(() => {
            textarea.focus();
            textarea.setSelectionRange(nextState.selectionStart, nextState.selectionEnd);

            // Ensure cursor is visible by scrolling it into view (Safari fix)
            const cursorPosition = nextState.selectionStart;
            const textBeforeCursor = textarea.value.substring(0, cursorPosition);
            const lines = textBeforeCursor.split('\n').length;
            const lineHeight = parseInt(window.getComputedStyle(textarea).lineHeight) || 20;
            const scrollTop = Math.max(0, (lines - 5) * lineHeight);
            textarea.scrollTop = scrollTop;

            this.handleCursorChange();
        });

        this.isUndoRedoOperation = false;

        // Limit undo stack size
        if (this.undoStack.length > this.maxUndoSteps) {
            this.undoStack.shift();
        }

        this.showMessage('Redo applied', 'success');
    }

    clearUndoHistory() {
        this.undoStack = [];
        this.redoStack = [];
        this.lastUndoState = null;
        this.saveUndoState(); // Save current state as first undo point
    }

    // Hotkey Management System
    initializeHotkeys() {
        // Load hotkeys from localStorage or use defaults
        this.hotkeys = {
            generate: localStorage.getItem('generateHotkey') || 'Ctrl+G',
            useText: localStorage.getItem('useTextHotkey') || 'Ctrl+U'
        };

        // Update button labels with current hotkeys
        this.updateButtonLabels();

        // Set up global hotkey listener
        this.setupHotkeyListener();

        // Load hotkey values into settings form
        this.loadHotkeySettings();
    }

    setupHotkeyListener() {
        // Remove existing listener if it exists
        if (this.hotkeyListener) {
            document.removeEventListener('keydown', this.hotkeyListener);
        }

        // Create new listener
        this.hotkeyListener = (e) => {
            const pressedKey = this.getKeyComboString(e);

            // Skip if this is an undo/redo shortcut (handled by undo system)
            if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'y')) {
                return;
            }

            if (pressedKey === this.hotkeys.generate) {
                e.preventDefault();
                // Trigger ideas mode by default with hotkey
                const ideasBtn = document.querySelector('.mode-btn[data-mode="ideas"]');
                if (ideasBtn && !ideasBtn.disabled) {
                    this.generateSuggestionForCurrentSection('ideas');
                }
            } else if (pressedKey === this.hotkeys.useText) {
                e.preventDefault();
                const useSuggestionBtn = document.getElementById('use-suggestion-btn');
                if (!useSuggestionBtn.disabled) {
                    this.useSuggestion();
                }
            }
        };

        document.addEventListener('keydown', this.hotkeyListener);
    }

    getKeyComboString(e) {
        const parts = [];
        if (e.ctrlKey) parts.push('Ctrl');
        if (e.altKey) parts.push('Alt');
        if (e.shiftKey) parts.push('Shift');
        if (e.metaKey) parts.push('Meta');

        // Get the main key
        let key = e.key;
        if (key === ' ') key = 'Space';
        else if (key === 'Enter') key = 'Enter';
        else if (key.length === 1) key = key.toUpperCase();

        // Don't include modifier keys as the main key
        if (!['Control', 'Alt', 'Shift', 'Meta'].includes(key)) {
            parts.push(key);
        }

        return parts.join('+');
    }

    parseHotkeyString(hotkeyString) {
        if (!hotkeyString || typeof hotkeyString !== 'string') return null;

        const parts = hotkeyString.split('+').map(p => p.trim());
        if (parts.length === 0) return null;

        return {
            ctrl: parts.includes('Ctrl'),
            alt: parts.includes('Alt'),
            shift: parts.includes('Shift'),
            meta: parts.includes('Meta'),
            key: parts[parts.length - 1] // Last part is the main key
        };
    }

    updateButtonLabels() {
        this.setUseSuggestionButtonText();
    }

    setUseSuggestionButtonText(baseText = null) {
        const useSuggestionBtn = document.getElementById('use-suggestion-btn');
        if (!useSuggestionBtn) return;

        if (baseText === null) {
            baseText = useSuggestionBtn.textContent.split('(')[0].trim();
        }
        useSuggestionBtn.textContent = `${baseText} (${this.hotkeys.useText})`;
    }

    loadHotkeySettings() {
        const generateInput = document.getElementById('generate-hotkey');
        const useTextInput = document.getElementById('use-text-hotkey');

        if (generateInput) generateInput.value = this.hotkeys.generate;
        if (useTextInput) useTextInput.value = this.hotkeys.useText;
    }

    saveHotkeySettings() {
        const generateInput = document.getElementById('generate-hotkey');
        const useTextInput = document.getElementById('use-text-hotkey');

        if (generateInput && generateInput.value.trim()) {
            this.hotkeys.generate = generateInput.value.trim();
            localStorage.setItem('generateHotkey', this.hotkeys.generate);
        }

        if (useTextInput && useTextInput.value.trim()) {
            this.hotkeys.useText = useTextInput.value.trim();
            localStorage.setItem('useTextHotkey', this.hotkeys.useText);
        }

        // Update the system
        this.updateButtonLabels();
        this.setupHotkeyListener();
    }

    async createNewDocument() {
        const title = document.getElementById('new-document-title').value.trim();
        const content = document.getElementById('new-document-outline').value.trim();

        if (!title && !content) {
            this.showMessage('Please provide either a title or initial content.', 'error');
            return;
        }

        try {
            // Reset to saved defaults from localStorage for new document
            this.documentMetadata = {
                writing_style: localStorage.getItem('writingStyle') || 'formal',
                target_audience: localStorage.getItem('targetAudience') || '',
                tone: localStorage.getItem('tone') || 'neutral',
                background_context: localStorage.getItem('backgroundContext') || '',
                generation_directive: localStorage.getItem('generationDirective') || '',
                word_limit: localStorage.getItem('wordLimit') || null,
                source: localStorage.getItem('generationSource') || '',
                model: localStorage.getItem('generationModel') || ''
            };

            // Apply saved AI settings (no server call needed)
            this.applySavedAISettings();

            // Set new title in both state and DOM
            this.documentTitle = title;
            const titleInput = document.getElementById('document-title');
            titleInput.value = title;

            // Set new content in both state and DOM
            this.documentText = content;
            const textarea = document.getElementById('document-text');
            textarea.value = content;

            this.parseSections();
            this.handleCursorChange();

            // Clear current filename since this is a new document
            this.currentFilename = null;
            this.updateFilenameDisplay();

            // Update the settings form to reflect the new document's metadata
            this.loadCurrentDocumentToSettingsForm();

            this.hideNewDocumentModal();

            // Reset undo history for new document
            this.clearUndoHistory();

            this.showMessage('New document created successfully!', 'success');
        } catch (error) {
            console.error('Error creating new document:', error);
            this.showMessage('Error creating new document. Please try again.', 'error');
        }
    }

    async copyDocumentToClipboard() {
        try {
            let documentText = '';
            if (this.documentTitle) {
                documentText += this.documentTitle + '\n\n';
            }
            documentText += this.documentText || '(No content)';

            // Try modern clipboard API first
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(documentText);
                this.showMessage('Document copied to clipboard!', 'success');
            } else {
                // Fallback for older browsers or insecure contexts
                this.fallbackCopyToClipboard(documentText);
            }
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            // Try fallback method
            try {
                let documentText = '';
                if (this.documentTitle) {
                    documentText += this.documentTitle + '\n\n';
                }
                documentText += this.documentText || '(No content)';
                this.fallbackCopyToClipboard(documentText);
            } catch (fallbackError) {
                console.error('Fallback copy also failed:', fallbackError);
                this.showMessage('Failed to copy to clipboard. Your browser may not support this feature.', 'error');
            }
        }
    }

    fallbackCopyToClipboard(text) {
        // Create a temporary textarea element
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.top = '0';
        textarea.style.left = '0';
        textarea.style.width = '2em';
        textarea.style.height = '2em';
        textarea.style.padding = '0';
        textarea.style.border = 'none';
        textarea.style.outline = 'none';
        textarea.style.boxShadow = 'none';
        textarea.style.background = 'transparent';

        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();

        try {
            const successful = document.execCommand('copy');
            if (successful) {
                this.showMessage('Document copied to clipboard!', 'success');
            } else {
                throw new Error('execCommand failed');
            }
        } catch (err) {
            throw new Error('Fallback copy method failed');
        } finally {
            document.body.removeChild(textarea);
        }
    }

    // Document management methods (simplified versions)
    async saveDocument() {
        const filename = document.getElementById('save-filename').value.trim();
        if (!filename) {
            this.showMessage('Please enter a filename', 'error');
            return;
        }

        try {
            const documentData = {
                title: this.documentTitle,
                content: this.documentText,
                sections: this.sections,
                metadata: {
                    writing_style: document.getElementById('writing-style').value,
                    target_audience: document.getElementById('target-audience').value,
                    tone: document.getElementById('tone').value,
                    background_context: document.getElementById('background-context').value,
                    generation_directive: document.getElementById('generation-directive').value,
                    word_limit: document.getElementById('word-limit').value || null,
                    source: document.getElementById('ai-source').value,
                    model: document.getElementById('ai-model').value
                },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const formData = new FormData();
            formData.append('filename', filename);
            formData.append('document_data', JSON.stringify(documentData));

            const response = await this.authFetch('/documents/save', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Document saved as ${result.filename}`, 'success');
                document.getElementById('save-filename').value = '';
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error saving document:', error);
            this.showMessage('Error saving document', 'error');
        }
    }

    async downloadDocument() {
        try {
            const title = this.documentTitle || 'document';

            const documentData = {
                title: title,
                content: this.documentText,
                sections: this.sections,
                metadata: {
                    writing_style: this.documentMetadata.writing_style,
                    target_audience: this.documentMetadata.target_audience,
                    tone: this.documentMetadata.tone,
                    background_context: this.documentMetadata.background_context,
                    generation_directive: this.documentMetadata.generation_directive,
                    word_limit: this.documentMetadata.word_limit,
                    source: this.documentMetadata.source,
                    model: this.documentMetadata.model
                },
                created_at: new Date().toISOString()
            };

            const blob = new Blob([JSON.stringify(documentData, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = title + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showMessage('Document downloaded', 'success');
        } catch (error) {
            console.error('Error downloading document:', error);
            this.showMessage('Error downloading document', 'error');
        }
    }

    async loadDocument() {
        const fileInput = document.getElementById('load-file');
        if (!fileInput.files[0]) {
            this.showMessage('Please select a file', 'error');
            return;
        }

        try {
            const file = fileInput.files[0];
            const content = await file.text();
            const documentData = JSON.parse(content);

            // Load document data into both state and DOM
            if (documentData.title) {
                this.documentTitle = documentData.title;
                document.getElementById('document-title').value = documentData.title;
            } else {
                this.documentTitle = '';
                document.getElementById('document-title').value = '';
            }

            if (documentData.content) {
                this.documentText = documentData.content;
                document.getElementById('document-text').value = documentData.content;
                this.parseSections();
                this.handleCursorChange();
            } else {
                this.documentText = '';
                document.getElementById('document-text').value = '';
                this.parseSections();
                this.handleCursorChange();
            }

            this.showMessage('Document loaded successfully', 'success');
        } catch (error) {
            console.error('Error loading document:', error);
            this.showMessage('Error loading document', 'error');
        }
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file && !file.name.endsWith('.json')) {
            this.showMessage('Please select a JSON file', 'error');
            event.target.value = '';
        }
    }

    async loadDocumentsList() {
        const listContainer = document.getElementById('documents-list');

        try {
            const response = await this.authFetch('/documents/list');
            const result = await response.json();

            if (result.error) {
                listContainer.innerHTML = `<p class="error">Error loading documents: ${result.error}</p>`;
                return;
            }

            const files = result.files || [];

            if (files.length === 0) {
                listContainer.innerHTML = '<p class="no-documents">No saved documents found.</p>';
                return;
            }

            // Create document list HTML
            let html = '';
            files.forEach(file => {
                const sizeKB = Math.round(file.size / 1024 * 10) / 10;
                const date = new Date(file.modified).toLocaleDateString();
                const time = new Date(file.modified).toLocaleTimeString();

                html += `
                    <div class="document-item">
                        <div class="document-info">
                            <div class="document-name">${file.filename}</div>
                            <div class="document-date">Modified: ${date} at ${time}</div>
                            <div class="document-size">Size: ${sizeKB} KB</div>
                        </div>
                        <div class="document-actions">
                            <button class="btn btn-primary btn-small load-document-btn" data-filename="${file.filename}">Load</button>
                            <button class="btn btn-secondary btn-small download-document-btn" data-filename="${file.filename}">Download</button>
                            <button class="btn btn-danger btn-small delete-document-btn" data-filename="${file.filename}">Delete</button>
                        </div>
                    </div>
                `;
            });

            listContainer.innerHTML = html;

            // Add event listeners for document actions
            this.setupDocumentActionListeners();

        } catch (error) {
            console.error('Error loading documents list:', error);
            listContainer.innerHTML = '<p class="error">Error loading documents list.</p>';
        }
    }

    setupDocumentActionListeners() {
        // Load document buttons
        document.querySelectorAll('.load-document-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filename = e.target.dataset.filename;
                this.loadDocumentByFilename(filename);
            });
        });

        // Download document buttons
        document.querySelectorAll('.download-document-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filename = e.target.dataset.filename;
                this.downloadDocumentByFilename(filename);
            });
        });

        // Delete document buttons
        document.querySelectorAll('.delete-document-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filename = e.target.dataset.filename;
                this.deleteDocumentByFilename(filename);
            });
        });
    }

    async loadDocumentByFilename(filename) {
        try {
            const response = await this.authFetch(`/documents/download/${filename}`);

            if (!response.ok) {
                throw new Error('Document not found');
            }

            const blob = await response.blob();
            const text = await blob.text();
            const documentData = JSON.parse(text);

            // Load document data into both state and DOM
            if (documentData.title) {
                this.documentTitle = documentData.title;
                document.getElementById('document-title').value = documentData.title;
            } else {
                this.documentTitle = '';
                document.getElementById('document-title').value = '';
            }

            if (documentData.content) {
                this.documentText = documentData.content;
                document.getElementById('document-text').value = documentData.content;
                this.parseSections();
                // Restore saved section data (including generated_text)
                this.restoreSavedSections(documentData.sections);
                // Restore document metadata settings
                this.restoreDocumentMetadata(documentData);
                this.handleCursorChange();
            } else {
                this.documentText = '';
                document.getElementById('document-text').value = '';
                this.parseSections();
                this.handleCursorChange();
            }

            this.hideDocumentsModal();
            this.showMessage(`Document "${filename}" loaded successfully!`, 'success');
        } catch (error) {
            console.error('Error loading document:', error);
            this.showMessage('Error loading document', 'error');
        }
    }

    async downloadDocumentByFilename(filename) {
        try {
            const response = await this.authFetch(`/documents/download/${filename}`);

            if (!response.ok) {
                throw new Error('Document not found');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showMessage(`Document "${filename}" downloaded`, 'success');
        } catch (error) {
            console.error('Error downloading document:', error);
            this.showMessage('Error downloading document', 'error');
        }
    }

    async deleteDocumentByFilename(filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
            return;
        }

        try {
            // We need to add a delete endpoint
            const response = await this.authFetch(`/documents/delete/${filename}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Failed to delete document');
            }

            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Document "${filename}" deleted successfully`, 'success');
                // Refresh the documents list
                this.loadDocumentsList();
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            this.showMessage('Error deleting document', 'error');
        }
    }

    // SERVER SAVE/LOAD METHODS
    async saveDocumentToServer() {
        // Try to save with current filename first, or prompt if none exists
        if (this.currentFilename) {
            await this.saveWithFilename(this.currentFilename);
        } else {
            this.showSaveAsModal();
        }
    }

    async saveDocumentAs() {
        const filename = document.getElementById('save-as-filename').value.trim();

        if (!filename) {
            this.showMessage('Please enter a filename', 'error');
            return;
        }

        this.hideSaveAsModal();
        await this.saveWithFilename(filename, true); // true for "save as"
    }

    async createSnapshot() {
        // Check if document has been saved
        if (!this.currentFilename) {
            this.showMessage('Please save the document first before creating a snapshot', 'info');
            this.showSaveAsModal();
            return;
        }

        // Save the current document state first
        await this.saveWithFilename(this.currentFilename);

        // Then create the snapshot
        try {
            const response = await this.authFetch(`/documents/snapshot/${this.currentFilename}`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Snapshot created: ${result.snapshot_filename}`, 'success');
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error creating snapshot:', error);
            this.showMessage('Error creating snapshot', 'error');
        }
    }

    async saveWithFilename(filename, isSaveAs = false, isAutoSave = false) {
        try {
            const documentData = {
                title: this.documentTitle,
                content: this.documentText,
                sections: this.sections,
                metadata: {
                    writing_style: document.getElementById('writing-style').value,
                    target_audience: document.getElementById('target-audience').value,
                    tone: document.getElementById('tone').value,
                    background_context: document.getElementById('background-context').value,
                    generation_directive: document.getElementById('generation-directive').value,
                    word_limit: document.getElementById('word-limit').value || null,
                    source: document.getElementById('ai-source').value,
                    model: document.getElementById('ai-model').value
                },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const formData = new FormData();

            // Always include filename - use existing filename for regular save or provided filename for save-as/first save
            const saveFilename = isSaveAs || !this.currentFilename ? filename : this.currentFilename;
            formData.append('filename', saveFilename);

            // Always send the document data
            formData.append('document_data', JSON.stringify(documentData));

            // Use the backend Document save endpoints which save the actual document state
            const endpoint = isSaveAs ? '/documents/save-as' : '/documents/save';

            const response = await this.authFetch(endpoint, {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.currentFilename = result.filename;
                this.updateFilenameDisplay();
                this.lastSaveTime = new Date();
                if (!isAutoSave) {
                    this.showMessage(`Document saved as "${result.filename}"`, 'success');
                }
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error saving document:', error);
            this.showMessage('Error saving document', 'error');
        }
    }

    showLoadDocumentModal() {
        const modal = document.getElementById('load-document-modal');
        modal.classList.add('show');
        this.loadDocumentsList();
    }

    hideLoadDocumentModal() {
        const modal = document.getElementById('load-document-modal');
        modal.classList.remove('show');
    }

    async loadDocumentsList() {
        const listContainer = document.getElementById('load-documents-list');

        try {
            const response = await this.authFetch('/documents/list');
            const result = await response.json();

            if (result.error) {
                listContainer.innerHTML = `<p class="error">Error loading documents: ${result.error}</p>`;
                return;
            }

            const files = result.files || [];

            if (files.length === 0) {
                listContainer.innerHTML = '<p class="no-documents">No saved documents found.</p>';
                return;
            }

            // Create document list HTML
            let html = '';
            files.forEach(file => {
                const sizeKB = Math.round(file.size / 1024 * 10) / 10;
                const date = new Date(file.modified).toLocaleDateString();
                const time = new Date(file.modified).toLocaleTimeString();

                html += `
                    <div class="document-item">
                        <div class="document-info">
                            <div class="document-name">${file.filename}</div>
                            <div class="document-date">Modified: ${date} at ${time}</div>
                            <div class="document-size">Size: ${sizeKB} KB</div>
                        </div>
                        <div class="document-actions">
                            <button class="btn btn-primary btn-small load-document-btn" data-filename="${file.filename}">Load</button>
                            <button class="btn btn-danger btn-small delete-document-btn" data-filename="${file.filename}">Delete</button>
                        </div>
                    </div>
                `;
            });

            listContainer.innerHTML = html;
            this.setupDocumentActionListeners();

        } catch (error) {
            console.error('Error loading documents list:', error);
            listContainer.innerHTML = '<p class="error">Error loading documents list.</p>';
        }
    }

    setupDocumentActionListeners() {
        // Load document buttons
        document.querySelectorAll('.load-document-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filename = e.target.dataset.filename;
                this.loadDocumentFromServer(filename);
            });
        });

        // Delete document buttons
        document.querySelectorAll('.delete-document-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filename = e.target.dataset.filename;
                this.deleteDocumentFromServer(filename);
            });
        });
    }

    async loadDocumentFromServer(filename) {
        try {
            // Get document data directly from the load endpoint
            const response = await this.authFetch(`/documents/load/${filename}`);

            if (!response.ok) {
                throw new Error('Document not found');
            }

            const result = await response.json();

            if (result.status !== 'success') {
                throw new Error(result.message || 'Failed to load document');
            }

            const documentData = result.document;

            // Load document data into both state and DOM
            if (documentData.title) {
                this.documentTitle = documentData.title;
                document.getElementById('document-title').value = documentData.title;
            } else {
                this.documentTitle = '';
                document.getElementById('document-title').value = '';
            }

            if (documentData.content) {
                this.documentText = documentData.content;
                document.getElementById('document-text').value = documentData.content;
                this.parseSections();
                // Restore saved section data (including generated_text)
                this.restoreSavedSections(documentData.sections);
                this.handleCursorChange();
            } else {
                this.documentText = '';
                document.getElementById('document-text').value = '';
                this.parseSections();
                this.handleCursorChange();
            }

            // Always restore document metadata settings, regardless of content
            this.restoreDocumentMetadata(documentData);

            // Set current filename
            this.currentFilename = filename;
            this.updateFilenameDisplay();

            this.hideLoadDocumentModal();
            
            // Reset undo history for loaded document
            this.clearUndoHistory();
            
            this.showMessage(`Document "${filename}" loaded successfully!`, 'success');
        } catch (error) {
            console.error('Error loading document:', error);
            this.showMessage('Error loading document', 'error');
        }
    }

    async deleteDocumentFromServer(filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
            return;
        }

        try {
            const response = await this.authFetch(`/documents/delete/${filename}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Failed to delete document');
            }

            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Document "${filename}" deleted successfully`, 'success');
                this.loadDocumentsList(); // Refresh the list
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            this.showMessage('Error deleting document', 'error');
        }
    }

    // LOCAL FILE IMPORT/EXPORT METHODS
    importDocumentFromFile() {
        // Trigger the hidden file input
        document.getElementById('file-input').click();
    }

    async handleFileImport(event) {
        const file = event.target.files[0];
        if (!file) {
            return;
        }

        if (!file.name.endsWith('.json')) {
            this.showMessage('Please select a JSON file', 'error');
            event.target.value = '';
            return;
        }

        try {
            const content = await file.text();
            const documentData = JSON.parse(content);

            // Load document data into both state and DOM
            if (documentData.title) {
                this.documentTitle = documentData.title;
                document.getElementById('document-title').value = documentData.title;
            } else {
                this.documentTitle = '';
                document.getElementById('document-title').value = '';
            }

            if (documentData.content) {
                this.documentText = documentData.content;
                document.getElementById('document-text').value = documentData.content;
                this.parseSections();
                // Restore saved section data (including generated_text)
                this.restoreSavedSections(documentData.sections);
                // Restore document metadata settings
                this.restoreDocumentMetadata(documentData);
                this.handleCursorChange();
            } else {
                this.documentText = '';
                document.getElementById('document-text').value = '';
                this.parseSections();
                this.handleCursorChange();
            }

            // Clear current filename since this was imported from local file
            this.currentFilename = null;
            this.updateFilenameDisplay();

            // Clear the file input so the same file can be loaded again
            event.target.value = '';

            this.showMessage(`Document "${file.name}" imported successfully!`, 'success');
        } catch (error) {
            console.error('Error importing document:', error);
            this.showMessage('Error importing document. Please check the file format.', 'error');
            event.target.value = '';
        }
    }

    async exportDocumentToFile() {
        try {
            const title = this.documentTitle || 'document';

            const documentData = {
                title: title,
                content: this.documentText,
                sections: this.sections,
                metadata: {
                    writing_style: this.documentMetadata.writing_style,
                    target_audience: this.documentMetadata.target_audience,
                    tone: this.documentMetadata.tone,
                    background_context: this.documentMetadata.background_context,
                    generation_directive: this.documentMetadata.generation_directive,
                    word_limit: this.documentMetadata.word_limit,
                    source: this.documentMetadata.source,
                    model: this.documentMetadata.model
                },
                created_at: new Date().toISOString()
            };

            const blob = new Blob([JSON.stringify(documentData, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = title + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showMessage('Document exported successfully!', 'success');
        } catch (error) {
            console.error('Error exporting document:', error);
            this.showMessage('Error exporting document', 'error');
        }
    }

    updateFilenameDisplay() {
        const filenameElement = document.getElementById('current-filename');
        if (!filenameElement) return;

        if (this.currentFilename) {
            // Remove .json extension for display
            const displayName = this.currentFilename.replace(/\.json$/, '');
            filenameElement.textContent = displayName;
            filenameElement.className = 'filename-text saved';
        } else {
            filenameElement.textContent = 'Unsaved Document';
            filenameElement.className = 'filename-text unsaved';
        }
    }

    setupAutoSave() {
        // Start auto-save timer (5 minutes = 300000ms)
        this.startAutoSaveTimer();

        // Reset timer on document changes
        const titleInput = document.getElementById('document-title');
        const documentTextarea = document.getElementById('document-text');

        if (titleInput) {
            titleInput.addEventListener('input', () => {
                this.resetAutoSaveTimer();
            });
        }

        if (documentTextarea) {
            documentTextarea.addEventListener('input', () => {
                this.resetAutoSaveTimer();
            });
        }
    }

    startAutoSaveTimer() {
        this.clearAutoSaveTimer();
        this.autoSaveTimer = setTimeout(() => {
            this.performAutoSave();
        }, 300000); // 5 minutes
    }

    resetAutoSaveTimer() {
        this.startAutoSaveTimer();
    }

    clearAutoSaveTimer() {
        if (this.autoSaveTimer) {
            clearTimeout(this.autoSaveTimer);
            this.autoSaveTimer = null;
        }
    }

    async performAutoSave() {
        // Only auto-save if document has been saved at least once
        if (!this.currentFilename) {
            this.startAutoSaveTimer(); // Restart timer
            return;
        }

        try {
            await this.saveWithFilename(this.currentFilename, false, true);
            this.lastSaveTime = new Date();
            this.showMessage('Document auto-saved', 'success');
        } catch (error) {
            console.error('Auto-save failed:', error);
            this.showMessage('Auto-save failed', 'error');
        }

        // Restart the timer
        this.startAutoSaveTimer();
    }

    setupPageExitHandler() {
        // Save on page unload (if document has been saved before)
        window.addEventListener('beforeunload', () => {
            if (this.currentFilename) {
                // Perform synchronous save before page unload
                this.performSyncSave();
            }
        });

        // Also handle visibility change (when user switches tabs/minimizes)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && this.currentFilename) {
                this.performSyncSave();
            }
        });
    }

    performSyncSave() {
        if (!this.currentFilename || this.isPerformingSyncSave) return;

        this.isPerformingSyncSave = true;

        try {
            const documentData = {
                title: this.documentTitle,
                content: this.documentText,
                sections: this.sections,
                metadata: {
                    writing_style: document.getElementById('writing-style')?.value || this.documentMetadata.writing_style,
                    target_audience: document.getElementById('target-audience')?.value || this.documentMetadata.target_audience,
                    tone: document.getElementById('tone')?.value || this.documentMetadata.tone,
                    background_context: document.getElementById('background-context')?.value || this.documentMetadata.background_context,
                    generation_directive: document.getElementById('generation-directive')?.value || this.documentMetadata.generation_directive,
                    word_limit: document.getElementById('word-limit')?.value || this.documentMetadata.word_limit,
                    source: document.getElementById('ai-source')?.value || this.documentMetadata.source,
                    model: document.getElementById('ai-model')?.value || this.documentMetadata.model
                },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            // Create form data for the request
            const formData = new FormData();
            formData.append('filename', this.currentFilename);
            formData.append('document_data', JSON.stringify(documentData));

            // Use fetch with keepalive for reliable sending during page unload
            // This is similar to sendBeacon but supports auth headers
            fetch('/documents/save', this.getAuthFetchOptions({
                method: 'POST',
                body: formData,
                keepalive: true
            }));
        } catch (error) {
            console.error('Sync save failed:', error);
        } finally {
            // Reset flag after a short delay to allow for legitimate subsequent saves
            setTimeout(() => {
                this.isPerformingSyncSave = false;
            }, 1000);
        }
    }

    showMessage(text, type) {
        // Remove any existing message
        const existingMessage = document.querySelector('.message');
        if (existingMessage) {
            existingMessage.classList.remove('show');
            setTimeout(() => existingMessage.remove(), 300);
        }

        // Create new floating message
        const message = document.createElement('div');
        message.className = `message message-${type}`;
        message.textContent = text;

        // Add to body for proper positioning
        document.body.appendChild(message);

        // Trigger animation after a brief delay
        setTimeout(() => {
            message.classList.add('show');
        }, 50);

        // Auto-remove after 4 seconds with fade out animation
        setTimeout(() => {
            message.classList.remove('show');
            setTimeout(() => {
                if (message.parentNode) {
                    message.remove();
                }
            }, 300);
        }, 4000);
    }

    // File Menu Dropdown Methods
    toggleFileMenu() {
        const dropdown = document.getElementById('file-menu-content');
        dropdown.classList.toggle('show');
    }

    hideFileMenu() {
        const dropdown = document.getElementById('file-menu-content');
        dropdown.classList.remove('show');
    }

    // Dark Mode Methods
    initializeDarkMode() {
        // Check if user has a saved preference
        const savedMode = localStorage.getItem('darkMode');

        if (savedMode === 'enabled') {
            document.body.classList.add('dark-mode');
        } else if (savedMode === null) {
            // Check system preference if no saved preference
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                document.body.classList.add('dark-mode');
            }
        }

        // Listen for system preference changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                // Only apply if user hasn't manually set a preference
                if (localStorage.getItem('darkMode') === null) {
                    if (e.matches) {
                        document.body.classList.add('dark-mode');
                    } else {
                        document.body.classList.remove('dark-mode');
                    }
                }
            });
        }
    }

    toggleDarkMode() {
        const isDarkMode = document.body.classList.toggle('dark-mode');

        // Save preference
        localStorage.setItem('darkMode', isDarkMode ? 'enabled' : 'disabled');

        // Show feedback
        this.showMessage(isDarkMode ? 'Dark mode enabled' : 'Light mode enabled', 'success');
    }

    // Environment Variables Management
    loadEnvironmentVariables() {
        const saved = localStorage.getItem('environmentVariables');
        if (saved) {
            try {
                return JSON.parse(saved);
            } catch (e) {
                console.error('Failed to parse environment variables:', e);
                return {};
            }
        }
        return {};
    }

    saveEnvironmentVariables() {
        const envVars = {};
        const container = document.getElementById('env-vars-container');
        const rows = container.querySelectorAll('.env-var-item');

        rows.forEach(row => {
            const keyInput = row.querySelector('.env-var-key');
            const valueInput = row.querySelector('.env-var-value');
            const key = keyInput.value.trim();
            const value = valueInput.value.trim();

            if (key && value) {
                envVars[key] = value;
            }
        });

        this.environmentVariables = envVars;
        localStorage.setItem('environmentVariables', JSON.stringify(envVars));
    }

    renderEnvironmentVariables() {
        const container = document.getElementById('env-vars-container');
        container.innerHTML = '';

        // Render existing environment variables
        Object.entries(this.environmentVariables).forEach(([key, value]) => {
            this.addEnvironmentVariableRow(key, value);
        });
    }

    addEnvironmentVariableRow(key = '', value = '') {
        const container = document.getElementById('env-vars-container');

        const row = document.createElement('div');
        row.className = 'env-var-item';

        row.innerHTML = `
            <input type="text" class="env-var-key" placeholder="Variable name (e.g., OPENAI_API_KEY)" value="${this.escapeHtml(key)}">
            <input type="text" class="env-var-value" placeholder="Value" value="${this.escapeHtml(value)}">
            <button type="button" class="env-var-remove-btn">Remove</button>
        `;

        // Add event listener to remove button
        const removeBtn = row.querySelector('.env-var-remove-btn');
        removeBtn.addEventListener('click', () => {
            row.remove();
            // No need to save here, will save when user clicks "Save AI Settings"
        });

        container.appendChild(row);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global reference
let writingAssistant;

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired, creating WritingAssistant...');
    try {
        writingAssistant = new WritingAssistant();
        console.log('WritingAssistant instance created:', writingAssistant);
    } catch (error) {
        console.error('Failed to create WritingAssistant:', error);
    }
});
