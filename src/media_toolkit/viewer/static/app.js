/**
 * Social Media Collector - Frontend Application
 * Improved Workflow UI
 */

// State
let currentPosts = [];
let currentPage = 1;
let postsPerPage = 50;
let currentView = 'grid';
let selectedTags = new Set();
let selectedPosts = new Set();
let taskPollingInterval = null;
let inaccessiblePosts = [];

// API Base URL
const API_BASE = '';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadStats();
    loadFilterOptions();
    loadPosts();
    checkInaccessible();

    setupEventHandlers();
});

// Setup event handlers
function setupEventHandlers() {
    // Enter key for search
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchPosts();
    });

    // Modal handlers
    document.getElementById('postModal').addEventListener('click', (e) => {
        if (e.target.id === 'postModal') closeModal();
    });

    document.getElementById('inaccessibleModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'inaccessibleModal') closeInaccessibleModal();
    });

    document.getElementById('scanResultModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'scanResultModal') closeScanResultModal();
    });

    document.getElementById('configModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'configModal') closeConfigModal();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            closeInaccessibleModal();
            closeScanResultModal();
            closeConfigModal();
        }
    });
}

// ==================== Config ====================

// ==================== Config ====================

async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const config = await response.json();

        // Path
        document.getElementById('sourceDirInput').value = config.source_dir;
        document.getElementById('sourceInfo').textContent = `현재 경로: ${config.source_dir}`;

        // Cookies
        if (config.cookies_from_browser) {
            document.querySelector(`input[name="authType"][value="browser"]`).checked = true;
            document.getElementById('browserSelect').value = config.cookies_from_browser;
        } else if (config.cookies_file) {
            document.querySelector(`input[name="authType"][value="file"]`).checked = true;
            document.getElementById('cookiePathInput').value = config.cookies_file;
        }

        toggleAuthType();
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

async function updateSourceDir() {
    // Legacy function, kept for compatibility with Step 1 save button
    const newDir = document.getElementById('sourceDirInput').value.trim();
    saveConfigData({ source_dir: newDir });
}

async function saveConfig() {
    const sourceDir = document.getElementById('sourceDirInput').value.trim();
    const authType = document.querySelector('input[name="authType"]:checked').value;

    let cookiesFromBrowser = null;
    let cookiesFile = null;

    if (authType === 'browser') {
        cookiesFromBrowser = document.getElementById('browserSelect').value;
    } else {
        cookiesFile = document.getElementById('cookiePathInput').value.trim();
        if (!cookiesFile) {
            showToast('쿠키 파일 경로를 입력하세요', 'error');
            return;
        }
    }

    const success = await saveConfigData({
        source_dir: sourceDir,
        cookies_from_browser: cookiesFromBrowser,
        cookies_file: cookiesFile
    });

    if (success) {
        closeConfigModal();
    }
}

async function saveConfigData(data) {
    try {
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            const result = await response.json();
            showToast('설정이 저장되었습니다', 'success');

            if (result.source_dir) {
                document.getElementById('sourceInfo').textContent = `현재 경로: ${result.source_dir}`;
            }
            return true;
        } else {
            const err = await response.json();
            showToast('저장 실패: ' + (err.detail || ''), 'error');
            return false;
        }
    } catch (error) {
        showToast('저장 실패: ' + error.message, 'error');
        return false;
    }
}

function openConfigModal() {
    loadConfig(); // Refresh data
    document.getElementById('configModal').classList.add('open');
}

function closeConfigModal() {
    document.getElementById('configModal').classList.remove('open');
}

function toggleAuthType() {
    const authType = document.querySelector('input[name="authType"]:checked').value;
    document.getElementById('browserAuthSection').style.display = authType === 'browser' ? 'block' : 'none';
    document.getElementById('fileAuthSection').style.display = authType === 'file' ? 'block' : 'none';
}

// ==================== Stats ====================

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const stats = await response.json();

        document.getElementById('statTotal').textContent = stats.total_posts || 0;
        document.getElementById('statAccessible').textContent = stats.accessible || 0;
        document.getElementById('statPrivate').textContent = stats.private || 0;
        document.getElementById('statDeleted').textContent = stats.deleted || 0;
        document.getElementById('statPending').textContent = stats.pending || 0;

        // Check if there are inaccessible posts
        const inaccessibleCount = (stats.private || 0) + (stats.deleted || 0);
        updateInaccessibleSection(inaccessibleCount);
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

function updateInaccessibleSection(count) {
    const section = document.getElementById('inaccessibleSection');
    const countEl = document.getElementById('inaccessibleCount');

    if (count > 0) {
        section.style.display = 'block';
        countEl.textContent = count;
    } else {
        section.style.display = 'none';
    }
}

// ==================== Workflow Step 2: Scan MD Files ====================

let lastScanResult = null;

async function scanMdFiles() {
    const sourceDir = document.getElementById('sourceDirInput').value.trim();
    if (!sourceDir) {
        showToast('소스 경로를 먼저 설정하세요', 'error');
        return;
    }

    showToast('MD 파일 스캔 중...', 'info');

    try {
        const response = await fetch(`${API_BASE}/api/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_dir: sourceDir }),
        });

        const result = await response.json();
        const resultEl = document.getElementById('scanResult');

        if (result.success) {
            lastScanResult = result;

            // Show brief summary in sidebar
            resultEl.className = 'scan-result show success';

            let summaryText = '';
            if (result.existing_urls > 0 && result.new_urls === 0) {
                summaryText = `⚠️ 새 URL 없음 (${result.existing_urls}개 기존)`;
            } else if (result.existing_urls > 0) {
                summaryText = `✅ <strong>${result.new_urls}개 새</strong> / ${result.existing_urls}개 기존`;
            } else {
                summaryText = `✅ <strong>${result.new_urls}개 새 URL</strong>`;
            }

            resultEl.innerHTML = `
                ${summaryText}
                <button class="btn-link" onclick="showScanResultModal()">상세 보기 →</button>
            `;

            // Show detailed modal
            showScanResultModal();

            if (result.new_urls > 0) {
                showToast(`${result.new_urls}개 새 URL 발견! 자동 수집 시작...`, 'success');
                validateAndScrape();
            } else {
                showToast('새로운 URL이 없습니다', 'info');
            }
            loadStats();
            loadPosts();
        } else {
            resultEl.className = 'scan-result show error';
            resultEl.textContent = '❌ ' + (result.detail || '스캔 실패');
            showToast('스캔 실패', 'error');
        }
    } catch (error) {
        showToast('스캔 실패: ' + error.message, 'error');
    }
}

function showScanResultModal() {
    if (!lastScanResult) return;

    const result = lastScanResult;
    const platformIcons = {
        instagram: '📷',
        facebook: '📘',
        linkedin: '💼',
        threads: '🧵',
        unknown: '🔗'
    };

    // Show alert if there are existing URLs
    let alertHtml = '';
    if (result.existing_urls > 0) {
        alertHtml = `
            <div class="scan-alert info">
                ℹ️ <strong>${result.existing_urls}개 URL</strong>은 이미 수집되어 있습니다.
                새로 발견된 <strong>${result.new_urls}개 URL</strong>만 추가되었습니다.
            </div>
        `;
    } else if (result.new_urls > 0) {
        alertHtml = `
            <div class="scan-alert success">
                ✅ 모든 URL이 새로 발견되었습니다!
            </div>
        `;
    } else {
        alertHtml = `
            <div class="scan-alert warning">
                ⚠️ 새로운 URL이 없습니다. 모든 URL이 이미 수집되어 있습니다.
            </div>
        `;
    }

    // Render stats with alert
    document.getElementById('scanStats').innerHTML = `
        ${alertHtml}
        <div class="scan-stat-cards">
            <div class="scan-stat-card">
                <div class="scan-stat-value">${result.files_scanned}</div>
                <div class="scan-stat-label">스캔된 파일</div>
            </div>
            <div class="scan-stat-card">
                <div class="scan-stat-value">${result.unique_urls}</div>
                <div class="scan-stat-label">고유 URL</div>
            </div>
            <div class="scan-stat-card new">
                <div class="scan-stat-value">${result.new_urls}</div>
                <div class="scan-stat-label">🆕 새 URL</div>
                <div class="scan-stat-desc">수집 대기</div>
            </div>
            <div class="scan-stat-card existing">
                <div class="scan-stat-value">${result.existing_urls}</div>
                <div class="scan-stat-label">📦 기존 URL</div>
                <div class="scan-stat-desc">이미 DB에 있음</div>
            </div>
            <div class="scan-stat-card duplicate">
                <div class="scan-stat-value">${result.duplicates}</div>
                <div class="scan-stat-label">🔄 중복 제거</div>
                <div class="scan-stat-desc">파일 내 중복</div>
            </div>
        </div>
    `;

    // Render platform stats
    let platformHtml = '';
    for (const [platform, count] of Object.entries(result.by_platform || {})) {
        const icon = platformIcons[platform] || '🔗';
        platformHtml += `
            <div class="platform-stat">
                <span class="icon">${icon}</span>
                <span>${platform}</span>
                <span class="count">${count}</span>
            </div>
        `;
    }
    document.getElementById('platformStats').innerHTML = platformHtml || '<span style="color:var(--text-muted)">데이터 없음</span>';

    // Render URL list
    let urlListHtml = '';
    for (const url of (result.url_list || [])) {
        const icon = platformIcons[url.platform] || '🔗';
        urlListHtml += `
            <div class="url-item">
                <span class="platform-badge">${icon}</span>
                <a href="${url.url}" target="_blank" class="url-link">${url.url}</a>
                ${url.source_file ? `<span class="source-badge">${url.source_file}</span>` : ''}
                ${url.is_new ? '<span class="new-badge">NEW</span>' : '<span class="existing-badge">기존</span>'}
            </div>
        `;
    }
    document.getElementById('scannedUrlList').innerHTML = urlListHtml || '<p style="color:var(--text-muted)">URL 없음</p>';

    // Render duplicate list
    let duplicateHtml = '';
    for (const dup of (result.duplicate_list || [])) {
        duplicateHtml += `
            <div class="duplicate-item">
                <span class="count-badge">${dup.count}회</span>
                <span class="url-text">${dup.url}</span>
            </div>
        `;
    }
    document.getElementById('duplicateUrlList').innerHTML = duplicateHtml || '<p style="color:var(--text-muted)">중복 URL 없음</p>';

    // Show modal
    document.getElementById('scanResultModal').classList.add('open');
}

function closeScanResultModal() {
    document.getElementById('scanResultModal').classList.remove('open');
}

function showScanTab(tab) {
    document.querySelectorAll('.scan-tabs .tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    document.getElementById('urlsTab').style.display = tab === 'urls' ? 'block' : 'none';
    document.getElementById('duplicatesTab').style.display = tab === 'duplicates' ? 'block' : 'none';
}

// ==================== Workflow Step 3: Validate & Scrape ====================

async function validateAndScrape() {
    showToast('URL 정보 조회 시작...', 'info');

    try {
        // First validate
        const validateRes = await fetch(`${API_BASE}/api/validate`, { method: 'POST' });
        const validateResult = await validateRes.json();

        if (validateResult.count > 0) {
            showToast(`${validateResult.count}개 URL 검증 시작`, 'info');
            startTaskPolling();
        } else {
            // No pending URLs, try scraping
            const scrapeRes = await fetch(`${API_BASE}/api/scrape`, { method: 'POST' });
            const scrapeResult = await scrapeRes.json();

            if (scrapeResult.count > 0) {
                showToast(`${scrapeResult.count}개 메타데이터 수집 시작`, 'info');
                startTaskPolling();
            } else {
                showToast('처리할 URL이 없습니다', 'info');
            }
        }
    } catch (error) {
        showToast('조회 실패: ' + error.message, 'error');
    }
}

// ==================== Inaccessible URLs ====================

async function checkInaccessible() {
    try {
        const response = await fetch(`${API_BASE}/api/posts/inaccessible`);
        if (response.ok) {
            inaccessiblePosts = await response.json();
            updateInaccessibleSection(inaccessiblePosts.length);
        }
    } catch (error) {
        console.error('Failed to check inaccessible:', error);
    }
}

function showInaccessibleList() {
    const modal = document.getElementById('inaccessibleModal');
    const listEl = document.getElementById('inaccessibleList');

    if (inaccessiblePosts.length === 0) {
        listEl.innerHTML = '<p style="color: var(--text-muted)">접근 불가 URL이 없습니다</p>';
    } else {
        listEl.innerHTML = inaccessiblePosts.map(post => `
            <div class="inaccessible-item">
                <span class="status-badge ${post.status}">${post.status === 'private' ? '비공개' : '삭제됨'}</span>
                <div class="url">${post.url}</div>
                ${post.source_file ? `<div class="source">📄 ${post.source_file.split('/').pop()}</div>` : ''}
            </div>
        `).join('');
    }

    modal.classList.add('open');
}

function closeInaccessibleModal() {
    document.getElementById('inaccessibleModal').classList.remove('open');
}

function exportInaccessible() {
    if (inaccessiblePosts.length === 0) {
        showToast('내보낼 데이터가 없습니다', 'info');
        return;
    }

    const csv = 'Status,URL,Source File\n' +
        inaccessiblePosts.map(p =>
            `${p.status},"${p.url}","${p.source_file || ''}"`
        ).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'inaccessible_urls.csv';
    a.click();
    URL.revokeObjectURL(url);

    showToast('CSV 파일 다운로드됨', 'success');
}

function filterByStatus(status) {
    // Uncheck all and check specific status
    document.querySelectorAll('#statusFilters input').forEach(el => {
        el.checked = el.value === status;
    });
    applyFilters();
}

// ==================== Posts Loading ====================

async function loadFilterOptions() {
    try {
        const response = await fetch(`${API_BASE}/api/filters`);
        const filters = await response.json();

        const authorList = document.getElementById('authorList');
        authorList.innerHTML = '';

        // Add "Select All/None" logic or just list items
        filters.authors.forEach(author => {
            const div = document.createElement('div');
            div.className = 'option-item';
            div.onclick = (e) => {
                // Toggle checkbox when row clicked
                if (e.target.tagName !== 'INPUT') {
                    const cb = div.querySelector('input');
                    cb.checked = !cb.checked;
                    updateAuthorLabel();
                    applyFilters();
                }
            };

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = author;
            checkbox.onchange = () => {
                updateAuthorLabel();
                applyFilters();
            };

            const label = document.createElement('span');
            label.textContent = author;

            div.appendChild(checkbox);
            div.appendChild(label);
            authorList.appendChild(div);
        });
    } catch (error) {
        console.error('Failed to load filter options:', error);
    }
}

async function loadPosts() {
    const container = document.getElementById('postsContainer');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const params = new URLSearchParams();

        // Status filter
        const statusCheckboxes = document.querySelectorAll('#statusFilters input:checked');
        if (statusCheckboxes.length === 1) {
            params.set('status', statusCheckboxes[0].value);
        }

        // Platform filter
        const platformCheckboxes = document.querySelectorAll('#platformFilters input:checked');
        if (platformCheckboxes.length === 1) {
            params.set('platform', platformCheckboxes[0].value);
        }

        // Author filter (Multi-select)
        const checkedAuthors = Array.from(document.querySelectorAll('#authorList input:checked')).map(cb => cb.value);
        checkedAuthors.forEach(a => params.append('author', a));

        // Search
        // Media Type filter
        const mediaCheckboxes = document.querySelectorAll('#mediaFilters input:checked');
        if (mediaCheckboxes.length === 1) {
            params.set('media_type', mediaCheckboxes[0].value);
        }

        // Tag filter
        const tag = document.getElementById('tagFilter').value.trim();
        if (tag) params.set('tag', tag);
        const search = document.getElementById('searchInput').value.trim();
        if (search) params.set('search', search);

        // Sort
        params.set('sort_by', document.getElementById('sortSelect').value);
        params.set('sort_desc', 'true');
        params.set('limit', postsPerPage);
        params.set('offset', (currentPage - 1) * postsPerPage);
        // The user's provided code edit had a syntax error here.
        // Assuming the intent was to add a cursor parameter if it exists,
        // but since `cursor` is not defined in this scope, and the primary
        // instruction was about adding a timestamp, I'm only applying the
        // timestamp and params.toString() change to avoid introducing errors.
        // if (cursor) params.append('cursor', cursor);

        const response = await fetch(`${API_BASE}/api/posts?${params.toString()}&t=${Date.now()}`);
        const data = await response.json();

        currentPosts = data.posts;
        renderPosts();
        renderPagination(data.total);
    } catch (error) {
        console.error('Failed to load posts:', error);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-title">불러오기 실패</div>
            </div>
        `;
    }
}

function setView(view) {
    currentView = view;
    document.getElementById('gridViewBtn').classList.toggle('active', view === 'grid');
    document.getElementById('listViewBtn').classList.toggle('active', view === 'list');

    renderPosts();
}

function renderPosts() {
    const container = document.getElementById('postsContainer');
    container.className = `posts-container ${currentView}-view`;

    if (currentPosts.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-title">게시물이 없습니다</div>
                <div class="empty-state-text">Step 2에서 MD 파일을 스캔하세요</div>
            </div>
        `;
        return;
    }

    if (currentView === 'list') {
        const headerHtml = `
            <div class="post-list-header">
                <div class="list-header-cell check"></div>
                <div class="list-header-cell thumb">미디어</div>
                <div class="list-header-cell content clickable" onclick="setSort('posted_at')">내용 / 날짜 ↕</div>
                <div class="list-header-cell meta">
                    <span class="clickable" onclick="event.stopPropagation(); setSort('views')">조회수 ↕</span>
                    <span class="clickable" onclick="event.stopPropagation(); setSort('likes')">좋아요 ↕</span>
                </div>
            </div>
        `;
        container.innerHTML = headerHtml + currentPosts.map(post => renderPostListItem(post)).join('');
    } else {
        container.innerHTML = currentPosts.map(post => renderPostCard(post)).join('');
    }
}

function renderPostCard(post) {
    const platformIcons = {
        instagram: '📷',
        facebook: '📘',
        linkedin: '💼',
        threads: '🧵',
        unknown: '🔗'
    };
    const icon = platformIcons[post.platform] || platformIcons.unknown;

    let thumbnailHtml = post.thumbnail_path
        ? `<img src="/thumbnails/${post.id}.jpg" alt="" loading="lazy">`
        : `<div class="placeholder">${icon}</div>`;

    const date = post.posted_at ? new Date(post.posted_at).toLocaleDateString('ko-KR') : '';
    const metaItems = [];
    if (post.views) metaItems.push(`👁️ ${formatNumber(post.views)}`);
    if (post.likes) metaItems.push(`❤️ ${formatNumber(post.likes)}`);
    if (date) metaItems.push(`📅 ${date}`);
    if (post.media_paths && post.media_paths.length > 0) {
        metaItems.push(`<span class="folder-btn clickable" onclick="event.stopPropagation(); openLocalFolder('${post.id}')" title="저장 폴더 열기">📂</span>`);
    }

    const isSelected = selectedPosts.has(post.id);

    return `
        <div class="post-card ${isSelected ? 'selected' : ''}" onclick="openPostModal('${post.id}')">
            <div class="selection-checkbox ${isSelected ? 'checked' : ''}" onclick="event.stopPropagation(); toggleSelection('${post.id}')">
                ${isSelected ? '✓' : ''}
            </div>
            <div class="post-thumbnail">
                ${thumbnailHtml}
                <span class="post-platform-badge">${icon}</span>
                <span class="post-status-badge ${post.status}">${post.status}</span>
            </div>
            <div class="post-info">
                <div class="post-author">${post.author || '알 수 없음'}</div>
                <div class="post-content">${post.content || post.title || '내용 없음'}</div>
                <div class="post-meta">${metaItems.join(' • ')}</div>
            </div>
        </div>
    `;
}

function renderPostListItem(post) {
    const platformIcons = {
        instagram: '📷',
        facebook: '📘',
        linkedin: '💼',
        threads: '🧵',
        unknown: '🔗'
    };
    const icon = platformIcons[post.platform] || platformIcons.unknown;
    const date = post.posted_at ? new Date(post.posted_at).toLocaleDateString('ko-KR') : '';

    let thumbnailHtml = post.thumbnail_path
        ? `<img src="/thumbnails/${post.id}.jpg" alt="" loading="lazy">`
        : `<div class="placeholder small">${icon}</div>`;

    const isSelected = selectedPosts.has(post.id);

    return `
        <div class="post-list-item ${isSelected ? 'selected' : ''}" onclick="openPostModal('${post.id}')">
            <div class="selection-checkbox list-checkbox ${isSelected ? 'checked' : ''}" onclick="event.stopPropagation(); toggleSelection('${post.id}')">
                ${isSelected ? '✓' : ''}
            </div>
            <div class="list-thumb">
                ${thumbnailHtml}
                <span class="platform-icon">${icon}</span>
            </div>
            <div class="list-content">
                <div class="list-header">
                    <span class="list-author">${post.author || '알 수 없음'}</span>
                    <span class="post-status-badge ${post.status} mini">${post.status}</span>
                    <span class="list-date">${date}</span>
                </div>
                <div class="list-text">
                    ${post.content || post.title || ''}
                    <div class="list-url">
                        <a href="${post.url}" target="_blank" onclick="event.stopPropagation()">🔗 ${post.url}</a>
                    </div>
                </div>
            </div>
            <div class="list-meta">
                ${post.media_paths && post.media_paths.length > 0 ? `<span class="folder-btn clickable" style="margin-right:10px" onclick="event.stopPropagation(); openLocalFolder('${post.id}')" title="저장 폴더 열기">📂</span>` : ''}
                ${post.views ? `<span title="조회수">👁️ ${formatNumber(post.views)}</span>` : ''}
                ${post.likes ? `<span title="좋아요">❤️ ${formatNumber(post.likes)}</span>` : ''}
            </div>
        </div>
    `;
}

// ==================== Selection & Deletion ====================

function toggleSelection(postId) {
    if (selectedPosts.has(postId)) {
        selectedPosts.delete(postId);
    } else {
        selectedPosts.add(postId);
    }
    updateSelectionUI();
}

function selectAll() {
    currentPosts.forEach(post => selectedPosts.add(post.id));
    updateSelectionUI();
}

function clearSelection() {
    selectedPosts.clear();
    updateSelectionUI();
}

function updateSelectionUI() {
    // Update count and bar visibility
    const count = selectedPosts.size;
    document.getElementById('selectionCount').textContent = count;
    document.getElementById('deleteSelectedBtn').disabled = count === 0;
    const dlBtn = document.getElementById('downloadSelectedBtn');
    if (dlBtn) dlBtn.disabled = count === 0;
    document.getElementById('selectionBar').style.display = count > 0 ? 'flex' : 'none';

    // Update individual checkboxes visually without re-rendering everything
    document.querySelectorAll('.post-card, .post-list-item').forEach(el => {
        // Find post ID from onclick attribute or data attribute if we added one
        // Parsing "openPostModal('ID')" from onclick is fragile, but we'll re-render for simplicity 
        // or use class based update if we can match elements to IDs easily.
        // For now, let's re-render visible visible items to be safe and simple
    });

    // Efficient update: toggle classes on existing elements
    // This requires us to know which element corresponds to which ID.
    // For now, re-render is safest but let's try to be smarter next time.
    // Actually, re-rendering just the visible page is fine.
    renderPosts();
}

async function deleteSelectedPosts() {
    const count = selectedPosts.size;
    if (count === 0) return;

    if (!confirm(`선택한 ${count}개의 항목을 영구적으로 삭제하시겠습니까? 관련 파일도 모두 삭제됩니다.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/posts`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: Array.from(selectedPosts) })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`${result.deleted_count}개 삭제 완료`, 'success');
            clearSelection();

            // Reload stats and posts
            loadStats();
            loadPosts();

            if (result.errors && result.errors.length > 0) {
                console.warn('Some deletions failed:', result.errors);
            }
        } else {
            showToast('삭제 실패', 'error');
        }
    } catch (error) {
        showToast('삭제 요청 중 오류 발생: ' + error.message, 'error');
    }
}

async function deleteSinglePost(postId) {
    if (!confirm('이 항목을 영구적으로 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/posts/${postId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('삭제 완료', 'success');
            closeModal();

            // Remove from selected if present
            if (selectedPosts.has(postId)) {
                selectedPosts.delete(postId);
                updateSelectionUI();
            }

            loadStats();
            loadPosts();
        } else {
            showToast('삭제 실패', 'error');
        }
    } catch (error) {
        showToast('오류 발생: ' + error.message, 'error');
    }
}

function renderPagination(total) {
    const container = document.getElementById('pagination');
    const totalPages = Math.ceil(total / postsPerPage);

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = `<button class="page-btn" onclick="goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>‹</button>`;

    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, currentPage + 2);

    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    html += `<button class="page-btn" onclick="goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>›</button>`;
    container.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    loadPosts();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function searchPosts() {
    currentPage = 1;
    loadPosts();
}

function applyFilters() {
    currentPage = 1;
    loadPosts();
}

function changeLimit() {
    postsPerPage = parseInt(document.getElementById('limitSelect').value);
    currentPage = 1;
    loadPosts();
}

function clearFilters() {
    document.querySelectorAll('#platformFilters input, #statusFilters input, #mediaFilters input').forEach(el => el.checked = false);
    document.querySelectorAll('#authorList input').forEach(el => el.checked = false);
    updateAuthorLabel();
    document.getElementById('sortSelect').value = 'scraped_at';
    document.getElementById('searchInput').value = '';
    document.getElementById('tagFilter').value = '';
    currentPage = 1;
    loadPosts();
}

function setView(view) {
    currentView = view;
    document.getElementById('gridViewBtn').classList.toggle('active', view === 'grid');
    document.getElementById('listViewBtn').classList.toggle('active', view === 'list');
    renderPosts();
}

// ==================== Modal ====================

async function openPostModal(postId) {
    const modal = document.getElementById('postModal');
    const modalBody = document.getElementById('modalBody');
    modal.classList.add('open');
    modalBody.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const response = await fetch(`${API_BASE}/api/posts/${postId}`);
        const post = await response.json();
        modalBody.innerHTML = renderModalContent(post);
    } catch (error) {
        modalBody.innerHTML = '<div class="empty-state"><div class="empty-state-title">불러오기 실패</div></div>';
    }
}

function renderModalContent(post) {
    const icons = { instagram: '📷', facebook: '📘', linkedin: '💼', threads: '🧵', unknown: '🔗' };
    const icon = icons[post.platform] || icons.unknown;
    const date = post.posted_at ? new Date(post.posted_at).toLocaleString('ko-KR') : '날짜 없음';

    let mediaHtml = '';

    // Check for local media first
    if (post.media_paths && post.media_paths.length > 0) {
        mediaHtml = `<div class="modal-media-gallery">`;
        post.media_paths.forEach(path => {
            // Check extension
            const isVideo = path.match(/\.(mp4|mov|webm)$/i);
            // Construct local URL via /media endpoint
            // path is absolute, we need accessible URL. 
            // Server mounts data/media at /media. 
            // We need to extract filename from path.
            const filename = path.split('/').pop();
            const url = `/media/${filename}`;

            if (isVideo) {
                mediaHtml += `<video src="${url}" controls class="modal-media-item"></video>`;
            } else {
                mediaHtml += `<img src="${url}" class="modal-media-item" loading="lazy">`;
            }
        });
        mediaHtml += `</div>`;
    }
    // Fallback to media_urls if no local files but URLs exist
    else if (post.media_urls && post.media_urls.length > 0) {
        mediaHtml = `<div class="modal-media-gallery">`;
        post.media_urls.forEach(url => {
            // Basic check, URLs might not have extension. 
            // Assume image for safety unless clearly video.
            mediaHtml += `<img src="${url}" class="modal-media-item" loading="lazy">`;
        });
        mediaHtml += `</div>`;
    }
    // Fallback to thumbnail
    else if (post.thumbnail_path) {
        mediaHtml = `<img src="/thumbnails/${post.id}.jpg" class="modal-thumbnail" alt="">`;
    }

    const stats = [];
    if (post.views !== null) stats.push({ label: '조회수', value: formatNumber(post.views) });
    if (post.likes !== null) stats.push({ label: '좋아요', value: formatNumber(post.likes) });
    if (post.comments !== null) stats.push({ label: '댓글', value: formatNumber(post.comments) });

    const statsHtml = stats.length > 0 ? `
        <div class="modal-stats">
            ${stats.map(s => `<div class="modal-stat"><span class="modal-stat-value">${s.value}</span><span class="modal-stat-label">${s.label}</span></div>`).join('')}
        </div>
    ` : '';

    // Tags
    const tagsHtml = `
        <div class="modal-tags">
            <div class="tags-list">
                ${(post.tags || []).map(tag => `
                    <span class="tag-badge">
                        ${tag}
                        <button class="tag-remove" onclick="removeTag('${post.id}', '${tag}')">×</button>
                    </span>
                `).join('')}
            </div>
            <div class="tag-input-wrapper">
                <input type="text" class="tag-input" placeholder="태그 추가 (Enter)" 
                       onkeyup="if(event.key === 'Enter') addTag('${post.id}', this.value)">
            </div>
        </div>
    `;

    // Error Message
    const errorHtml = post.error_message ? `
        <div class="error-box">
            <strong>⚠️ 오류: (${post.url})</strong><br>
            ${post.error_message}
        </div>
    ` : '';

    return `
        <div class="modal-header">
            <span class="modal-platform-icon">${icon}</span>
            <div class="modal-title">
                <div class="modal-author">${post.author || '알 수 없음'}</div>
                <div class="modal-date">${date}</div>
            </div>
            <span class="post-status-badge ${post.status}">${post.status}</span>
        </div>
        ${errorHtml}
        ${mediaHtml}
        <div class="modal-note-section" style="margin: 1.5rem 0; padding: 1rem; background: var(--bg-tertiary); border-radius: var(--radius-md);">
            <h4 style="margin-bottom: 0.5rem; font-size: 0.9rem; color: var(--text-secondary);">📝 메모</h4>
            <textarea id="postNoteInput" style="width: 100%; min-height: 80px; padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary); resize: vertical; margin-bottom: 0.5rem;" placeholder="메모를 입력하세요...">${post.note || ''}</textarea>
            <div style="display: flex; justify-content: flex-end;">
                <button class="btn btn-sm btn-primary" onclick="saveNote('${post.id}')">저장</button>
            </div>
        </div>
        ${post.content ? `<div class="modal-content-text">${post.content}</div>` : ''}
        ${tagsHtml}
        ${statsHtml}
        <div class="modal-url-box" style="margin: 1rem 0; padding: 0.5rem; background: var(--bg-tertiary); border-radius: var(--radius-sm); word-break: break-all; font-size: 0.85rem;">
            <div style="font-weight:600; margin-bottom:0.2rem; color:var(--text-secondary)">URL:</div>
            <a href="${post.url}" target="_blank" style="color:var(--accent-primary); text-decoration:none;">${post.url}</a>
        </div>
        <div class="modal-actions">
            <a href="${post.url}" target="_blank" class="modal-link">🔗 원본 바로가기</a>
        </div>
        ${post.source_file ? `<div style="margin-top:1rem;font-size:0.8rem;color:var(--text-muted)">📄 출처: ${post.source_file}</div>` : ''}
    `;
}

function closeModal() {
    document.getElementById('postModal').classList.remove('open');
}

// ==================== Progress & Toast ====================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => toast.classList.remove('show'), 4000);
}

function showProgress(show = true) {
    document.getElementById('taskProgress').style.display = show ? 'block' : 'none';
}

function updateProgress(taskName, progress, total, message) {
    document.getElementById('taskName').textContent = taskName;
    document.getElementById('taskDetail').textContent = `${progress}/${total}`;
    document.getElementById('taskMessage').textContent = message;
    const pct = total > 0 ? (progress / total) * 100 : 0;
    document.getElementById('progressFill').style.width = `${pct}%`;
}

function startTaskPolling() {
    if (taskPollingInterval) return;
    showProgress(true);

    taskPollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/task/status`);
            const status = await response.json();

            if (status.is_running) {
                updateProgress(status.current_task, status.progress, status.total, status.message);

                // Add new posts to grid in real-time
                if (status.recent_posts && status.recent_posts.length > 0) {
                    addRecentPosts(status.recent_posts);
                }
            } else {
                stopTaskPolling();
                showProgress(false);
                loadStats();
                loadPosts();
                checkInaccessible();
                showToast(status.message || '작업 완료!', 'success');
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 1000);
}

function addRecentPosts(recentPosts) {
    const container = document.getElementById('postsContainer');

    // If empty state showing, clear it first
    if (container.querySelector('.empty-state')) {
        container.innerHTML = '';
    }

    // Check if container class matches current view (sync check)
    if (!container.classList.contains(`${currentView}-view`)) {
        container.className = `posts-container ${currentView}-view`;
    }

    // Add to currentPosts array for state consistency (prepend)
    // Filter out duplicates that might be already there
    const newIds = new Set(recentPosts.map(p => p.id));
    const uniqueRecents = recentPosts.filter(p => !currentPosts.some(cp => cp.id === p.id));

    // Add to state if not already there (this is just for UI consistency if user switches view)
    // Note: This logic assumes recentPosts are truly new.
    // In a real app we might want to merge properly.

    const platformIcons = {
        instagram: '📷',
        facebook: '📘',
        linkedin: '💼',
        threads: '🧵',
        unknown: '🔗'
    };

    for (const post of recentPosts) {
        // Mark as accessible for UI even if backend didn't (it should have)
        post.status = 'accessible';

        let html = '';

        if (currentView === 'list') {
            // List View Item
            const icon = platformIcons[post.platform] || platformIcons.unknown;
            const date = '방금 전';

            let thumbnailHtml = post.thumbnail_path
                ? `<img src="/thumbnails/${post.id}.jpg" alt="" loading="lazy">`
                : `<div class="placeholder small">${icon}</div>`;

            html = `
                <div class="post-list-item new-post" onclick="openPostModal('${post.id}')">
                    <div class="list-thumb">
                        ${thumbnailHtml}
                        <span class="platform-icon">${icon}</span>
                    </div>
                    <div class="list-content">
                        <div class="list-header">
                            <span class="list-author">${post.author || '알 수 없음'}</span>
                            <span class="post-status-badge accessible mini">NEW</span>
                            <span class="list-date">${date}</span>
                        </div>
                        <div class="list-text">${post.content || post.title || '수집 중...'}</div>
                    </div>
                    <div class="list-meta">
                        ${post.views ? `<span title="조회수">👁️ ${formatNumber(post.views)}</span>` : ''}
                        ${post.likes ? `<span title="좋아요">❤️ ${formatNumber(post.likes)}</span>` : ''}
                    </div>
                </div>
            `;
        } else {
            // Grid View Card
            const icon = platformIcons[post.platform] || platformIcons.unknown;

            let thumbnailHtml = post.thumbnail_path
                ? `<img src="/thumbnails/${post.id}.jpg" alt="" loading="lazy">`
                : `<div class="placeholder">${icon}</div>`;

            const metaItems = [];
            if (post.views) metaItems.push(`👁️ ${formatNumber(post.views)}`);
            if (post.likes) metaItems.push(`❤️ ${formatNumber(post.likes)}`);

            html = `
                <div class="post-card new-post" onclick="openPostModal('${post.id}')">
                    <div class="post-thumbnail">
                        ${thumbnailHtml}
                        <span class="post-platform-badge">${icon}</span>
                        <span class="post-status-badge accessible">new</span>
                    </div>
                    <div class="post-info">
                        <div class="post-author">${post.author || '알 수 없음'}</div>
                        <div class="post-content">${post.content || '수집 중...'}</div>
                        <div class="post-meta">${metaItems.join(' • ') || '방금 수집'}</div>
                    </div>
                </div>
            `;
        }

        // Insert at beginning
        container.insertAdjacentHTML('afterbegin', html);
    }
}

function stopTaskPolling() {
    if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
        taskPollingInterval = null;
    }
}

function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

// ==================== Tags ====================

async function addTag(postId, tag) {
    tag = tag.trim();
    if (!tag) return;

    try {
        // Get current post to append tag
        const res = await fetch(`${API_BASE}/api/posts/${postId}`);
        const post = await res.json();

        const newTags = [...(post.tags || [])];
        if (!newTags.includes(tag)) {
            newTags.push(tag);

            const updateRes = await fetch(`${API_BASE}/api/posts/${postId}/tags`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags: newTags }),
            });

            if (updateRes.ok) {
                // Refresh modal
                openPostModal(postId);
                showToast('태그가 추가되었습니다', 'success');
            } else {
                showToast('태그 추가 실패', 'error');
            }
        }
    } catch (e) {
        console.error(e);
        showToast('태그 추가 오류', 'error');
    }
}

async function removeTag(postId, tagToRemove) {
    if (!confirm(`'${tagToRemove}' 태그를 삭제하시겠습니까?`)) return;

    try {
        const res = await fetch(`${API_BASE}/api/posts/${postId}`);
        const post = await res.json();

        const newTags = (post.tags || []).filter(t => t !== tagToRemove);

        const updateRes = await fetch(`${API_BASE}/api/posts/${postId}/tags`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags: newTags }),
        });

        if (updateRes.ok) {
            openPostModal(postId);
            showToast('태그가 삭제되었습니다', 'success');
        } else {
            showToast('태그 삭제 실패', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('태그 삭제 오류', 'error');
    }
}

async function downloadSelectedPosts() {
    if (selectedPosts.size === 0) return;
    if (taskPollingInterval) {
        showToast('다른 작업이 진행 중입니다', 'error');
        return;
    }

    const postIds = Array.from(selectedPosts);

    try {
        const response = await fetch(`${API_BASE}/api/download-batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ post_ids: postIds }),
        });

        const result = await response.json();
        if (result.success) {
            showToast(`선택한 ${result.count}개 항목 다운로드 시작 (저장위치: data/media)`, 'success');
            clearSelection();
            startTaskPolling();
        } else {
            showToast(result.detail || '다운로드 시작 실패', 'error');
        }
    } catch (error) {
        console.error('Download error:', error);
        showToast('다운로드 요청 실패', 'error');
    }
}

async function saveNote(postId) {
    const note = document.getElementById('postNoteInput').value;

    try {
        const response = await fetch(`${API_BASE}/api/posts/${postId}/note`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note: note }),
        });

        if (response.ok) {
            showToast('메모가 저장되었습니다', 'success');
        } else {
            showToast('메모 저장 실패', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('메모 저장 오류', 'error');
    }
}

// ==================== Author Dropdown ====================

function toggleAuthorDropdown() {
    const opts = document.getElementById('authorOptions');
    opts.classList.toggle('open');

    // Auto focus search if opening
    if (opts.classList.contains('open')) {
        opts.querySelector('.search-input').focus();
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function (e) {
    const dropdown = document.getElementById('authorDropdown');
    const opts = document.getElementById('authorOptions');
    if (dropdown && !dropdown.contains(e.target)) {
        opts.classList.remove('open');
    }
});

function filterAuthorOptions(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('#authorList .option-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? 'flex' : 'none';
    });
}

function updateAuthorLabel() {
    const checked = document.querySelectorAll('#authorList input:checked');
    const label = document.getElementById('authorSelectLabel');
    if (checked.length === 0) {
        label.textContent = "전체";
    } else if (checked.length === 1) {
        label.textContent = checked[0].value;
    } else {
        label.textContent = `${checked.length}명 선택됨`;
    }
}

async function openLocalFolder(postId) {
    try {
        const response = await fetch(`${API_BASE}/api/open/${postId}`, { method: 'POST' });
        const result = await response.json();
        if (!result.success) {
            showToast('폴더 열기 실패: ' + result.detail, 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('폴더 열기 요청 실패', 'error');
    }
}

// ==================== Analytics ====================

function setSort(key) {
    document.getElementById('sortSelect').value = key;
    applyFilters();
}

async function openAnalyticsModal() {
    try {
        const response = await fetch(`${API_BASE}/api/analytics`);
        const data = await response.json();
        renderAnalytics(data);
        document.getElementById('analyticsModal').classList.add('open');
    } catch (error) {
        console.error(error);
        showToast('통계 데이터 로드 실패', 'error');
    }
}

function closeAnalyticsModal() {
    document.getElementById('analyticsModal').classList.remove('open');
}

function renderAnalytics(data) {
    // 1. Author Stats Table
    const tbody = document.querySelector('#authorStatsTable tbody');
    tbody.innerHTML = data.author_stats.slice(0, 50).map(author => `
        <tr>
            <td>${author.name}</td>
            <td>${formatNumber(author.count)}</td>
            <td>${formatNumber(author.likes)}</td>
            <td>${formatNumber(author.comments)}</td>
        </tr>
    `).join('');

    // 2. Charts (Simple HTML Bar Charts)
    renderBarChart('platformChart', data.platform_counts);
    renderBarChart('mediaTypeChart', data.media_type_counts);
}

function renderBarChart(elementId, data) {
    const container = document.getElementById(elementId);
    if (!data) return;

    const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
    const maxVal = entries[0] ? entries[0][1] : 0;

    container.innerHTML = entries.map(([label, value]) => {
        const percent = maxVal > 0 ? (value / maxVal) * 100 : 0;
        return `
            <div class="chart-item">
                <div class="chart-label">${label}</div>
                <div class="chart-bar-bg">
                    <div class="chart-bar-fill" style="width: ${percent}%"></div>
                </div>
                <div class="chart-value">${formatNumber(value)}</div>
            </div>
        `;
    }).join('');
}


