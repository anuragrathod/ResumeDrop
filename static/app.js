/**
 * static/app.js
 * ResumeDrop — Client Controller
 * Pure Vanilla JavaScript: 2-view navigation, drag-and-drop file queue,
 * live SSE progress bar, candidate table & inspection modal, and API logs monitor.
 */

(() => {
    'use strict';

    // State
    const state = {
        queuedFiles: [],
        candidates: [],
        currentView: 'home',
        isProcessing: false,
        eventSource: null,
    };

    // DOM Elements
    const elements = {
        brandLink: document.getElementById('brand-link'),
        tabHome: document.getElementById('tab-home'),
        tabLogs: document.getElementById('tab-logs'),
        viewHome: document.getElementById('view-home'),
        viewLogs: document.getElementById('view-logs'),
        btnExportExcel: document.getElementById('btn-export-excel'),

        // Upload & Queue
        dropzone: document.getElementById('dropzone'),
        fileInput: document.getElementById('file-input'),
        queueContainer: document.getElementById('queue-container'),
        queueList: document.getElementById('queue-list'),
        queueSummary: document.getElementById('queue-summary'),
        btnClearQueue: document.getElementById('btn-clear-queue'),
        btnExtract: document.getElementById('btn-extract'),

        // Real Load Bar
        progressCard: document.getElementById('progress-card'),
        progressLabel: document.getElementById('progress-label'),
        progressStats: document.getElementById('progress-stats'),
        progressBar: document.getElementById('progress-bar'),
        progressFilename: document.getElementById('progress-filename'),

        // Candidates Table
        candidateCount: document.getElementById('candidate-count'),
        candidateTbody: document.getElementById('candidate-tbody'),

        // Logs
        btnCheckConnection: document.getElementById('btn-check-connection'),
        btnRefreshLogs: document.getElementById('btn-refresh-logs'),
        btnClearLogs: document.getElementById('btn-clear-logs'),
        connectionAlertContainer: document.getElementById('connection-alert-container'),
        logCount: document.getElementById('log-count'),
        logsTbody: document.getElementById('logs-tbody'),

        // Modal
        modalOverlay: document.getElementById('modal-overlay'),
        modalCloseBtn: document.getElementById('modal-close-btn'),
        modalCandidateName: document.getElementById('modal-candidate-name'),
        modalCandidateBody: document.getElementById('modal-candidate-body'),
    };

    // -------------------------------------------------------------------------
    // 1. Navigation & Routing (Home & API Logs)
    // -------------------------------------------------------------------------
    function setView(viewName, pushHistory = true) {
        state.currentView = viewName;

        if (viewName === 'logs') {
            elements.tabHome.classList.remove('active');
            elements.tabHome.setAttribute('aria-selected', 'false');
            elements.tabLogs.classList.add('active');
            elements.tabLogs.setAttribute('aria-selected', 'true');

            elements.viewHome.classList.remove('active');
            elements.viewLogs.classList.add('active');

            if (pushHistory && window.location.pathname !== '/logs') {
                window.history.pushState({ view: 'logs' }, '', '/logs');
            }
            loadLogs();
        } else {
            elements.tabLogs.classList.remove('active');
            elements.tabLogs.setAttribute('aria-selected', 'false');
            elements.tabHome.classList.add('active');
            elements.tabHome.setAttribute('aria-selected', 'true');

            elements.viewLogs.classList.remove('active');
            elements.viewHome.classList.add('active');

            if (pushHistory && window.location.pathname !== '/') {
                window.history.pushState({ view: 'home' }, '', '/');
            }
        }
    }

    elements.tabHome.addEventListener('click', () => setView('home'));
    elements.tabLogs.addEventListener('click', () => setView('logs'));
    elements.brandLink.addEventListener('click', () => setView('home'));

    window.addEventListener('popstate', () => {
        const path = window.location.pathname;
        setView(path === '/logs' ? 'logs' : 'home', false);
    });

    // Initial route check on page load
    if (window.location.pathname === '/logs') {
        setView('logs', false);
    } else {
        setView('home', false);
    }

    // -------------------------------------------------------------------------
    // 2. Drag & Drop File Upload Queue
    // -------------------------------------------------------------------------
    const ALLOWED_EXTS = ['.pdf', '.docx', '.txt'];

    function isAllowedFile(filename) {
        const lower = filename.toLowerCase();
        return ALLOWED_EXTS.some(ext => lower.endsWith(ext));
    }

    function addFiles(files) {
        let addedCount = 0;
        for (const file of files) {
            if (!isAllowedFile(file.name)) continue;
            // Prevent duplicate file names in queue
            if (!state.queuedFiles.some(f => f.name === file.name && f.size === file.size)) {
                state.queuedFiles.push(file);
                addedCount++;
            }
        }
        renderQueue();
    }

    function removeFile(index) {
        if (state.isProcessing) return;
        state.queuedFiles.splice(index, 1);
        renderQueue();
    }

    function clearQueue() {
        if (state.isProcessing) return;
        state.queuedFiles = [];
        elements.fileInput.value = '';
        renderQueue();
    }

    function renderQueue() {
        const count = state.queuedFiles.length;
        elements.queueSummary.textContent = `${count} ${count === 1 ? 'file' : 'files'} queued`;

        if (count === 0) {
            elements.queueContainer.style.display = 'none';
            elements.queueList.innerHTML = '';
            elements.btnClearQueue.disabled = true;
            elements.btnExtract.disabled = true;
            return;
        }

        elements.queueContainer.style.display = 'block';
        elements.btnClearQueue.disabled = state.isProcessing;
        elements.btnExtract.disabled = state.isProcessing;

        elements.queueList.innerHTML = state.queuedFiles.map((file, idx) => `
            <div class="rd-queue-item">
                <span>📄 ${escapeHtml(file.name)}</span>
                <span style="color: var(--muted); font-size: 0.75rem;">(${(file.size / 1024).toFixed(0)} KB)</span>
                <button type="button" class="rd-queue-remove" onclick="window.__removeFile(${idx})" title="Remove file" ${state.isProcessing ? 'disabled' : ''}>&times;</button>
            </div>
        `).join('');
    }

    window.__removeFile = removeFile;

    // File Input change
    elements.fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            addFiles(e.target.files);
        }
    });

    // Drag and Drop Events
    ['dragenter', 'dragover'].forEach(eventName => {
        elements.dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            elements.dropzone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        elements.dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            elements.dropzone.classList.remove('drag-over');
        });
    });

    elements.dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        if (dt && dt.files && dt.files.length > 0) {
            addFiles(dt.files);
        }
    });

    elements.btnClearQueue.addEventListener('click', clearQueue);

    // -------------------------------------------------------------------------
    // 3. Extraction & Real Load Bar (SSE Integration)
    // -------------------------------------------------------------------------
    elements.btnExtract.addEventListener('click', async () => {
        if (state.queuedFiles.length === 0 || state.isProcessing) return;

        state.isProcessing = true;
        renderQueue();

        elements.btnExtract.disabled = true;
        elements.btnClearQueue.disabled = true;
        elements.btnExtract.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
                <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-linecap="round"></circle>
            </svg>
            Extracting...
        `;

        // Initialize Real Load Bar
        const totalFiles = state.queuedFiles.length;
        elements.progressCard.style.display = 'block';
        elements.progressBar.style.width = '0%';
        elements.progressLabel.textContent = 'Processing resumes...';
        elements.progressStats.textContent = `0 of ${totalFiles} (0%)`;
        elements.progressFilename.textContent = 'Uploading files to processing worker...';

        // Prepare multipart form data
        const formData = new FormData();
        state.queuedFiles.forEach(file => {
            formData.append('files', file);
        });

        // Generate a unique batch session ID for SSE tracking
        const sessionId = 'batch_' + Date.now() + '_' + Math.random().toString(36).substring(2, 8);
        formData.append('session_id', sessionId);

        // Open SSE connection before sending upload
        setupEventSource(sessionId, totalFiles);

        try {
            const resp = await fetch('/api/process', {
                method: 'POST',
                body: formData,
            });

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Server error (${resp.status})`);
            }
        } catch (err) {
            console.error('Extraction error:', err);
            elements.progressLabel.textContent = 'Extraction failed';
            elements.progressFilename.textContent = err.message || 'Error communicating with server';
            finishExtraction();
        }
    });

    function setupEventSource(sessionId, totalFiles) {
        if (state.eventSource) {
            state.eventSource.close();
        }

        const sseUrl = `/api/events?session_id=${encodeURIComponent(sessionId)}`;
        const es = new EventSource(sseUrl);
        state.eventSource = es;

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'progress') {
                    const completed = data.completed;
                    const total = data.total || totalFiles;
                    const percent = Math.min(100, Math.round((completed / total) * 100));

                    elements.progressBar.style.width = `${percent}%`;
                    elements.progressStats.textContent = `${completed} of ${total} (${percent}%)`;
                    elements.progressLabel.textContent = `Processing resumes (${completed} of ${total} done)`;
                    if (data.filename) {
                        elements.progressFilename.textContent = `Parsing: ${data.filename}`;
                    }

                    if (data.candidate) {
                        addCandidate(data.candidate);
                    }
                } else if (data.type === 'complete') {
                    elements.progressBar.style.width = '100%';
                    elements.progressStats.textContent = `${data.total} of ${data.total} (100%)`;
                    elements.progressLabel.textContent = 'Extraction complete';
                    elements.progressFilename.textContent = `Successfully processed ${data.total} ${data.total === 1 ? 'resume' : 'resumes'}.`;
                    es.close();
                    finishExtraction();
                } else if (data.type === 'error') {
                    elements.progressFilename.textContent = `Notice: ${data.message}`;
                }
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        };

        es.onerror = () => {
            es.close();
            finishExtraction();
        };
    }

    function finishExtraction() {
        state.isProcessing = false;
        elements.btnExtract.disabled = false;
        elements.btnClearQueue.disabled = false;
        elements.btnExtract.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Extract Candidates
        `;
        renderQueue();
        updateExportButton();
    }

    // -------------------------------------------------------------------------
    // 4. Extracted Candidates Table & Inspection Modal
    // -------------------------------------------------------------------------
    function addCandidate(cand) {
        state.candidates.push(cand);
        renderCandidatesTable();
        updateExportButton();
    }

    function renderCandidatesTable() {
        const count = state.candidates.length;
        elements.candidateCount.textContent = `${count} ${count === 1 ? 'candidate' : 'candidates'}`;

        if (count === 0) {
            elements.candidateTbody.innerHTML = `
                <tr>
                    <td colspan="9" class="rd-empty">
                        <div class="rd-empty-icon">📄</div>
                        <div class="rd-empty-title">No candidates extracted yet</div>
                        <div class="rd-empty-desc">Upload resumes above and click Extract Candidates to begin.</div>
                    </td>
                </tr>
            `;
            return;
        }

        elements.candidateTbody.innerHTML = state.candidates.map((cand, idx) => {
            const statusClass = cand.status === 'success' ? 'status-success' :
                               (cand.status === 'review_required' || cand.status === 'partial' ? 'status-warning' : 'status-error');
            const statusLabel = cand.status === 'success' ? 'Verified' :
                               (cand.status === 'review_required' ? 'Needs Review' : (cand.status || 'Verified'));

            return `
                <tr>
                    <td class="rd-col-num">${idx + 1}</td>
                    <td><strong>${escapeHtml(cand.full_name || 'N/A')}</strong></td>
                    <td>${escapeHtml(cand.email || '—')}</td>
                    <td>${escapeHtml(cand.phone || '—')}</td>
                    <td>${escapeHtml(cand.location || '—')}</td>
                    <td>${escapeHtml(cand.highest_degree || '—')}</td>
                    <td class="rd-col-num rd-col-right">${cand.years_of_experience != null ? cand.years_of_experience : 0}</td>
                    <td><span class="${statusClass}">${statusLabel}</span></td>
                    <td class="rd-col-right">
                        <button type="button" class="btn btn-secondary btn-sm" onclick="window.__viewCandidate(${idx})">View</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function viewCandidate(index) {
        const cand = state.candidates[index];
        if (!cand) return;

        elements.modalCandidateName.textContent = cand.full_name || 'Candidate Details';

        let html = `
            <div class="rd-detail-section">
                <div class="rd-detail-label">Contact & Location</div>
                <div class="rd-detail-val">
                    <div>Email: <strong>${escapeHtml(cand.email || '—')}</strong></div>
                    <div>Phone: <strong>${escapeHtml(cand.phone || '—')}</strong></div>
                    <div>Location: ${escapeHtml(cand.location || '—')}</div>
                    ${cand.linkedin_url ? `<div>LinkedIn: <a href="${escapeHtml(cand.linkedin_url)}" target="_blank" rel="noopener">${escapeHtml(cand.linkedin_url)}</a></div>` : ''}
                    ${cand.github_url ? `<div>GitHub: <a href="${escapeHtml(cand.github_url)}" target="_blank" rel="noopener">${escapeHtml(cand.github_url)}</a></div>` : ''}
                </div>
            </div>

            <div class="rd-detail-section">
                <div class="rd-detail-label">Education</div>
                <div class="rd-detail-val">
                    ${(cand.education && cand.education.length > 0) ?
                        cand.education.map(e => `
                            <div style="margin-bottom: 6px;">
                                <strong>${escapeHtml(e.degree || e.qualification || 'Degree')}</strong> ${e.specialization ? `in ${escapeHtml(e.specialization)}` : ''}
                                <div style="color: var(--muted); font-size: 0.82rem;">${escapeHtml(e.institution || '')} ${e.graduation_year ? `· ${e.graduation_year}` : ''}</div>
                            </div>
                        `).join('') : '<div style="color: var(--muted);">No education records listed</div>'}
                </div>
            </div>

            <div class="rd-detail-section">
                <div class="rd-detail-label">Work Experience</div>
                <div class="rd-detail-val">
                    ${(cand.work_experience && cand.work_experience.length > 0) ?
                        cand.work_experience.map(w => `
                            <div style="margin-bottom: 8px;">
                                <strong>${escapeHtml(w.job_title || 'Role')}</strong> at ${escapeHtml(w.employer || w.company || 'Company')}
                                <div style="color: var(--muted); font-size: 0.82rem;">${escapeHtml(w.start_date || '')} — ${escapeHtml(w.end_date || 'Present')}</div>
                                ${w.responsibilities ? `<div style="font-size: 0.82rem; margin-top: 2px;">${escapeHtml(w.responsibilities)}</div>` : ''}
                            </div>
                        `).join('') : '<div style="color: var(--muted);">No work experience listed</div>'}
                </div>
            </div>

            <div class="rd-detail-section">
                <div class="rd-detail-label">Technical Skills & Tools</div>
                <div class="rd-tag-list">
                    ${(cand.technical_skills && cand.technical_skills.length > 0) ?
                        cand.technical_skills.map(s => `<span class="rd-tag">${escapeHtml(s)}</span>`).join('') :
                        '<span style="color: var(--muted); font-size: 0.85rem;">None listed</span>'}
                </div>
            </div>
        `;

        elements.modalCandidateBody.innerHTML = html;
        elements.modalOverlay.style.display = 'flex';
    }

    window.__viewCandidate = viewCandidate;

    function closeModal() {
        elements.modalOverlay.style.display = 'none';
    }

    elements.modalCloseBtn.addEventListener('click', closeModal);
    elements.modalOverlay.addEventListener('click', (e) => {
        if (e.target === elements.modalOverlay) {
            closeModal();
        }
    });

    // -------------------------------------------------------------------------
    // 5. Excel Workbook Export (.xlsx)
    // -------------------------------------------------------------------------
    function updateExportButton() {
        elements.btnExportExcel.disabled = state.candidates.length === 0;
    }

    elements.btnExportExcel.addEventListener('click', async () => {
        if (state.candidates.length === 0) return;

        try {
            const resp = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ candidates: state.candidates }),
            });

            if (!resp.ok) {
                throw new Error('Export generation failed');
            }

            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            a.href = url;
            a.download = `resumedrop_candidates_${stamp}.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Export error:', err);
            alert('Failed to download Excel file: ' + err.message);
        }
    });

    // -------------------------------------------------------------------------
    // 6. API Logs View & Check Connection
    // -------------------------------------------------------------------------
    async function loadLogs() {
        try {
            const resp = await fetch('/api/logs');
            if (!resp.ok) return;
            const data = await resp.json();
            renderLogsTable(data.logs || []);
        } catch (err) {
            console.error('Failed to load logs:', err);
        }
    }

    function renderLogsTable(logs) {
        elements.logCount.textContent = `${logs.length} ${logs.length === 1 ? 'call' : 'calls'}`;

        if (!logs || logs.length === 0) {
            elements.logsTbody.innerHTML = `
                <tr>
                    <td colspan="5" class="rd-empty">
                        <div class="rd-empty-icon">📊</div>
                        <div class="rd-empty-title">No API calls recorded yet</div>
                        <div class="rd-empty-desc">API calls made during extraction or connection checks will appear here.</div>
                    </td>
                </tr>
            `;
            return;
        }

        // Strictly the 5 requested columns: Time, Used for (Type), Model, Latency, Status
        elements.logsTbody.innerHTML = logs.map(log => {
            const statusClass = log.http_status === 200 ? 'status-success' :
                               (log.http_status === 429 ? 'status-warning' : 'status-error');

            const statusText = log.http_status === 200 ? '200 OK' :
                              (log.http_status === 429 ? '429 Rate Limited' :
                              (log.http_status === 504 ? '504 Timeout' : `${log.http_status || 500} ${log.status || 'Failed'}`));

            return `
                <tr>
                    <td class="rd-col-num">${escapeHtml(log.timestamp || '—')}</td>
                    <td>${escapeHtml(log.used_for || log.document_name || 'Extraction')}</td>
                    <td style="font-family: var(--font-mono); font-size: 0.82rem;">${escapeHtml(log.model || '—')}</td>
                    <td class="rd-col-num rd-col-right">${log.latency_ms ? log.latency_ms.toLocaleString() + ' ms' : '—'}</td>
                    <td><span class="${statusClass}">${escapeHtml(statusText)}</span></td>
                </tr>
            `;
        }).join('');
    }

    elements.btnRefreshLogs.addEventListener('click', loadLogs);

    elements.btnClearLogs.addEventListener('click', async () => {
        try {
            await fetch('/api/clear-logs', { method: 'POST' });
            loadLogs();
        } catch (err) {
            console.error('Failed to clear logs:', err);
        }
    });

    // Check Connection Button with Auto-fading Alert (No API Keys Displayed!)
    elements.btnCheckConnection.addEventListener('click', async () => {
        elements.btnCheckConnection.disabled = true;
        const originalText = elements.btnCheckConnection.innerHTML;
        elements.btnCheckConnection.innerHTML = `
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
                <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-linecap="round"></circle>
            </svg>
            Checking...
        `;

        try {
            const resp = await fetch('/api/check-connection', { method: 'POST' });
            const data = await resp.json().catch(() => ({ success: false, message: 'Check failed' }));

            showConnectionAlert(data.success, data.message);
            // Refresh logs table to show the connection check API call
            loadLogs();
        } catch (err) {
            showConnectionAlert(false, 'Could not connect to server.');
        } finally {
            elements.btnCheckConnection.disabled = false;
            elements.btnCheckConnection.innerHTML = originalText;
        }
    });

    function showConnectionAlert(success, message) {
        elements.connectionAlertContainer.innerHTML = '';

        const alertEl = document.createElement('div');
        alertEl.className = `rd-alert ${success ? 'rd-alert-success' : 'rd-alert-error'}`;
        alertEl.innerHTML = `
            <div>
                <strong>${success ? '✓' : '✕'}</strong>
                <span style="margin-left: 6px;">${escapeHtml(message)}</span>
            </div>
        `;

        elements.connectionAlertContainer.appendChild(alertEl);

        // Message automatically disappears after 5 seconds
        setTimeout(() => {
            alertEl.classList.add('fade-out');
            setTimeout(() => {
                alertEl.remove();
            }, 500);
        }, 5000);
    }

    // -------------------------------------------------------------------------
    // Utility Helpers
    // -------------------------------------------------------------------------
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

})();
