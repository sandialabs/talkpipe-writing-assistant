class WritingAssistant {
    constructor() {
        this.pollingIntervals = new Map(); // Track polling for each section
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.updateSectionNumbers();
        this.loadMetadata();
        this.setupHamburgerMenu();
        this.initializeExistingSections();
    }

    setupEventListeners() {
        const titleInput = document.getElementById('document-title');
        const addSectionBtn = document.getElementById('add-section-btn');
        const sectionsList = document.getElementById('sections-list');
        
        const saveMetadataBtn = document.getElementById('save-metadata-btn');
        const resetMetadataBtn = document.getElementById('reset-metadata-btn');
        const tabButtons = document.querySelectorAll('.tab-btn');
        
        const saveDocumentBtn = document.getElementById('save-document-btn');
        const downloadCurrentBtn = document.getElementById('download-current-btn');
        const loadDocumentBtn = document.getElementById('load-document-btn');
        const refreshDocumentsBtn = document.getElementById('refresh-documents-btn');
        const loadFileInput = document.getElementById('load-file');
        const copyDocumentBtn = document.getElementById('copy-document-btn');
        const newDocumentBtn = document.getElementById('new-document-btn');
        const expandAllBtn = document.getElementById('expand-all-btn');
        const collapseAllBtn = document.getElementById('collapse-all-btn');

        titleInput.addEventListener('blur', () => this.updateTitle(titleInput.value));
        addSectionBtn.addEventListener('click', () => this.addSection());
        copyDocumentBtn.addEventListener('click', () => this.copyDocumentToClipboard());
        newDocumentBtn.addEventListener('click', () => this.showNewDocumentModal());
        expandAllBtn.addEventListener('click', () => this.expandAllSections());
        collapseAllBtn.addEventListener('click', () => this.collapseAllSections());
        
        saveMetadataBtn.addEventListener('click', () => this.saveMetadata());
        resetMetadataBtn.addEventListener('click', () => this.resetMetadata());
        
        saveDocumentBtn.addEventListener('click', () => this.saveDocument());
        downloadCurrentBtn.addEventListener('click', () => this.downloadDocument());
        loadDocumentBtn.addEventListener('click', () => this.loadDocument());
        refreshDocumentsBtn.addEventListener('click', () => this.loadDocumentsList());
        loadFileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });

        sectionsList.addEventListener('click', (e) => {
            console.log('Clicked element:', e.target.className, e.target.tagName);
            const section = e.target.closest('.section');
            const sectionWrapper = e.target.closest('.section-wrapper');

            if (e.target.classList.contains('delete-section') && section) {
                this.deleteSection(section.dataset.sectionId);
            } else if (e.target.classList.contains('move-up') && section) {
                this.moveSection(section, 'up');
            } else if (e.target.classList.contains('move-down') && section) {
                this.moveSection(section, 'down');
            } else if (e.target.classList.contains('insert-above-btn') && section) {
                const position = parseInt(section.dataset.order);
                this.insertSection(position);
            } else if (e.target.classList.contains('insert-below-btn') && section) {
                const position = parseInt(section.dataset.order) + 1;
                this.insertSection(position);
            } else if (e.target.classList.contains('btn-replace-text') && section) {
                this.replaceUserText(section);
            } else if (e.target.classList.contains('btn-generate-text') && section) {
                this.generateText(section);
            } else if (e.target.classList.contains('collapse-toggle') || e.target.classList.contains('collapse-icon')) {
                e.stopPropagation();
                this.toggleSectionCollapse(section);
            } else if (e.target.classList.contains('section-header') ||
                       e.target.classList.contains('section-title') ||
                       e.target.classList.contains('section-title-container')) {
                const headerSection = e.target.closest('.section');
                if (headerSection && !e.target.closest('.section-controls')) {
                    this.toggleSectionCollapse(headerSection);
                }
            }
        });

        sectionsList.addEventListener('input', (e) => {
            const section = e.target.closest('.section');
            if (!section) return;

            if (e.target.classList.contains('main-point')) {
                // Update section title immediately as user types
                const sectionTitle = section.querySelector('.section-title');
                const mainPointValue = e.target.value.trim();
                sectionTitle.textContent = mainPointValue || 'New Section';

                // No automatic generation - just update the title
            }
            // Removed automatic generation for user-text changes
        });

        // New Document Modal Event Listeners
        const modal = document.getElementById('new-document-modal');
        const closeModalBtn = document.getElementById('close-new-document-modal');
        const cancelBtn = document.getElementById('cancel-new-document-btn');
        const createBtn = document.getElementById('create-new-document-btn');

        closeModalBtn.addEventListener('click', () => this.hideNewDocumentModal());
        cancelBtn.addEventListener('click', () => this.hideNewDocumentModal());
        createBtn.addEventListener('click', () => this.createNewDocument());

        // Close modal when clicking outside of it
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideNewDocumentModal();
            }
        });
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

    async addSection() {
        try {
            const response = await fetch('/sections', {
                method: 'POST'
            });
            const section = await response.json();
            this.createSectionElement(section);
            this.updateSectionNumbers();
        } catch (error) {
            console.error('Error adding section:', error);
        }
    }

    async insertSection(position) {
        const formData = new FormData();
        formData.append('position', position);

        try {
            const response = await fetch('/sections', {
                method: 'POST',
                body: formData
            });
            const section = await response.json();
            this.createSectionElement(section, position);
            this.updateSectionNumbers();
        } catch (error) {
            console.error('Error inserting section:', error);
        }
    }

    createSectionElement(section, position = null) {
        const sectionsList = document.getElementById('sections-list');
        const noSectionsMessage = sectionsList.querySelector('.no-sections-message');
        if (noSectionsMessage) {
            noSectionsMessage.remove();
        }

        const sectionWrapper = document.createElement('div');
        sectionWrapper.className = 'section-wrapper';

        sectionWrapper.innerHTML = `
            <div class="section" data-section-id="${section.id}" data-order="${section.order}">
                <div class="section-header" data-collapse-target="${section.id}">
                    <div class="section-title-container">
                        <button class="collapse-toggle" title="Expand/Collapse Section">
                            <span class="collapse-icon">▼</span>
                        </button>
                        <span class="section-title">${section.main_point || 'New Section'}</span>
                    </div>
                    <div class="section-controls">
                        <button class="btn btn-small btn-muted insert-above-btn" title="Insert Section Above">+↑</button>
                        <button class="btn btn-small btn-muted insert-below-btn" title="Insert Section Below">+↓</button>
                        <button class="btn btn-small move-up" title="Move Up">↑</button>
                        <button class="btn btn-small move-down" title="Move Down">↓</button>
                        <button class="btn btn-small btn-danger delete-section" title="Delete Section">×</button>
                    </div>
                </div>

                <div class="section-content expanded" data-section-content="${section.id}">
                    <div class="form-group">
                        <label>Main Point (single sentence):</label>
                        <input type="text" class="main-point" placeholder="Enter the main point...">
                    </div>

                    <div class="form-group">
                        <label>Your Text:</label>
                        <textarea class="user-text" rows="4" placeholder="Enter your text here..."></textarea>
                    </div>

                    <div class="form-group">
                        <label>Generated Text:</label>
                        <div class="generated-text-container">
                            <div class="generated-text">${section.generated_text}</div>
                            <div class="loading-indicator" style="display: none;">
                                <span class="loading-spinner">⟳</span>
                                <span class="loading-text">Generating...</span>
                            </div>
                            <div class="generated-text-controls">
                                <button class="btn btn-small btn-primary btn-generate-text" title="Generate new version">⚡ Generate</button>
                                <button class="btn btn-small btn-replace-text" title="Replace 'Your Text' with generated text">← Use This Text</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        if (position !== null && position < sectionsList.children.length) {
            const existingWrappers = Array.from(sectionsList.querySelectorAll('.section-wrapper'));
            if (existingWrappers[position]) {
                sectionsList.insertBefore(sectionWrapper, existingWrappers[position]);
            } else {
                sectionsList.appendChild(sectionWrapper);
            }
        } else {
            sectionsList.appendChild(sectionWrapper);
        }

        // Set values after element is in DOM to avoid triggering input events during creation
        const sectionElement = sectionWrapper.querySelector('.section');
        const mainPointInput = sectionElement.querySelector('.main-point');
        const userTextArea = sectionElement.querySelector('.user-text');

        if (mainPointInput && section.main_point) {
            mainPointInput.value = section.main_point;
        }
        if (userTextArea && section.user_text) {
            userTextArea.value = section.user_text;
        }
    }

    async generateText(sectionElement) {
        const sectionId = sectionElement.dataset.sectionId;
        const generateButton = sectionElement.querySelector('.btn-generate-text');

        // Prevent multiple clicks - check if already generating
        if (generateButton && generateButton.disabled) {
            return;
        }

        // Clear any existing polling for this section first
        if (this.pollingIntervals.has(sectionId)) {
            clearTimeout(this.pollingIntervals.get(sectionId));
            this.pollingIntervals.delete(sectionId);
        }

        const mainPoint = sectionElement.querySelector('.main-point').value;
        const userText = sectionElement.querySelector('.user-text').value;

        // Don't generate if main point is empty
        if (!mainPoint || !mainPoint.trim()) {
            this.showMessage('Please enter a main point before generating text', 'error');
            return;
        }

        // Show loading indicator immediately
        const loadingIndicator = sectionElement.querySelector('.loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'flex';
        }

        // Disable generate button during generation
        if (generateButton) {
            generateButton.disabled = true;
            generateButton.textContent = '⏳ Generating...';
        }

        const formData = new FormData();
        formData.append('main_point', mainPoint);
        formData.append('user_text', userText);

        try {
            const response = await fetch(`/sections/${sectionId}`, {
                method: 'PUT',
                body: formData
            });
            const updatedSection = await response.json();

            const generatedTextDiv = sectionElement.querySelector('.generated-text');
            generatedTextDiv.textContent = updatedSection.generated_text;

            // Poll for the final result
            this.pollForGeneratedText(sectionId, sectionElement);
        } catch (error) {
            console.error('Error generating text:', error);
            // Hide loading indicator on error
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            // Re-enable generate button on error
            if (generateButton) {
                generateButton.disabled = false;
                generateButton.textContent = '⚡ Generate';
            }
        }
    }

    async updateSection(sectionElement) {
        // Legacy method kept for compatibility - now just calls generateText
        return this.generateText(sectionElement);
    }

    async pollForGeneratedText(sectionId, sectionElement) {
        // Clear any existing polling for this section
        if (this.pollingIntervals.has(sectionId)) {
            clearTimeout(this.pollingIntervals.get(sectionId));
            this.pollingIntervals.delete(sectionId);
        }

        const generatedTextDiv = sectionElement.querySelector('.generated-text');
        const loadingIndicator = sectionElement.querySelector('.loading-indicator');

        const maxPolls = 60; // Poll for up to 60 seconds
        let pollCount = 0;
        let lastText = generatedTextDiv.textContent;

        const hideLoadingIndicator = () => {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            // Re-enable generate button
            const generateButton = sectionElement.querySelector('.btn-generate-text');
            if (generateButton) {
                generateButton.disabled = false;
                generateButton.textContent = '⚡ Generate';
            }
        };

        const poll = async () => {
            try {
                const response = await fetch(`/sections/${sectionId}/generated`);
                const data = await response.json();

                if (data.generated_text) {
                    generatedTextDiv.textContent = data.generated_text;
                    lastText = data.generated_text;
                }

                // Only continue polling if still generating
                if (data.is_generating && pollCount < maxPolls) {
                    pollCount++;
                    const timeoutId = setTimeout(poll, 1000); // Poll every 1 second
                    this.pollingIntervals.set(sectionId, timeoutId);
                } else {
                    // Generation complete, clean up immediately
                    hideLoadingIndicator();
                    this.pollingIntervals.delete(sectionId);
                }
            } catch (error) {
                console.error('Error polling for generated text:', error);
                hideLoadingIndicator();
                this.pollingIntervals.delete(sectionId);
            }
        };

        // Start polling after a short delay
        const initialTimeoutId = setTimeout(poll, 1000);
        this.pollingIntervals.set(sectionId, initialTimeoutId);
    }

    async deleteSection(sectionId) {
        if (!confirm('Are you sure you want to delete this section?')) {
            return;
        }

        try {
            await fetch(`/sections/${sectionId}`, {
                method: 'DELETE'
            });
            
            const sectionElement = document.querySelector(`[data-section-id="${sectionId}"]`);
            const sectionWrapper = sectionElement.closest('.section-wrapper');
            sectionWrapper.remove();
            this.updateSectionNumbers();
            
            const remainingSections = document.querySelectorAll('.section-wrapper');
            if (remainingSections.length === 0) {
                const sectionsList = document.getElementById('sections-list');
                const noSectionsDiv = document.createElement('div');
                noSectionsDiv.className = 'no-sections-message';
                noSectionsDiv.innerHTML = '<p>No sections yet. Click "Add Section" to get started.</p>';
                sectionsList.appendChild(noSectionsDiv);
            }
        } catch (error) {
            console.error('Error deleting section:', error);
        }
    }

    async moveSection(sectionElement, direction) {
        const currentOrder = parseInt(sectionElement.dataset.order);
        const sections = Array.from(document.querySelectorAll('.section'));
        const currentIndex = sections.indexOf(sectionElement);
        
        let newIndex;
        if (direction === 'up' && currentIndex > 0) {
            newIndex = currentIndex - 1;
        } else if (direction === 'down' && currentIndex < sections.length - 1) {
            newIndex = currentIndex + 1;
        } else {
            return;
        }

        const sectionId = sectionElement.dataset.sectionId;
        const formData = new FormData();
        formData.append('new_position', newIndex);

        try {
            await fetch(`/sections/${sectionId}/move`, {
                method: 'PUT',
                body: formData
            });

            const sectionsList = document.getElementById('sections-list');
            const sectionWrappers = Array.from(sectionsList.querySelectorAll('.section-wrapper'));
            const currentWrapper = sectionElement.closest('.section-wrapper');
            const currentWrapperIndex = sectionWrappers.indexOf(currentWrapper);
            
            if (direction === 'up' && currentWrapperIndex > 0) {
                const targetWrapper = sectionWrappers[currentWrapperIndex - 1];
                sectionsList.insertBefore(currentWrapper, targetWrapper);
            } else if (direction === 'down' && currentWrapperIndex < sectionWrappers.length - 1) {
                const targetWrapper = sectionWrappers[currentWrapperIndex + 1];
                sectionsList.insertBefore(currentWrapper, targetWrapper.nextSibling);
            }

            this.updateSectionNumbers();
        } catch (error) {
            console.error('Error moving section:', error);
        }
    }

    updateSectionNumbers() {
        const sections = document.querySelectorAll('.section');
        sections.forEach((section, index) => {
            section.dataset.order = index;
        });
    }

    toggleSectionCollapse(section) {
        if (!section) return;

        const content = section.querySelector('.section-content');

        if (!content) {
            console.log('Could not find content element');
            return;
        }

        const isCollapsed = content.classList.contains('collapsed');

        if (isCollapsed) {
            // Expand
            content.classList.remove('collapsed');
            content.classList.add('expanded');
            section.classList.remove('collapsed');
        } else {
            // Collapse
            content.classList.add('collapsed');
            content.classList.remove('expanded');
            section.classList.add('collapsed');
        }
    }

    switchTab(tabName) {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));

        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');
        
        // Load documents list when Documents tab is selected
        if (tabName === 'documents') {
            this.loadDocumentsList();
        }
    }

    async loadMetadata() {
        try {
            // Load from server only
            const response = await fetch('/metadata');
            const metadata = await response.json();
            
            // Load source and model into hamburger menu from localStorage (overriding server values)
            const savedSource = localStorage.getItem('generationSource') || metadata.source || '';
            const savedModel = localStorage.getItem('generationModel') || metadata.model || '';
            
            const sourceElement = document.getElementById('hamburger-source');
            const modelElement = document.getElementById('hamburger-model');
            if (sourceElement) sourceElement.value = savedSource;
            if (modelElement) modelElement.value = savedModel;
            
            // Load other metadata into metadata tab
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
        await this.saveMetadataToServer(true);
    }

    async saveMetadataToServer(showMessage = true) {
        const metadata = this.getMetadataFromForm();

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

            if (showMessage) {
                this.showMessage('Metadata saved successfully!', 'success');
            }
        } catch (error) {
            console.error('Error saving metadata:', error);
            if (showMessage) {
                this.showMessage('Error saving metadata', 'error');
            }
            throw error; // Rethrow the error so saveDocument can handle it
        }
    }

    getMetadataFromForm() {
        // Get source and model from hamburger menu
        const sourceElement = document.getElementById('hamburger-source');
        const modelElement = document.getElementById('hamburger-model');
        
        return {
            source: sourceElement ? sourceElement.value : '',
            model: modelElement ? modelElement.value : '',
            writing_style: document.getElementById('writing-style').value,
            target_audience: document.getElementById('target-audience').value,
            tone: document.getElementById('tone').value,
            background_context: document.getElementById('background-context').value,
            generation_directive: document.getElementById('generation-directive').value,
            word_limit: document.getElementById('word-limit').value || null
        };
    }

    async resetMetadata() {
        // Reset hamburger menu fields
        const sourceElement = document.getElementById('hamburger-source');
        const modelElement = document.getElementById('hamburger-model');
        if (sourceElement) sourceElement.value = '';
        if (modelElement) modelElement.value = '';
        
        // Reset metadata tab fields
        document.getElementById('writing-style').value = 'formal';
        document.getElementById('target-audience').value = '';
        document.getElementById('tone').value = 'neutral';
        document.getElementById('background-context').value = '';
        document.getElementById('generation-directive').value = '';
        document.getElementById('word-limit').value = '';

        await this.saveMetadataToServer(false);
    }


    showMessage(text, type) {
        const existingMessage = document.querySelector('.message');
        if (existingMessage) {
            existingMessage.remove();
        }

        const message = document.createElement('div');
        message.className = `message message-${type}`;
        message.textContent = text;
        
        const container = document.querySelector('.container');
        container.insertBefore(message, container.firstChild);
        
        setTimeout(() => {
            message.remove();
        }, 3000);
    }


    async saveDocument() {
        const filename = document.getElementById('save-filename').value.trim();
        if (!filename) {
            this.showMessage('Please enter a filename', 'error');
            return;
        }

        try {
            // First, save the current metadata to ensure it's up to date (without regenerating)
            await this.saveMetadataToServer(false);
            
            const formData = new FormData();
            formData.append('filename', filename);

            const response = await fetch('/documents/save', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Document saved as ${result.filename}`, 'success');
                document.getElementById('save-filename').value = '';
                this.loadDocumentsList();
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
            const response = await fetch('/metadata');
            const metadata = await response.json();
            
            const documentData = {
                title: document.getElementById('document-title').value,
                sections: [],
                metadata: metadata,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            // Get current sections
            const sections = document.querySelectorAll('.section');
            sections.forEach((section, index) => {
                documentData.sections.push({
                    id: section.dataset.sectionId,
                    main_point: section.querySelector('.main-point').value,
                    user_text: section.querySelector('.user-text').value,
                    generated_text: section.querySelector('.generated-text').textContent,
                    order: index
                });
            });

            const blob = new Blob([JSON.stringify(documentData, null, 2)], {
                type: 'application/json'
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = (documentData.title || 'document') + '.json';
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

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            const response = await fetch('/documents/load', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage('Document loaded successfully', 'success');
                // Reload the page to reflect the loaded document
                window.location.reload();
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
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
        try {
            const response = await fetch('/documents/list');
            const result = await response.json();
            
            const listContainer = document.getElementById('documents-list');
            
            if (result.error) {
                listContainer.innerHTML = `<p class="error">Error loading documents: ${result.error}</p>`;
                return;
            }

            if (result.files.length === 0) {
                listContainer.innerHTML = '<p class="no-documents">No saved documents found.</p>';
                return;
            }

            listContainer.innerHTML = result.files.map(file => `
                <div class="document-item">
                    <div class="document-info">
                        <span class="document-name">${file.filename}</span>
                        <span class="document-date">${new Date(file.modified).toLocaleDateString()}</span>
                        <span class="document-size">${this.formatFileSize(file.size)}</span>
                    </div>
                    <div class="document-actions">
                        <button class="btn btn-small btn-primary" onclick="writingAssistant.loadSavedDocument('${file.filename}')">Load</button>
                        <button class="btn btn-small" onclick="writingAssistant.downloadSavedDocument('${file.filename}')">Download</button>
                        <button class="btn btn-small btn-danger" onclick="writingAssistant.deleteSavedDocument('${file.filename}')">Delete</button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading documents list:', error);
            document.getElementById('documents-list').innerHTML = '<p class="error">Error loading documents list</p>';
        }
    }

    async downloadSavedDocument(filename) {
        try {
            const response = await fetch(`/documents/download/${filename}`);
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } else {
                this.showMessage('Error downloading file', 'error');
            }
        } catch (error) {
            console.error('Error downloading document:', error);
            this.showMessage('Error downloading document', 'error');
        }
    }

    async loadSavedDocument(filename) {
        if (!confirm(`Load "${filename}"? This will replace the current document.`)) {
            return;
        }

        try {
            const response = await fetch(`/documents/load/${filename}`, {
                method: 'POST'
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage(`Document "${result.title || filename}" loaded successfully`, 'success');
                // Reload the page to reflect the loaded document
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error loading document:', error);
            this.showMessage('Error loading document', 'error');
        }
    }

    async deleteSavedDocument(filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/documents/${filename}`, {
                method: 'DELETE'
            });
            const result = await response.json();

            if (result.status === 'success') {
                this.showMessage('Document deleted', 'success');
                this.loadDocumentsList();
            } else {
                this.showMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            this.showMessage('Error deleting document', 'error');
        }
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
        return Math.round(bytes / (1024 * 1024)) + ' MB';
    }

    setupHamburgerMenu() {
        const hamburgerBtn = document.getElementById('hamburger-btn');
        const hamburgerDropdown = document.getElementById('hamburger-dropdown');
        const saveGenerationSettingsBtn = document.getElementById('save-generation-settings-btn');

        if (hamburgerBtn && hamburgerDropdown) {
            hamburgerBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                hamburgerBtn.classList.toggle('active');
                hamburgerDropdown.classList.toggle('show');
            });

            document.addEventListener('click', (e) => {
                if (!hamburgerDropdown.contains(e.target) && !hamburgerBtn.contains(e.target)) {
                    hamburgerBtn.classList.remove('active');
                    hamburgerDropdown.classList.remove('show');
                }
            });
        }

        if (saveGenerationSettingsBtn) {
            saveGenerationSettingsBtn.addEventListener('click', () => this.saveGenerationSettings());
        }

        this.loadGenerationSettings();
    }

    saveGenerationSettings() {
        const source = document.getElementById('hamburger-source').value;
        const model = document.getElementById('hamburger-model').value;

        localStorage.setItem('generationSource', source);
        localStorage.setItem('generationModel', model);

        const sourceField = document.querySelector('input[name="source"]');
        const modelField = document.querySelector('input[name="model"]');
        
        if (sourceField) sourceField.value = source;
        if (modelField) modelField.value = model;

        this.showMessage('Generation settings saved successfully!', 'success');

        const hamburgerBtn = document.getElementById('hamburger-btn');
        const hamburgerDropdown = document.getElementById('hamburger-dropdown');
        hamburgerBtn.classList.remove('active');
        hamburgerDropdown.classList.remove('show');
    }

    loadGenerationSettings() {
        const savedSource = localStorage.getItem('generationSource') || '';
        const savedModel = localStorage.getItem('generationModel') || '';

        const hamburgerSource = document.getElementById('hamburger-source');
        const hamburgerModel = document.getElementById('hamburger-model');

        if (hamburgerSource) hamburgerSource.value = savedSource;
        if (hamburgerModel) hamburgerModel.value = savedModel;

        const sourceField = document.querySelector('input[name="source"]');
        const modelField = document.querySelector('input[name="model"]');
        
        if (sourceField) sourceField.value = savedSource;
        if (modelField) modelField.value = savedModel;
    }

    replaceUserText(section) {
        const generatedTextDiv = section.querySelector('.generated-text');
        const userTextArea = section.querySelector('.user-text');

        if (generatedTextDiv && userTextArea) {
            const generatedText = generatedTextDiv.textContent.trim();

            if (generatedText) {
                userTextArea.value = generatedText;

                // No automatic generation - just replace the text
                this.showMessage('Text replaced successfully!', 'success');
            } else {
                this.showMessage('No generated text to replace with.', 'error');
            }
        }
    }

    async copyDocumentToClipboard() {
        try {
            const titleInput = document.getElementById('document-title');
            const title = titleInput.value.trim();
            
            const sections = document.querySelectorAll('.section');
            const sectionTexts = [];
            
            sections.forEach((section) => {
                const userTextArea = section.querySelector('.user-text');
                if (userTextArea && userTextArea.value.trim()) {
                    sectionTexts.push(userTextArea.value.trim());
                }
            });
            
            let documentText = '';
            
            if (title) {
                documentText += title + '\n\n';
            }
            
            if (sectionTexts.length > 0) {
                documentText += sectionTexts.join('\n\n');
            } else {
                documentText += '(No content in sections)';
            }
            
            await navigator.clipboard.writeText(documentText);
            this.showMessage('Document copied to clipboard!', 'success');
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            
            try {
                const titleInput = document.getElementById('document-title');
                const title = titleInput.value.trim();
                
                const sections = document.querySelectorAll('.section');
                const sectionTexts = [];
                
                sections.forEach((section) => {
                    const userTextArea = section.querySelector('.user-text');
                    if (userTextArea && userTextArea.value.trim()) {
                        sectionTexts.push(userTextArea.value.trim());
                    }
                });
                
                let documentText = '';
                
                if (title) {
                    documentText += title + '\n\n';
                }
                
                if (sectionTexts.length > 0) {
                    documentText += sectionTexts.join('\n\n');
                } else {
                    documentText += '(No content in sections)';
                }
                
                const textArea = document.createElement('textarea');
                textArea.value = documentText;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                this.showMessage('Document copied to clipboard!', 'success');
            } catch (fallbackError) {
                console.error('Fallback copy also failed:', fallbackError);
                this.showMessage('Failed to copy to clipboard. Please try again.', 'error');
            }
        }
    }

    showNewDocumentModal() {
        const modal = document.getElementById('new-document-modal');
        modal.classList.add('show');
        
        // Clear previous values
        document.getElementById('new-document-title').value = '';
        document.getElementById('new-document-outline').value = '';
        
        // Focus on title field
        document.getElementById('new-document-title').focus();
    }

    hideNewDocumentModal() {
        const modal = document.getElementById('new-document-modal');
        modal.classList.remove('show');
    }

    async createNewDocument() {
        const title = document.getElementById('new-document-title').value.trim();
        const outline = document.getElementById('new-document-outline').value.trim();

        if (!title && !outline) {
            this.showMessage('Please provide either a title or section outline.', 'error');
            return;
        }

        try {
            // First, clear the current document by setting title to empty
            const titleInput = document.getElementById('document-title');
            titleInput.value = title;
            await this.updateTitle(title);

            // Clear all existing sections from frontend
            const sectionsList = document.getElementById('sections-list');

            // Cancel any ongoing polling for existing sections
            this.pollingIntervals.forEach((timeoutId, sectionId) => {
                clearTimeout(timeoutId);
            });
            this.pollingIntervals.clear();

            sectionsList.innerHTML = '<div class="no-sections-message"><p>No sections yet. Click "Add Section" to get started.</p></div>';

            // Clear backend document state
            await fetch('/documents/clear', { method: 'POST' });

            // Create sections from outline
            if (outline) {
                const lines = outline.split('\n').filter(line => line.trim());
                for (const line of lines) {
                    const response = await fetch('/sections', {
                        method: 'POST'
                    });
                    const section = await response.json();
                    
                    // Update the section with the main point (data only, no generation)
                    const formData = new FormData();
                    formData.append('main_point', line.trim());
                    formData.append('user_text', '');

                    await fetch(`/sections/${section.id}`, {
                        method: 'PATCH',
                        body: formData
                    });
                    
                    // Create the section element with updated data
                    const updatedSection = {...section, main_point: line.trim()};
                    this.createSectionElement(updatedSection);
                }
                
                this.updateSectionNumbers();
            }

            this.hideNewDocumentModal();
            this.showMessage('New document created successfully!', 'success');
            
        } catch (error) {
            console.error('Error creating new document:', error);
            this.showMessage('Error creating new document. Please try again.', 'error');
        }
    }

    initializeExistingSections() {
        // Initialize any sections that were already on the page when loaded
        const existingSections = document.querySelectorAll('.section');
        existingSections.forEach(section => {
            const mainPointInput = section.querySelector('.main-point');
            const sectionTitle = section.querySelector('.section-title');

            if (mainPointInput && sectionTitle) {
                // Set initial title from main point value
                const mainPointValue = mainPointInput.value.trim();
                sectionTitle.textContent = mainPointValue || 'New Section';

                // Make sure content starts expanded
                const content = section.querySelector('.section-content');
                if (content) {
                    content.classList.add('expanded');
                    content.classList.remove('collapsed');
                }
            }
        });
    }

    expandAllSections() {
        const sections = document.querySelectorAll('.section');
        sections.forEach(section => {
            const content = section.querySelector('.section-content');
            if (content && content.classList.contains('collapsed')) {
                this.toggleSectionCollapse(section);
            }
        });
    }

    collapseAllSections() {
        const sections = document.querySelectorAll('.section');
        sections.forEach(section => {
            const content = section.querySelector('.section-content');
            if (content && !content.classList.contains('collapsed')) {
                this.toggleSectionCollapse(section);
            }
        });
    }
}

// Global reference for onclick handlers
let writingAssistant;

document.addEventListener('DOMContentLoaded', () => {
    writingAssistant = new WritingAssistant();
});