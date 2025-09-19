class WritingAssistant {
    constructor() {
        this.sections = [];
        this.currentSectionIndex = -1;
        this.documentText = '';
        this.documentTitle = '';
        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.loadMetadata();
        // Apply saved AI settings to the initial document
        await this.applySavedAISettings();
        this.loadExistingDocument();
        this.setupModals();
    }

    setupEventListeners() {
        const titleInput = document.getElementById('document-title');
        const documentTextarea = document.getElementById('document-text');
        const generateBtn = document.getElementById('generate-btn');
        const useSuggestionBtn = document.getElementById('use-suggestion-btn');

        // Document title
        titleInput.addEventListener('input', () => this.handleTitleChange());

        // Document text editing and cursor tracking
        documentTextarea.addEventListener('input', () => this.handleDocumentTextChange());
        documentTextarea.addEventListener('click', () => this.handleCursorChange());
        documentTextarea.addEventListener('keyup', () => this.handleCursorChange());

        // AI suggestion controls
        generateBtn.addEventListener('click', () => this.generateSuggestionForCurrentSection());
        useSuggestionBtn.addEventListener('click', () => this.useSuggestion());

        // Initialize hotkey system
        this.initializeHotkeys();

        // Header controls
        document.getElementById('new-document-btn').addEventListener('click', () => this.showNewDocumentModal());
        document.getElementById('save-document-btn').addEventListener('click', () => this.saveDocumentToServer());
        document.getElementById('load-document-btn').addEventListener('click', () => this.showLoadDocumentModal());
        document.getElementById('import-document-btn').addEventListener('click', () => this.importDocumentFromFile());
        document.getElementById('export-document-btn').addEventListener('click', () => this.exportDocumentToFile());
        document.getElementById('file-input').addEventListener('change', (e) => this.handleFileImport(e));
        document.getElementById('copy-document-btn').addEventListener('click', () => this.copyDocumentToClipboard());
        document.getElementById('settings-btn').addEventListener('click', () => this.showSettingsModal());
    }

    setupModals() {
        // Settings modal
        const settingsModal = document.getElementById('settings-modal');
        const closeSettingsBtn = document.getElementById('close-settings-modal');
        const closeSettingsFooterBtn = document.getElementById('close-settings-btn');
        const saveMetadataBtn = document.getElementById('save-metadata-btn');
        const resetMetadataBtn = document.getElementById('reset-metadata-btn');
        const saveGenerationSettingsBtn = document.getElementById('save-generation-settings-btn');

        closeSettingsBtn.addEventListener('click', () => this.hideSettingsModal());
        closeSettingsFooterBtn.addEventListener('click', () => this.hideSettingsModal());
        saveMetadataBtn.addEventListener('click', () => this.saveMetadata());
        resetMetadataBtn.addEventListener('click', () => this.resetMetadata());
        saveGenerationSettingsBtn.addEventListener('click', () => this.saveGenerationSettings());

        // Settings tabs
        const settingsTabBtns = document.querySelectorAll('.settings-tab-btn');
        settingsTabBtns.forEach(btn => {
            btn.addEventListener('click', (e) => this.switchSettingsTab(e.target.dataset.settingsTab));
        });

        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) this.hideSettingsModal();
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
    }

    handleDocumentTextChange() {
        const textarea = document.getElementById('document-text');
        this.documentText = textarea.value;
        this.parseSections();
        this.handleCursorChange();
    }

    handleTitleChange() {
        const titleInput = document.getElementById('document-title');
        this.documentTitle = titleInput.value;
        // Don't send to server immediately - let it be managed with the document
    }

    parseSections() {
        const text = this.documentText;
        const oldSections = [...this.sections]; // Save previous sections
        this.sections = [];

        if (!text.trim()) {
            this.updateSectionInfo();
            return;
        }

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
                // Look for a section with the same or similar text content
                const matchingOldSection = oldSections.find(oldSection => {
                    // Exact match first
                    if (oldSection.text === trimmed) {
                        return true;
                    }
                    // If no exact match, check if the old section text is contained in the new text
                    // This handles cases where the user edited the section slightly
                    return trimmed.includes(oldSection.text) && oldSection.generated_text;
                });

                if (matchingOldSection && matchingOldSection.generated_text) {
                    newSection.generated_text = matchingOldSection.generated_text;
                }

                this.sections.push(newSection);
            }
        });

        this.updateSectionInfo();
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
        const generateBtn = document.getElementById('generate-btn');
        const useSuggestionBtn = document.getElementById('use-suggestion-btn');
        const infoElement = document.getElementById('current-section-info');

        if (this.currentSectionIndex === -1 || this.sections.length === 0) {
            suggestionText.textContent = 'Position your cursor in a section above to see AI suggestions for that section.';
            generateBtn.disabled = true;
            this.setGenerateButtonText('⚡ Generate');
            useSuggestionBtn.disabled = true;
            infoElement.textContent = 'No section selected';
        } else {
            const currentSection = this.sections[this.currentSectionIndex];
            const sectionNum = this.currentSectionIndex + 1;
            infoElement.textContent = `Section ${sectionNum} of ${this.sections.length} selected`;

            // Generate button is always enabled when a section is selected
            generateBtn.disabled = false;

            if (currentSection.generated_text) {
                suggestionText.textContent = currentSection.generated_text;
                this.setGenerateButtonText('🔄 Regenerate');
                useSuggestionBtn.disabled = false;
            } else {
                suggestionText.textContent = 'Click "Generate" to get AI suggestions for this section.';
                this.setGenerateButtonText('⚡ Generate');
                useSuggestionBtn.disabled = true;
            }
        }
    }

    async generateSuggestionForCurrentSection() {
        if (this.currentSectionIndex === -1 || this.sections.length === 0) {
            this.showMessage('Please position your cursor in a section first', 'error');
            return;
        }

        const currentSection = this.sections[this.currentSectionIndex];
        const generateBtn = document.getElementById('generate-btn');
        const suggestionText = document.getElementById('suggestion-text');

        // Show loading state
        generateBtn.disabled = true;
        this.setGenerateButtonText('⏳ Generating...');
        suggestionText.textContent = 'Generating AI suggestion...';

        try {
            // Get context (previous and next sections)
            const prevSection = this.currentSectionIndex > 0 ? this.sections[this.currentSectionIndex - 1] : null;
            const nextSection = this.currentSectionIndex < this.sections.length - 1 ? this.sections[this.currentSectionIndex + 1] : null;

            const title = document.getElementById('document-title').value || '';

            // Get selected generation mode
            const selectedMode = document.querySelector('input[name="generation-mode"]:checked').value;

            const formData = new FormData();
            formData.append('main_point', this.extractMainPoint(currentSection.text));
            formData.append('user_text', currentSection.text);
            formData.append('title', title);
            formData.append('prev_paragraph', prevSection ? prevSection.text : '');
            formData.append('next_paragraph', nextSection ? nextSection.text : '');
            formData.append('generation_mode', selectedMode);

            const response = await fetch('/generate-text', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.generated_text) {
                currentSection.generated_text = result.generated_text;
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
            generateBtn.disabled = false;
            // Update button text based on whether we have generated text
            if (currentSection.generated_text) {
                this.setGenerateButtonText('🔄 Regenerate');
            } else {
                this.setGenerateButtonText('⚡ Generate');
            }
        }
    }

    extractMainPoint(text) {
        // Extract the first sentence as the main point
        const sentences = text.split(/[.!?]+/);
        return sentences[0].trim() || text.substring(0, 100);
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

        // Debug section boundaries
        console.log('Section replacement debug:');
        console.log('Current section text:', JSON.stringify(currentSection.text));
        console.log('Section start pos:', currentSection.startPos);
        console.log('Section end pos:', currentSection.endPos);
        console.log('Generated text:', JSON.stringify(currentSection.generated_text));

        const beforeSection = this.documentText.substring(0, currentSection.startPos);
        const afterSection = this.documentText.substring(currentSection.endPos);

        console.log('Before section:', JSON.stringify(beforeSection.slice(-10))); // Last 10 chars
        console.log('After section:', JSON.stringify(afterSection.slice(0, 10))); // First 10 chars

        // Clean the generated text to prevent extra blank lines
        const cleanGeneratedText = currentSection.generated_text.trim();

        // Calculate new cursor position (end of the replaced section)
        const newCursorPos = beforeSection.length + cleanGeneratedText.length;

        // Replace the current section with the suggestion
        const newText = beforeSection + cleanGeneratedText + afterSection;
        textarea.value = newText;

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
            // Load both title and content from the DOM
            const titleInput = document.getElementById('document-title');
            const textarea = document.getElementById('document-text');

            this.documentTitle = titleInput.value || '';

            if (textarea.value.trim()) {
                this.documentText = textarea.value;
                this.parseSections();
                this.handleCursorChange();
            }
        } catch (error) {
            console.error('Error loading existing document:', error);
        }
    }

    async updateTitle(title) {
        const formData = new FormData();
        formData.append('title', title);

        try {
            await fetch('/title', {
                method: 'POST',
                body: formData
            });
        } catch (error) {
            console.error('Error updating title:', error);
        }
    }

    // Modal management methods
    showSettingsModal() {
        const modal = document.getElementById('settings-modal');
        modal.classList.add('show');
        this.loadMetadata();
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
            const response = await fetch('/metadata');
            const metadata = await response.json();

            // Load AI settings
            const savedSource = localStorage.getItem('generationSource') || metadata.source || '';
            const savedModel = localStorage.getItem('generationModel') || metadata.model || '';

            const sourceElement = document.getElementById('ai-source');
            const modelElement = document.getElementById('ai-model');
            if (sourceElement) sourceElement.value = savedSource;
            if (modelElement) modelElement.value = savedModel;

            // Load writing settings
            document.getElementById('writing-style').value = metadata.writing_style || 'formal';
            document.getElementById('target-audience').value = metadata.target_audience || '';
            document.getElementById('tone').value = metadata.tone || 'neutral';
            document.getElementById('background-context').value = metadata.background_context || '';
            document.getElementById('generation-directive').value = metadata.generation_directive || '';
            document.getElementById('word-limit').value = metadata.word_limit || '';
        } catch (error) {
            console.error('Error loading metadata:', error);
        }
    }

    async saveMetadata() {
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

        const formData = new FormData();
        Object.keys(metadata).forEach(key => {
            if (metadata[key] !== null && metadata[key] !== '') {
                formData.append(key, metadata[key]);
            }
        });

        try {
            await fetch('/metadata', {
                method: 'POST',
                body: formData
            });
            this.showMessage('Settings saved successfully!', 'success');
        } catch (error) {
            console.error('Error saving metadata:', error);
            this.showMessage('Error saving settings', 'error');
        }
    }

    async resetMetadata() {
        document.getElementById('ai-source').value = '';
        document.getElementById('ai-model').value = '';
        document.getElementById('writing-style').value = 'formal';
        document.getElementById('target-audience').value = '';
        document.getElementById('tone').value = 'neutral';
        document.getElementById('background-context').value = '';
        document.getElementById('generation-directive').value = '';
        document.getElementById('word-limit').value = '';

        await this.saveMetadata();
    }

    saveGenerationSettings() {
        const source = document.getElementById('ai-source').value;
        const model = document.getElementById('ai-model').value;

        localStorage.setItem('generationSource', source);
        localStorage.setItem('generationModel', model);

        // Save hotkey settings
        this.saveHotkeySettings();

        this.showMessage('AI settings and hotkeys saved successfully!', 'success');
    }

    async applySavedAISettings() {
        // Get saved AI settings from both localStorage and form fields
        const savedSource = localStorage.getItem('generationSource') || document.getElementById('ai-source')?.value || '';
        const savedModel = localStorage.getItem('generationModel') || document.getElementById('ai-model')?.value || '';

        console.log('applySavedAISettings called - savedSource:', savedSource, 'savedModel:', savedModel);

        // Always apply some metadata, even if source/model are empty, to ensure defaults are set
        const metadata = {
            source: savedSource,
            model: savedModel,
            writing_style: 'formal', // Keep existing defaults
            target_audience: 'general public',
            tone: 'neutral',
            background_context: 'none provided',
            generation_directive: 'use good grammar.  Be concise and clear.',
            word_limit: 250
        };

        const formData = new FormData();
        Object.keys(metadata).forEach(key => {
            // Always include source and model, even if empty
            if (key === 'source' || key === 'model' || (metadata[key] !== null && metadata[key] !== '')) {
                formData.append(key, metadata[key]);
            }
        });

        console.log('Sending metadata to server:', Array.from(formData.entries()));

        try {
            const response = await fetch('/metadata', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            console.log('Metadata update result:', result);
        } catch (error) {
            console.error('Error updating metadata:', error);
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
                // Simple text matching - could be made more sophisticated if needed
                const currentText = currentSection.text.trim();
                const savedText = savedSection.text ? savedSection.text.trim() : '';

                // If texts match exactly or are very similar, restore the generated text
                if (currentText === savedText ||
                    (currentText.length > 0 && savedText.length > 0 &&
                     currentText.substring(0, Math.min(100, currentText.length)) ===
                     savedText.substring(0, Math.min(100, savedText.length)))) {

                    currentSection.generated_text = savedSection.generated_text;
                    console.log(`Restored generated_text for section ${i}:`, savedSection.generated_text.substring(0, 50) + '...');
                }
            }
        }
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

            if (pressedKey === this.hotkeys.generate) {
                e.preventDefault();
                const generateBtn = document.getElementById('generate-btn');
                if (!generateBtn.disabled) {
                    this.generateSuggestionForCurrentSection();
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
        this.setGenerateButtonText();
        this.setUseSuggestionButtonText();
    }

    setGenerateButtonText(baseText = null) {
        const generateBtn = document.getElementById('generate-btn');
        if (!generateBtn) return;

        if (baseText === null) {
            baseText = generateBtn.textContent.split('(')[0].trim();
        }
        generateBtn.textContent = `${baseText} (${this.hotkeys.generate})`;
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

        console.log('Hotkeys updated:', this.hotkeys);
    }

    async createNewDocument() {
        const title = document.getElementById('new-document-title').value.trim();
        const content = document.getElementById('new-document-outline').value.trim();

        if (!title && !content) {
            this.showMessage('Please provide either a title or initial content.', 'error');
            return;
        }

        try {
            // Clear current document
            await fetch('/documents/clear', { method: 'POST' });

            // Apply saved AI settings to the new document
            await this.applySavedAISettings();

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

            this.hideNewDocumentModal();
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

            await navigator.clipboard.writeText(documentText);
            this.showMessage('Document copied to clipboard!', 'success');
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            this.showMessage('Failed to copy to clipboard. Please try again.', 'error');
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
            await this.saveMetadata();

            const documentData = {
                title: this.documentTitle,
                content: this.documentText,
                sections: this.sections,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const formData = new FormData();
            formData.append('filename', filename);
            formData.append('document_data', JSON.stringify(documentData));

            const response = await fetch('/documents/save-document', {
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
            const response = await fetch('/documents/list');
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
            const response = await fetch(`/documents/download/${filename}`);

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
            const response = await fetch(`/documents/download/${filename}`);

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
            const response = await fetch(`/documents/delete/${filename}`, {
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
        const filename = prompt('Enter a filename for your document:', this.documentTitle || 'document');

        if (!filename) {
            return; // User cancelled
        }

        try {
            await this.saveMetadata();

            const documentData = {
                title: this.documentTitle,
                content: this.documentText,
                sections: this.sections,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const formData = new FormData();
            formData.append('filename', filename);
            formData.append('document_data', JSON.stringify(documentData));

            const response = await fetch('/documents/save-document', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Document saved as "${result.filename}"`, 'success');
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
            const response = await fetch('/documents/list');
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
            const response = await fetch(`/documents/download/${filename}`);

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
                this.handleCursorChange();
            } else {
                this.documentText = '';
                document.getElementById('document-text').value = '';
                this.parseSections();
                this.handleCursorChange();
            }

            this.hideLoadDocumentModal();
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
            const response = await fetch(`/documents/delete/${filename}`, {
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
                this.handleCursorChange();
            } else {
                this.documentText = '';
                document.getElementById('document-text').value = '';
                this.parseSections();
                this.handleCursorChange();
            }

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
}

// Global reference
let writingAssistant;

document.addEventListener('DOMContentLoaded', () => {
    writingAssistant = new WritingAssistant();
});