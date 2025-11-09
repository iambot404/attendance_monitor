const state = {
    records: [],
    selected: new Set(),
    threshold: 75,
    columns: [],
    identifierKey: 'roll_number',
    insights: { suggestions: [], stats: {}, lowest: [] },
    template: '',
    templateDraft: '',
    templateDirty: false,
    templateMaxLength: 4000,
    placeholders: [],
    charts: {
        distribution: null,
        course: null,
    },
};

const elements = {};

const INSIGHT_STAT_ORDER = [
    'threshold',
    'total_students',
    'below_threshold_count',
    'below_threshold_pct',
    'at_or_above_threshold_pct',
    'median_attendance',
    'average_attendance',
    'lowest_course',
    'lowest_course_average',
    'highest_course',
    'highest_course_average',
    'top_bucket_label',
    'top_bucket_value',
];

const INSIGHT_STAT_LABELS = {
    threshold: 'Threshold %',
    total_students: 'Records Evaluated',
    below_threshold_count: 'Below Threshold',
    below_threshold_pct: '% Below Threshold',
    at_or_above_threshold_pct: '% Meeting Threshold',
    median_attendance: 'Median %',
    average_attendance: 'Average %',
    lowest_course: 'Lowest Course',
    lowest_course_average: 'Lowest Course Avg %',
    highest_course: 'Highest Course',
    highest_course_average: 'Highest Course Avg %',
    top_bucket_label: 'Top Attendance Band',
    top_bucket_value: 'Students in Band',
};

const INSIGHT_PERCENT_KEYS = new Set([
    'threshold',
    'below_threshold_pct',
    'at_or_above_threshold_pct',
    'median_attendance',
    'average_attendance',
    'lowest_course_average',
    'highest_course_average',
]);

const LOWEST_COLUMNS = [
    { key: 'roll_number', label: 'Roll' },
    { key: 'student_name', label: 'Name' },
    { key: 'course', label: 'Course' },
    { key: 'attendance_percent', label: 'Attendance', format: 'percent' },
    { key: 'email', label: 'Email' },
    { key: 'phone_number', label: 'Phone' },
];

document.addEventListener('DOMContentLoaded', () => {
    cacheElements();
    const templateMax = Number.parseInt(document.body?.dataset.templateMax || state.templateMaxLength, 10);
    if (Number.isFinite(templateMax)) {
        state.templateMaxLength = templateMax;
    }
    wireEvents();
    updateThresholdDisplay(state.threshold);
    bootstrapFlash();
    initializeDashboard();
});

function cacheElements() {
    elements.form = document.getElementById('upload-form');
    elements.fileInput = document.getElementById('csvFileInput');
    elements.fileBrowse = document.getElementById('fileBrowse');
    elements.fileTrigger = document.getElementById('uploadTrigger');
    elements.fileName = document.getElementById('fileName');
    elements.thresholdSlider = document.getElementById('thresholdSlider');
    elements.thresholdValue = document.getElementById('thresholdValue');
    elements.tableHeadRow = document.getElementById('tableHeaderRow');
    elements.tableBody = document.getElementById('studentsTable');
    elements.selectAll = document.getElementById('selectAll');
    elements.clearSelection = document.getElementById('clearSelection');
    elements.sendAlerts = document.getElementById('sendAlerts');
    elements.sendAlertsTop = document.getElementById('sendAlertsTop');
    elements.toast = document.getElementById('toast');
    elements.summaryFields = document.querySelectorAll('[data-summary]');
    elements.distributionCanvas = document.getElementById('attendanceDistributionChart');
    elements.courseCanvas = document.getElementById('courseAverageChart');
    elements.insightSuggestions = document.getElementById('insightSuggestions');
    elements.insightStats = document.getElementById('insightStats');
    elements.insightLowestBody = document.getElementById('insightLowestBody');
    elements.refreshInsights = document.getElementById('refreshInsights');
    elements.templateForm = document.getElementById('templateForm');
    elements.templateTextarea = document.getElementById('templateEditor');
    elements.templateSave = document.getElementById('templateSave');
    elements.templateStatus = document.getElementById('templateStatus');
    elements.templateCounter = document.getElementById('templateCounter');
    elements.templatePlaceholders = document.getElementById('templatePlaceholders');
}

function wireEvents() {
    if (elements.fileBrowse) {
        elements.fileBrowse.addEventListener('click', () => elements.fileInput?.click());
    }
    if (elements.fileTrigger) {
        elements.fileTrigger.addEventListener('click', () => elements.fileInput?.click());
    }
    if (elements.fileInput) {
        elements.fileInput.addEventListener('change', handleFileSelection);
    }
    if (elements.thresholdSlider) {
        elements.thresholdSlider.addEventListener('input', (event) => {
            const value = Number.parseFloat(event.target.value);
            state.threshold = Number.isNaN(value) ? state.threshold : value;
            updateThresholdDisplay(state.threshold);
        });
    }
    if (elements.form) {
        elements.form.addEventListener('submit', handleFormSubmit);
    }
    if (elements.selectAll) {
        elements.selectAll.addEventListener('change', handleSelectAll);
    }
    if (elements.clearSelection) {
        elements.clearSelection.addEventListener('click', clearSelection);
    }
    if (elements.sendAlerts) {
        elements.sendAlerts.addEventListener('click', sendAlerts);
    }
    if (elements.sendAlertsTop) {
        elements.sendAlertsTop.addEventListener('click', sendAlerts);
    }
    if (elements.refreshInsights) {
        elements.refreshInsights.addEventListener('click', () => refreshInsights());
    }
    if (elements.templateForm) {
        elements.templateForm.addEventListener('submit', saveTemplate);
    }
    if (elements.templateTextarea) {
        elements.templateTextarea.addEventListener('input', handleTemplateInput);
    }
    if (elements.templateSave) {
        elements.templateSave.addEventListener('click', saveTemplate);
    }
}

async function initializeDashboard() {
    renderInsights();
    updateTemplateCounter();
    await Promise.allSettled([loadMessageTemplate(), refreshInsights(true)]);
}

function bootstrapFlash() {
    const flashPayload = document.body?.dataset.flash;
    if (!flashPayload) return;
    try {
        const messages = JSON.parse(flashPayload);
        if (Array.isArray(messages)) {
            messages.forEach(([variant, message], index) => {
                setTimeout(() => showToast(message, variant === 'error' ? 'error' : 'success'), index * 200);
            });
        }
    } catch (error) {
        // Swallow parse errors silently to avoid blocking UI bootstrap.
    }
}

function handleFileSelection(event) {
    const file = event.target.files?.[0];
    if (file) {
        elements.fileName.textContent = file.name;
    } else {
        elements.fileName.textContent = 'No file selected...';
    }
}

async function handleFormSubmit(event) {
    event.preventDefault();
    const formData = new FormData(elements.form);
    formData.set('threshold', state.threshold.toString());

    try {
        let response;
        if (elements.fileInput?.files?.length) {
            response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });
        } else {
            response = await fetch('/api/filter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ threshold: state.threshold }),
            });
        }

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Unable to process request');
        }
        ingestDataPayload(payload);
        showToast('Filter applied successfully.', 'success');
    } catch (error) {
        showToast(error.message || 'Something went wrong.', 'error');
    }
}

function ingestDataPayload(payload) {
    if (Array.isArray(payload.columns) && payload.columns.length) {
        state.columns = payload.columns;
    } else if (!state.columns.length && Array.isArray(payload.records) && payload.records.length) {
        state.columns = deriveColumnsFromRecord(payload.records[0]);
    }

    if (payload.identifier) {
        state.identifierKey = payload.identifier;
    } else if (!state.identifierKey && state.columns.length) {
        const identifierColumn = state.columns.find((column) => column.isIdentifier);
        if (identifierColumn) state.identifierKey = identifierColumn.key;
    }

    state.records = Array.isArray(payload.records) ? payload.records : [];
    state.records = state.records.map((record) => normalizeRecord(record));

    if (payload.insights) {
        applyInsights(payload.insights);
    }

    renderTable();
    updateSummary(payload.summary, state.threshold);
    updateCharts(payload.charts || {});
}

function deriveColumnsFromRecord(record) {
    return Object.keys(record || {}).map((key) => ({
        key,
        label: key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
        format: key === 'attendance_percent' ? 'percent' : 'text',
        isIdentifier: key === state.identifierKey,
    }));
}

function normalizeRecord(record) {
    const next = { ...record };
    if (Object.prototype.hasOwnProperty.call(next, 'attendance_percent')) {
        const numeric = Number.parseFloat(next.attendance_percent);
        next.attendance_percent = Number.isFinite(numeric) ? numeric : next.attendance_percent;
    }
    if (!next.alert_status) {
        next.alert_status = 'Pending';
    }
    if (state.identifierKey && Object.prototype.hasOwnProperty.call(next, state.identifierKey)) {
        next[state.identifierKey] = String(next[state.identifierKey]);
    }
    return next;
}

function renderTable() {
    renderTableHead();

    const identifier = state.identifierKey;
    state.selected = new Set(
        [...state.selected].filter((id) =>
            state.records.some((row) => identifier && String(row[identifier]) === id),
        ),
    );

    if (!state.records.length) {
        const columnCount = (state.columns.length || 0) + 1;
        elements.tableBody.innerHTML = `<tr class="empty"><td colspan="${columnCount}">Upload data and apply filters to see results.</td></tr>`;
        if (elements.selectAll) elements.selectAll.checked = false;
        return;
    }

    const rows = state.records
        .map((record) => {
            const rowId = identifier && record[identifier] !== undefined ? String(record[identifier]) : '';
            const checked = rowId && state.selected.has(rowId) ? 'checked' : '';
            const cells = state.columns.map((column) => renderCell(record, column)).join('');
            const disabled = rowId ? '' : 'disabled';
            return `
                <tr data-id="${rowId}">
                    <td class="select-col"><input type="checkbox" class="row-select" data-id="${rowId}" ${checked} ${disabled}></td>
                    ${cells}
                </tr>
            `;
        })
        .join('');

    elements.tableBody.innerHTML = rows;
    elements.tableBody.querySelectorAll('.row-select').forEach((checkbox) => {
        checkbox.addEventListener('change', handleRowSelection);
    });
    if (elements.selectAll) {
        const selectableRows = state.records.filter((record) => {
            const rowId = identifier && record[identifier] !== undefined ? String(record[identifier]) : '';
            return Boolean(rowId);
        });
        elements.selectAll.checked = selectableRows.length > 0 && state.selected.size === selectableRows.length;
        elements.selectAll.disabled = selectableRows.length === 0;
    }
}

function renderTableHead() {
    if (!elements.tableHeadRow) return;
    Array.from(elements.tableHeadRow.querySelectorAll('th[data-column]')).forEach((node) => node.remove());
    state.columns.forEach((column) => {
        const th = document.createElement('th');
        th.dataset.column = column.key;
        th.textContent = column.label || column.key;
        elements.tableHeadRow.appendChild(th);
    });
}

function renderCell(record, column) {
    const rawValue = record[column.key];
    if (column.key === 'alert_status') {
        const statusText = (rawValue || 'Pending').toString();
        const alertClass = statusText.toLowerCase() === 'sent' ? 'sent' : 'pending';
        return `<td><span class="status ${alertClass}">${statusText}</span></td>`;
    }

    if (column.format === 'percent') {
        const numeric = Number.parseFloat(rawValue);
        const value = Number.isFinite(numeric) ? `${numeric.toFixed(1)}%` : `${rawValue ?? '-'}`;
        return `<td>${value}</td>`;
    }

    const value = rawValue === null || typeof rawValue === 'undefined' || rawValue === '' ? '-' : rawValue;
    return `<td>${value}</td>`;
}

function handleRowSelection(event) {
    const checkbox = event.target;
    const id = checkbox.dataset.id;
    if (!id) return;

    if (checkbox.checked) {
        state.selected.add(id);
    } else {
        state.selected.delete(id);
    }
    if (elements.selectAll) {
        elements.selectAll.checked = state.records.length && state.selected.size === state.records.length;
    }
}

function handleSelectAll(event) {
    const identifier = state.identifierKey;
    if (!state.records.length || !identifier) {
        event.target.checked = false;
        return;
    }

    if (event.target.checked) {
        state.records.forEach((record) => {
            if (Object.prototype.hasOwnProperty.call(record, identifier)) {
                const rowId = String(record[identifier]);
                if (rowId) state.selected.add(rowId);
            }
        });
    } else {
        state.selected.clear();
    }
    renderTable();
}

function clearSelection() {
    state.selected.clear();
    if (elements.selectAll) elements.selectAll.checked = false;
    renderTable();
}

function updateSummary(summary = {}, threshold) {
    if (!elements.summaryFields) return;
    elements.summaryFields.forEach((field) => {
        const key = field.dataset.summary;
        if (!key) return;
        let value = summary[key];
        if (['average', 'lowest', 'highest'].includes(key) && typeof value === 'number') {
            value = `${value.toFixed(1)}%`;
        }
        if (typeof value === 'undefined') {
            value = key === 'total' || key === 'below' ? 0 : '0%';
        }
        field.textContent = value;
    });
}

function updateCharts(charts) {
    const ChartJS = window.Chart;
    if (!ChartJS) {
        console.warn('Chart.js library not loaded');
        return;
    }

    if (elements.distributionCanvas) {
        const ctx = elements.distributionCanvas.getContext('2d');
        if (!state.charts.distribution) {
            state.charts.distribution = new ChartJS(ctx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Students',
                        data: [],
                        backgroundColor: '#3a86ff',
                        borderRadius: 8,
                    }],
                },
                options: {
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            });
        }
        const dataset = charts.distribution || [];
        state.charts.distribution.data.labels = dataset.map((item) => item.label);
        state.charts.distribution.data.datasets[0].data = dataset.map((item) => item.value);
        state.charts.distribution.update();
    }

    if (elements.courseCanvas) {
        const ctx = elements.courseCanvas.getContext('2d');
        if (!state.charts.course) {
            state.charts.course = new ChartJS(ctx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Average %',
                        data: [],
                        backgroundColor: '#38b000',
                        borderRadius: 8,
                    }],
                },
                options: {
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, suggestedMax: 100 },
                    },
                },
            });
        }
        const dataset = charts.byCourse || [];
        state.charts.course.data.labels = dataset.map((item) => item.label);
        state.charts.course.data.datasets[0].data = dataset.map((item) => item.value);
        state.charts.course.update();
    }
}

function applyInsights(insights) {
    if (insights && typeof insights === 'object') {
        state.insights = {
            suggestions: Array.isArray(insights.suggestions) ? insights.suggestions : [],
            stats: insights.stats || {},
            lowest: Array.isArray(insights.lowest) ? insights.lowest : [],
        };
    } else {
        state.insights = { suggestions: [], stats: {}, lowest: [] };
    }
    renderInsights();
}

function renderInsights() {
    if (elements.insightSuggestions) {
        const suggestions = state.insights?.suggestions || [];
        if (suggestions.length) {
            elements.insightSuggestions.innerHTML = suggestions
                .map((item) => `<li>${escapeHtml(item)}</li>`)
                .join('');
        } else {
            elements.insightSuggestions.innerHTML = '<li class="placeholder">Upload data to generate suggestions.</li>';
        }
    }

    if (elements.insightStats) {
        const stats = state.insights?.stats || {};
        const fragments = [];
        INSIGHT_STAT_ORDER.forEach((key) => {
            if (Object.prototype.hasOwnProperty.call(stats, key)) {
                const value = stats[key];
                if (value !== null && typeof value !== 'undefined' && value !== '') {
                    fragments.push(
                        `<div class="insight-stat-pair"><dt>${escapeHtml(INSIGHT_STAT_LABELS[key] || key)}</dt><dd>${formatStatValue(key, value)}</dd></div>`,
                    );
                }
            }
        });
        elements.insightStats.innerHTML = fragments.length
            ? fragments.join('')
            : '<div class="insight-stat-pair"><dt>Info</dt><dd>No metrics yet.</dd></div>';
    }

    if (elements.insightLowestBody) {
        const rows = state.insights?.lowest || [];
        if (!rows.length) {
            elements.insightLowestBody.innerHTML = '<tr class="empty"><td colspan="6">No records yet.</td></tr>';
        } else {
            elements.insightLowestBody.innerHTML = rows
                .map((record) => {
                    const cells = LOWEST_COLUMNS.map((column) => {
                        const rawValue = record[column.key];
                        const value = formatLowestValue(column, rawValue);
                        return `<td>${value}</td>`;
                    }).join('');
                    return `<tr>${cells}</tr>`;
                })
                .join('');
        }
    }
}

async function refreshInsights(silent = false) {
    try {
        const response = await fetch('/api/plot-data');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Unable to refresh insights.');
        }
        if (data.charts) {
            updateCharts(data.charts);
        }
        applyInsights(data.insights || null);
    } catch (error) {
        if (!silent) {
            showToast(error.message || 'Unable to refresh insights.', 'error');
        }
    }
}

async function loadMessageTemplate() {
    if (!elements.templateTextarea) {
        return;
    }
    try {
        const response = await fetch('/api/message-template');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Unable to load template.');
        }

        state.template = typeof data.template === 'string' ? data.template : '';
        state.templateDraft = state.template;
        state.templateDirty = false;

        if (typeof data.max_length === 'number' && Number.isFinite(data.max_length)) {
            state.templateMaxLength = data.max_length;
        }

        elements.templateTextarea.value = state.template;
        renderTemplatePlaceholders(data.placeholders);
        updateTemplateCounter();
        if (elements.templateSave) {
            elements.templateSave.disabled = true;
        }
        setTemplateStatus('success', 'Template loaded.');
    } catch (error) {
        setTemplateStatus('error', 'Failed to load template.');
        showToast(error.message || 'Unable to load template.', 'error');
    }
}

function renderTemplatePlaceholders(placeholders) {
    if (!elements.templatePlaceholders) return;

    if (Array.isArray(placeholders)) {
        state.placeholders = placeholders;
    }

    if (!state.placeholders.length) {
        elements.templatePlaceholders.textContent = 'No placeholders available.';
        return;
    }

    const markup = state.placeholders
        .map((item) => {
            const key = escapeHtml(item.key || '');
            const description = escapeHtml(item.description || '');
            return `<span class="placeholder-item"><code>{${key}}</code><span>${description}</span></span>`;
        })
        .join('');
    elements.templatePlaceholders.innerHTML = markup;
}

function handleTemplateInput() {
    if (!elements.templateTextarea) return;
    state.templateDraft = elements.templateTextarea.value;
    state.templateDirty = state.templateDraft !== state.template;
    updateTemplateCounter();
    if (elements.templateSave) {
        elements.templateSave.disabled = !state.templateDirty;
    }
    setTemplateStatus();
}

function updateTemplateCounter() {
    if (!elements.templateCounter) return;
    const length = state.templateDraft ? state.templateDraft.length : 0;
    elements.templateCounter.textContent = `${length}/${state.templateMaxLength}`;
    if (length > state.templateMaxLength) {
        elements.templateCounter.classList.add('over-limit');
    } else {
        elements.templateCounter.classList.remove('over-limit');
    }
}

function setTemplateStatus(status, message = '') {
    if (!elements.templateStatus) return;
    elements.templateStatus.textContent = message;
    elements.templateStatus.classList.remove('success', 'error');
    if (status === 'success' || status === 'error') {
        elements.templateStatus.classList.add(status);
    }
}

async function saveTemplate(event) {
    event?.preventDefault?.();
    if (!elements.templateTextarea) {
        return;
    }

    if (!state.templateDirty) {
        setTemplateStatus('success', 'No changes to save.');
        return;
    }

    const template = state.templateDraft || '';
    if (!template.trim()) {
        setTemplateStatus('error', 'Template cannot be empty.');
        showToast('Template cannot be empty.', 'error');
        return;
    }

    if (template.length > state.templateMaxLength) {
        setTemplateStatus('error', 'Template exceeds the allowed length.');
        showToast('Template exceeds the allowed length.', 'error');
        return;
    }

    try {
        if (elements.templateSave) {
            elements.templateSave.disabled = true;
        }
        const response = await fetch('/api/message-template', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ template }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Unable to save template.');
        }

        state.template = data.template || template;
        state.templateDraft = state.template;
        state.templateDirty = false;

        if (typeof data.max_length === 'number' && Number.isFinite(data.max_length)) {
            state.templateMaxLength = data.max_length;
        }

        renderTemplatePlaceholders(data.placeholders);
        updateTemplateCounter();
        setTemplateStatus('success', 'Template saved successfully.');
        showToast('Template saved successfully.', 'success');
    } catch (error) {
        state.templateDirty = true;
        if (elements.templateSave) {
            elements.templateSave.disabled = false;
        }
        setTemplateStatus('error', error.message || 'Unable to save template.');
        showToast(error.message || 'Unable to save template.', 'error');
    } finally {
        if (elements.templateSave) {
            elements.templateSave.disabled = !state.templateDirty;
        }
    }
}

function formatStatValue(key, value) {
    if (INSIGHT_PERCENT_KEYS.has(key)) {
        const numeric = Number.parseFloat(value);
        if (Number.isFinite(numeric)) {
            return `${numeric.toFixed(1)}%`;
        }
        return `${escapeHtml(value)}%`;
    }

    if (key === 'top_bucket_label') {
        return escapeHtml(value);
    }

    if (typeof value === 'number') {
        return Number.isInteger(value) ? `${value}` : `${value.toFixed(1)}`;
    }

    return escapeHtml(value);
}

function formatLowestValue(column, value) {
    if (column.format === 'percent') {
        const numeric = Number.parseFloat(value);
        if (Number.isFinite(numeric)) {
            return `${numeric.toFixed(1)}%`;
        }
        return value ? `${escapeHtml(value)}%` : '-';
    }
    if (value === null || typeof value === 'undefined' || value === '') {
        return '-';
    }
    return escapeHtml(value);
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function sendAlerts() {
    if (!state.selected.size) {
        showToast('Select at least one student before sending alerts.', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/send-alerts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ students: Array.from(state.selected), threshold: state.threshold }),
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || 'Unable to send alerts');
        }

        const sentIds = Array.isArray(payload.sent_ids) ? payload.sent_ids.map((value) => String(value)) : [];
        const identifier = state.identifierKey;
        if (identifier && sentIds.length) {
            state.records.forEach((record) => {
                if (String(record[identifier]) && sentIds.includes(String(record[identifier]))) {
                    record.alert_status = 'Sent';
                    state.selected.delete(String(record[identifier]));
                }
            });
        } else if (Array.isArray(payload.sent)) {
            payload.sent.forEach((email) => {
                const record = state.records.find((row) => row.email === email);
                if (record) {
                    record.alert_status = 'Sent';
                    if (identifier && record[identifier]) {
                        state.selected.delete(String(record[identifier]));
                    }
                }
            });
        }
        renderTable();

        const sentCount = sentIds.length || payload.sent?.length || 0;
        const failCount = payload.failed?.length || 0;
        const message = `Alerts sent: ${sentCount}${failCount ? `, failed: ${failCount}` : ''}`;
        showToast(message, failCount ? 'warning' : 'success');
    } catch (error) {
        showToast(error.message || 'Unable to send alerts.', 'error');
    }
}

function updateThresholdDisplay(value) {
    if (elements.thresholdValue) {
        elements.thresholdValue.textContent = Number.parseFloat(value).toFixed(0);
    }
}

let toastTimeout;
function showToast(message, variant = 'info') {
    if (!elements.toast) return;
    elements.toast.textContent = message;
    elements.toast.className = `toast show ${variant}`;
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 4000);
}
