(function() {
  'use strict';

  // ==================== Phrase Reading Controller ====================
  // Handles the "Secret Messages" Phrase Reading experience
  // Integrates with the shared assessment_reader.js for speech/evaluation logic
  
  const PHRASE_TOTAL = 10;
  const PHRASES_PER_ROW = 5;

  class PhraseReadingManager {
    constructor() {
      this.app = document.getElementById('phraseReadingApp');
      if (!this.app) {
        console.error('Phrase Reading: #phraseReadingApp not found');
        return;
      }

      // Core state
      this.phrases = [];
      this.completedPhrases = new Set();
      this.currentPhraseIndex = null;
      this.currentPhrase = null;
      this.selectedPhrase = null;
      this.activityMarkedComplete = false;
      this.activityStateKey = 'phrase-reading-default';

      // DOM references
      this.envelopeBoard = document.getElementById('phraseEnvelopeBoard');
      this.envelopeScene = document.getElementById('phraseEnvelopeScene');
      this.messageView = document.getElementById('phraseMessageView');
      this.messageClose = document.getElementById('phraseMessageClose');
      this.completionPage = document.getElementById('completionPage');
      this.progressCount = document.getElementById('phraseProgressCount');
      this.progressFill = document.getElementById('progressFill');
      this.readingWord = document.getElementById('readingWord');
      this.counter = document.getElementById('counter');
      this.readingHelperText = document.getElementById('readingHelperText');

      // Control buttons for speech
      this.btnReadAloud = document.getElementById('btnReadAloud');
      this.btnStartReading = document.getElementById('btnStartReading');
      this.btnStopReading = document.getElementById('btnStopReading');
      this.reviewBtn = document.getElementById('reviewBtn');
      this.finishBtn = document.getElementById('finishBtn');

      // Asset stamps
      this.stampAssets = window.__PHRASE_READING_ASSETS__?.stamps || [];

      // Initialize
      this._init();
    }

    _init() {
      try {
        // Load phrase data from backend context
        this._loadPhraseData();
        
        // Restore completion state from storage
        this._restoreCompletionState();
        
        // Render the envelope board
        this._renderEnvelopeBoard();
        
        // Setup event listeners
        this._setupEventListeners();
        
        // Update progress display
        this._updateProgress();
        
        console.log('Phrase Reading initialized', {
          totalPhrases: this.phrases.length,
          completed: this.completedPhrases.size,
          phrases: this.phrases.slice(0, 3),
        });
      } catch (error) {
        console.error('Phrase Reading initialization error:', error);
      }
    }

    _loadPhraseData() {
      const contextData = window.__PABASA_CUSTOM_MATERIAL__ || {};
      const nestedContentJson = contextData.content_json || {};
      const phraseReadingConfig = nestedContentJson.phraseReading || {};
      const activityIdentity = contextData.id || contextData.raw_id || contextData.code
        || phraseReadingConfig.setKey || contextData.title || 'default';
      this.activityStateKey = `phrase-reading-${String(activityIdentity).trim()}`;
      const readingCandidates = [
        contextData.reading_items,
        contextData.items,
        nestedContentJson.items,
      ].filter(Array.isArray);

      const normalizeText = (item) => {
        if (item === null || item === undefined) return '';
        if (typeof item === 'string') return item.trim();
        if (typeof item === 'object') {
          return String(
            item.phrase ||
            item.text ||
            item.content ||
            item.title ||
            item.sentence ||
            item.paragraph ||
            item.word ||
            ''
          ).trim();
        }
        return String(item).trim();
      };

      const phraseTexts = [];
      const seen = new Set();

      readingCandidates.forEach((list) => {
        list.forEach((item) => {
          const text = normalizeText(item);
          if (!text || seen.has(text)) return;
          const itemType = typeof item === 'object' && item ? String(item.type || item.item_type || '').toLowerCase() : '';
          if (itemType && itemType !== 'phrase' && itemType !== 'sentence' && itemType !== 'paragraph') {
            return;
          }
          seen.add(text);
          phraseTexts.push(text);
        });
      });

      if (!phraseTexts.length && typeof contextData.content === 'string') {
        const splitLines = contextData.content
          .split(/\r?\n/)
          .map(line => line.trim())
          .filter(Boolean);
        splitLines.forEach((line) => {
          if (!seen.has(line)) {
            seen.add(line);
            phraseTexts.push(line);
          }
        });
      }

      this.phrases = phraseTexts
        .slice(0, PHRASE_TOTAL)
        .map((text, index) => ({
          id: `phrase-${index}`,
          index,
          text,
          language: contextData.language || 'English',
          order: index,
        }));

      if (this.phrases.length < PHRASE_TOTAL) {
        const fallbackText = 'Phrase item not available';
        while (this.phrases.length < PHRASE_TOTAL) {
          this.phrases.push({
            id: `phrase-${this.phrases.length}`,
            index: this.phrases.length,
            text: fallbackText,
            language: contextData.language || 'English',
            order: this.phrases.length,
          });
        }
      }

      console.log('Loaded phrases:', this.phrases);
    }

    _restoreCompletionState() {
      const normalizeIndexes = (value) => {
        if (!Array.isArray(value)) return [];
        return value
          .map((entry) => Number(entry))
          .filter((entry) => Number.isInteger(entry) && entry >= 0 && entry < PHRASE_TOTAL);
      };

      let storedCompleted = [];
      try {
        const stored = sessionStorage.getItem(`phraseReadingState:${this.activityStateKey}`);
        if (stored) {
          const state = JSON.parse(stored);
          if (state.activity_id === this.activityStateKey) {
            storedCompleted = normalizeIndexes(state.completed_phrases || state.completed || []);
          }
        }
      } catch (e) {
        console.warn('Could not restore completion state from storage:', e);
      }

      this.completedPhrases = new Set(storedCompleted);
    }

    _renderEnvelopeBoard() {
      if (!this.envelopeBoard) return;
      
      this.envelopeBoard.innerHTML = '';
      
      this.phrases.forEach((phrase, index) => {
        const envelope = document.createElement('button');
        envelope.type = 'button';
        envelope.className = 'phrase-envelope';
        envelope.id = `envelope-${index}`;
        envelope.dataset.phraseIndex = index;
        
        if (this.completedPhrases.has(index)) {
          envelope.classList.add('is-complete');
        }
        
        // Build envelope HTML structure
        const stampAsset = this.stampAssets[index] || this.stampAssets[0];
        envelope.innerHTML = `
          <span class="phrase-envelope-back" aria-hidden="true"></span>
          <span class="phrase-envelope-front" aria-hidden="true"></span>
          <span class="phrase-envelope-flap" aria-hidden="true"></span>
          ${stampAsset ? `<img class="phrase-envelope-stamp stamp-${index + 1}" src="${stampAsset}" alt="" aria-hidden="true">` : ''}
          <span class="phrase-envelope-number" aria-hidden="true">${index + 1}</span>
          ${this.completedPhrases.has(index) ? '<span class="phrase-envelope-check" aria-hidden="true">✓</span>' : ''}
        `;
        
        envelope.addEventListener('click', () => this._selectEnvelope(index));
        envelope.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            this._selectEnvelope(index);
          }
        });
        
        this.envelopeBoard.appendChild(envelope);
      });
    }

    _selectEnvelope(index) {
      if (!Number.isInteger(index) || index < 0 || index >= this.phrases.length) {
        return;
      }

      this.currentPhraseIndex = index;
      this.currentPhrase = this.phrases[index];
      this.selectedPhrase = {
        ...this.currentPhrase,
        sourceIndex: index,
        sourceId: this.currentPhrase.id || `phrase-${index}`,
        selectedAt: Date.now(),
      };
      window.__PABASA_SELECTED_PHRASE__ = this.selectedPhrase;
      window.__PABASA_SELECTED_READING_ITEM__ = this.selectedPhrase;
      window.__PABASA_CURRENT_PHRASE_INDEX__ = index;

      console.log('Envelope selected and stored', {
        envelopeId: `envelope-${index}`,
        phraseIndex: index,
        phraseId: this.selectedPhrase.sourceId,
        phraseText: this.selectedPhrase.text,
      });

      const envelope = document.getElementById(`envelope-${index}`);
      if (envelope && !this.completedPhrases.has(index)) {
        envelope.classList.add('is-opening');
      }

      this._showMessageView();
      
      // Update counter and phrase text
      this.counter.textContent = `Message ${index + 1} / ${PHRASE_TOTAL}`;
      this.readingWord.textContent = this.currentPhrase.text;
      
      // Reset the helper text for the new phrase
      this.readingHelperText.textContent = 'Read the message aloud.';
      
      // Show the speech control buttons
      this.btnReadAloud?.classList.remove('d-none');
      this.btnStartReading?.classList.remove('d-none');
      this.btnStopReading?.classList.add('d-none');
      
      // Mute the envelope scene while message is open
      this.envelopeScene?.classList.add('is-muted');
      
      // Trigger phrase reading mode in shared reader
      // This will set up speech recognition to evaluate the phrase
      this._initiatePhraseEvaluation();
    }

    _showMessageView() {
      if (!this.messageView) return;
      this.messageView.classList.add('is-visible');
      this.messageView.setAttribute('aria-hidden', 'false');
    }

    _hideMessageView() {
      if (!this.messageView) return;
      this.messageView.classList.remove('is-visible');
      this.messageView.setAttribute('aria-hidden', 'true');
      
      // Unmute the envelope scene
      this.envelopeScene?.classList.remove('is-muted');
    }

    _initiatePhraseEvaluation() {
      const selectedPhrase = this.selectedPhrase || this.currentPhrase;
      if (!selectedPhrase) return;

      window.__PABASA_READING_MODE__ = 'phrase';
      window.__PABASA_CURRENT_PHRASE_INDEX__ = this.currentPhraseIndex;
      window.__PABASA_SELECTED_PHRASE__ = selectedPhrase;
      window.__PABASA_SELECTED_READING_ITEM__ = selectedPhrase;

      const event = new CustomEvent('phraseReadingStarted', {
        detail: {
          phraseIndex: this.currentPhraseIndex,
          phraseId: selectedPhrase.sourceId || selectedPhrase.id || `phrase-${this.currentPhraseIndex}`,
          phraseText: selectedPhrase.text,
          phrase: selectedPhrase,
          language: selectedPhrase.language,
        },
      });
      document.dispatchEvent(event);

      console.log('Phrase evaluation initiated:', {
        envelopeId: `envelope-${this.currentPhraseIndex}`,
        phraseIndex: this.currentPhraseIndex,
        phraseId: selectedPhrase.sourceId || selectedPhrase.id || `phrase-${this.currentPhraseIndex}`,
        phraseText: selectedPhrase.text,
      });
    }

    _markPhraseComplete(index) {
      if (!Number.isInteger(index) || index < 0 || index >= PHRASE_TOTAL) return;
      if (this.completedPhrases.has(index)) return;

      this.completedPhrases.add(index);

      const envelope = document.getElementById(`envelope-${index}`);
      if (envelope) {
        envelope.classList.add('is-complete');
        if (!envelope.querySelector('.phrase-envelope-check')) {
          const check = document.createElement('span');
          check.className = 'phrase-envelope-check';
          check.setAttribute('aria-hidden', 'true');
          check.textContent = '✓';
          envelope.appendChild(check);
        }
      }

      this._persistCompletionState();
      this._updateProgress();

      if (this.completedPhrases.size === PHRASE_TOTAL) {
        this._showCompletionPage();
        this._notifyActivityCompletion();
      }
    }

    _updateProgress() {
      const completed = this.completedPhrases.size;
      const percentage = (completed / PHRASE_TOTAL) * 100;

      if (this.progressCount) {
        this.progressCount.textContent = `${completed} / ${PHRASE_TOTAL}`;
      }

      if (this.progressFill) {
        this.progressFill.style.width = `${percentage}%`;
      }

      // Only completed phrase items should affect progress. Opening or previewing
      // a message should never update the student's reading count.
      const message = `${completed} of ${PHRASE_TOTAL} messages read`;
      const liveRegion = this.messageView?.querySelector('[role="status"]');
      if (liveRegion) {
        liveRegion.textContent = message;
      }
    }

    _notifyActivityCompletion() {
      if (this.activityMarkedComplete) return;
      this.activityMarkedComplete = true;

      const detail = {
        assessmentType: 'phrase',
        totalScore: 100,
        completedCount: this.completedPhrases.size,
        completedPhrases: Array.from(this.completedPhrases).sort((a, b) => a - b),
      };

      window.dispatchEvent(new CustomEvent('pabasa:assessment-completed', { detail }));
      document.dispatchEvent(new CustomEvent('phraseReadingComplete', { detail }));
    }

    _persistCompletionState() {
      try {
        const completed = Array.from(this.completedPhrases).sort((a, b) => a - b);
        const state = {
          activity_id: this.activityStateKey,
          completed,
          completed_phrases: completed,
          count: completed.length,
          total: PHRASE_TOTAL,
          finished: completed.length >= PHRASE_TOTAL,
          timestamp: new Date().toISOString(),
        };

        sessionStorage.setItem(`phraseReadingState:${this.activityStateKey}`, JSON.stringify(state));

        const existingPhraseState = window.__PABASA_STUDENT_END_STATE__?.phrase_reading || {};
        window.__PABASA_STUDENT_END_STATE__ = {
          ...(window.__PABASA_STUDENT_END_STATE__ || {}),
          phrase_reading: {
            ...existingPhraseState,
            [this.activityStateKey]: {
              completed_phrases: completed,
              completed_count: completed.length,
              activity_complete: completed.length >= PHRASE_TOTAL,
              updated_at: new Date().toISOString(),
            },
          },
        };
      } catch (e) {
        console.warn('Could not persist completion state:', e);
      }
    }

    _showCompletionPage() {
      if (!this.completionPage) return;
      
      // Hide the message and envelope views
      this._hideMessageView();
      this.envelopeScene?.classList.add('is-muted');
      
      // Show the completion page
      this.app?.classList.add('is-complete');
      
      // Set up completion screen text
      const completionTitle = this.completionPage.querySelector('#completionTitle');
      const completionMessage = this.completionPage.querySelector('#completionMessage');
      
      if (completionTitle) {
        completionTitle.textContent = 'Secret messages complete!';
      }
      if (completionMessage) {
        completionMessage.textContent = 'Wonderful reading—you opened every magical message.';
      }
      
      // Setup completion action buttons
      if (this.reviewBtn) {
        this.reviewBtn.addEventListener('click', () => this._restartPhraseReading());
      }
      if (this.finishBtn) {
        this.finishBtn.addEventListener('click', () => this._returnToAssessment());
      }
    }

    _restartPhraseReading() {
      this.completedPhrases.clear();
      this.activityMarkedComplete = false;
      this._persistCompletionState();
      this.app?.classList.remove('is-complete');
      this._hideMessageView();
      this.envelopeScene?.classList.remove('is-muted');
      this._renderEnvelopeBoard();
      this._updateProgress();
    }

    _returnToAssessment() {
      // Navigate back to assessment dashboard
      window.location.href = '/dashboard/assessment/';
    }

    _setupEventListeners() {
      // Close button for message view
      if (this.messageClose) {
        this.messageClose.addEventListener('click', () => this._closeMessageView());
      }
      
      // Listen for phrase completion from shared reader
      document.addEventListener('phraseReadingCompleted', (event) => {
        const { phraseIndex } = event.detail;
        console.log('Phrase reading completed event:', phraseIndex);
        this._markPhraseComplete(phraseIndex);
      });
      
      // Listen for evaluation errors
      document.addEventListener('phraseReadingError', (event) => {
        const { error } = event.detail;
        console.error('Phrase reading error:', error);
        this.readingHelperText.textContent = 'There was an issue. Please try again.';
      });
    }

    _closeMessageView() {
      // Close without marking as complete
      // Return to envelope board
      this._hideMessageView();
      this.envelopeScene?.classList.remove('is-muted');
      
      // Remove opening state from envelope
      if (this.currentPhraseIndex !== null) {
        const envelope = document.getElementById(`envelope-${this.currentPhraseIndex}`);
        if (envelope) {
          envelope.classList.remove('is-opening');
        }
      }
      
      this.currentPhraseIndex = null;
      this.currentPhrase = null;
      
      // Dispatch event to stop any ongoing speech recognition
      document.dispatchEvent(new CustomEvent('phraseReadingStopped'));
    }

    // External API for shared reader to call when phrase is complete
    markPhraseComplete(index) {
      this._markPhraseComplete(index);
    }
  }

  // ==================== Bridge: Connect Shared Reader to Phrase Manager ====================
  // Monitors the assessment_reader.js for phrase completion and evaluation results
  
  class PhraseReaderBridge {
    constructor(manager) {
      this.manager = manager;
      this.isListening = false;
      this.completionThreshold = 0.70; // 70% accuracy to mark as complete
      this.setupListeners();
    }

    setupListeners() {
      // Listen for successful phrase evaluation from shared reader
      // The shared reader will dispatch custom events when speech is evaluated
      this.setupCustomEventListeners();
    }

    setupCustomEventListeners() {
      // Listen only for completion explicitly reported by the shared evaluator.
      document.addEventListener('phraseReadingCompleted', (event) => {
        const phraseIndex = event.detail?.phraseIndex ?? window.__PABASA_CURRENT_PHRASE_INDEX__;
        if (phraseIndex === null || phraseIndex === undefined) return;
        this.manager.markPhraseComplete(phraseIndex);
        this._closeAndReturnToBoard();
      });
    }

    _closeAndReturnToBoard() {
      // Trigger the close button to return to board
      const closeBtn = document.getElementById('phraseMessageClose');
      if (closeBtn) {
        closeBtn.click();
      }
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.phraseReadingManager = new PhraseReadingManager();
      // Connect the bridge after manager is initialized
      setTimeout(() => {
        window.phraseReaderBridge = new PhraseReaderBridge(window.phraseReadingManager);
      }, 100);
    });
  } else {
    window.phraseReadingManager = new PhraseReadingManager();
    setTimeout(() => {
      window.phraseReaderBridge = new PhraseReaderBridge(window.phraseReadingManager);
    }, 100);
  }
})();
