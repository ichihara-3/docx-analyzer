// Drag and drop functionality
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('file');
const fileInfo = document.getElementById('fileInfo');
const form = document.getElementById('analyzeForm');
const loadingDiv = document.getElementById('loading');

// Template descriptions
const templateDescriptions = {
    'default': 'リスクのある条項、追跡変更、コメントを総合的にレビューします',
    'risk_focus': '契約上のリスクを最優先で評価し、具体的な軽減策を提案します',
    'change_summary': '追跡変更の内容を分類し、各変更の影響度を評価します',
    'comment_review': 'インラインコメントへの対応を重点的に確認します',
    'custom': 'カスタムプロンプトを使用してレビューを実行します'
};

// Template prompts (matching PROMPT_TEMPLATES from llm_review.py)
const templatePrompts = {
    'default': `以下のレビュー指示に従ってください：

- リスクのある条項・不足している保護・曖昧な表現を指摘し、修正提案を添える
- 追跡履歴（add/delete）は「受け入れ/却下」の推奨と理由を述べる
- インラインコメントや指示に応答する
- 段落 index や comment_id を参照して特定しやすくする
- 短く行動可能な箇条書きでまとめること`,
    'risk_focus': `以下のレビュー指示に従ってください：

- **リスク重点レビュー**: 契約上のリスクを最優先で評価
- 損害賠償、解除条件、秘密保持、知的財産権などの重要条項を重点的に分析
- リスクレベル（高/中/低）を明示
- 各リスクに対する具体的な軽減策を提案
- 段落 index を参照して特定しやすくする
- 優先度順に箇条書きでまとめること`,
    'change_summary': `以下のレビュー指示に従ってください：

- **変更履歴サマリー**: 追跡変更の内容を要約
- 追加（add）、削除（delete）、移動（move）の各変更を分類
- 各変更の影響度を評価（重要/通常/軽微）
- 変更の受け入れ/却下の推奨と理由を明確に述べる
- 変更者（author）と日時（date）を含めて記載
- 段落 index を参照して特定しやすくする`,
    'comment_review': `以下のレビュー指示に従ってください：

- **コメント対応チェック**: インラインコメントへの対応を重点的に確認
- 各コメント（comment_id）に対する具体的な回答や対応案を提示
- コメントで指摘された問題点の妥当性を評価
- 対応の優先度を明示（必須/推奨/任意）
- コメント対象の段落 index と comment_id を参照
- 対応が必要なコメントを優先順に箇条書きでまとめること`,
    'custom': ''
};

// Prevent default drag behaviors
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
    document.body.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

// Highlight drop zone when dragging over it
['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => {
        dropZone.classList.add('drag-over');
    }, false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => {
        dropZone.classList.remove('drag-over');
    }, false);
});

// Handle dropped files
dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        displayFileInfo(files[0]);
    }
}, false);

// Handle file selection via input
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        displayFileInfo(e.target.files[0]);
    }
});

// Display file information
function displayFileInfo(file) {
    const sizeMB = (file.size / 1024 / 1024).toFixed(2);
    const sizeKB = (file.size / 1024).toFixed(1);
    const sizeText = sizeMB >= 1 ? `${sizeMB} MB` : `${sizeKB} KB`;

    // Validate file size
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        fileInfo.innerHTML = `❌ <strong>${file.name}</strong> (${sizeText}) - ファイルサイズが大きすぎます（上限: 10MB）`;
        fileInfo.style.background = '#fef2f2';
        fileInfo.style.color = '#b91c1c';
        fileInfo.classList.add('visible');
        return;
    }

    // Validate file type
    if (!file.name.toLowerCase().endsWith('.docx')) {
        fileInfo.innerHTML = `❌ <strong>${file.name}</strong> - DOCXファイルのみ対応しています`;
        fileInfo.style.background = '#fef2f2';
        fileInfo.style.color = '#b91c1c';
        fileInfo.classList.add('visible');
        return;
    }

    fileInfo.innerHTML = `✅ <strong>${file.name}</strong> (${sizeText})`;
    fileInfo.style.background = '#e0f2fe';
    fileInfo.style.color = '#0369a1';
    fileInfo.classList.add('visible');
}

// Template selection handler
const templateSelect = document.getElementById('template');
const templateInfo = document.getElementById('templateInfo');
const promptTextarea = document.getElementById('prompt');

templateSelect.addEventListener('change', (e) => {
    const selectedTemplate = e.target.value;
    templateInfo.textContent = templateDescriptions[selectedTemplate];

    // Load the template's default prompt into the textarea
    if (templatePrompts[selectedTemplate] !== undefined) {
        promptTextarea.value = templatePrompts[selectedTemplate];
    }
});

// Initialize template info and prompt on page load
window.addEventListener('DOMContentLoaded', () => {
    const selectedTemplate = templateSelect.value;
    templateInfo.textContent = templateDescriptions[selectedTemplate];

    // Load the initial template's prompt
    if (templatePrompts[selectedTemplate] !== undefined) {
        promptTextarea.value = templatePrompts[selectedTemplate];
    }
});

// Form submission handler
const loadingOverlay = document.getElementById('loadingOverlay');

form.addEventListener('submit', async (e) => {
    e.preventDefault(); // Prevent default form submission

    // Validate file before submission
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('ファイルを選択してください');
        return;
    }

    const file = fileInput.files[0];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (file.size > maxSize) {
        alert(`ファイルサイズが大きすぎます（${(file.size / 1024 / 1024).toFixed(1)}MB）。上限は10MBです。`);
        return;
    }

    if (!file.name.toLowerCase().endsWith('.docx')) {
        alert('DOCXファイルのみ対応しています');
        return;
    }

    // Show loading overlay
    loadingOverlay.classList.add('visible');

    // Prepare form data
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', document.getElementById('model').value);
    formData.append('template', document.getElementById('template').value);
    const promptValue = document.getElementById('prompt').value;
    if (promptValue) {
        formData.append('prompt', promptValue);
    }

    try {
        // Call API
        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            // Handle error
            loadingOverlay.classList.remove('visible');
            showError(data.error, data.error_type);
            return;
        }

        // Hide loading overlay
        loadingOverlay.classList.remove('visible');

        // Render results
        renderResults(data);

        // Scroll to results
        document.getElementById('results').scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        loadingOverlay.classList.remove('visible');
        showError('ネットワークエラーが発生しました: ' + error.message, 'network_error');
    }
});

function showError(message, errorType) {
    const errorHtml = `
    <div class="error">
      <div class="error-title">❌ エラーが発生しました</div>
      <p>${message}</p>
      ${getErrorSolutions(errorType)}
      <button type="button" onclick="window.location.reload()" style="margin-top: 12px;">
        🔄 もう一度試す
      </button>
    </div>
  `;

    // Insert error before form
    const container = document.querySelector('.container');
    const existingError = container.querySelector('.error');
    if (existingError) {
        existingError.remove();
    }
    form.insertAdjacentHTML('beforebegin', errorHtml);

    // Scroll to error
    container.querySelector('.error').scrollIntoView({ behavior: 'smooth' });
}

function getErrorSolutions(errorType) {
    const solutions = {
        'file_too_large': `
      <div class="error-solutions">
        <strong>対処方法:</strong>
        <ul>
          <li>ファイルサイズを10MB以下に削減してください</li>
          <li>不要な画像や埋め込みオブジェクトを削除してください</li>
          <li>ファイルを複数に分割することを検討してください</li>
        </ul>
      </div>
    `,
        'invalid_file_type': `
      <div class="error-solutions">
        <strong>対処方法:</strong>
        <ul>
          <li>ファイルの拡張子が .docx であることを確認してください</li>
          <li>.doc ファイルの場合は、Wordで開いて .docx 形式で保存し直してください</li>
        </ul>
      </div>
    `,
        'parse_error': `
      <div class="error-solutions">
        <strong>対処方法:</strong>
        <ul>
          <li>ファイルをWordで開いて再保存してください</li>
          <li>別のDOCXファイルで試してください</li>
          <li>ファイルが破損していないか確認してください</li>
        </ul>
      </div>
    `,
        'llm_error': `
      <div class="error-solutions">
        <strong>対処方法:</strong>
        <ul>
          <li>GOOGLE_API_KEY が正しく設定されているか確認してください</li>
          <li>APIキーの利用制限に達していないか確認してください</li>
          <li>しばらく時間をおいて再試行してください</li>
        </ul>
      </div>
    `
    };

    return solutions[errorType] || '';
}

function renderResults(data) {
    const resultsHtml = `
    <div class="result-section">
      <h3>📊 処理結果</h3>
      <div style="margin-bottom: 16px;">
        <span class="info-badge">📁 ${data.filename}</span>
        <span class="info-badge">📏 ${data.file_size} KB</span>
        <span class="info-badge">⏱️ ${data.processing_time} 秒</span>
        <span class="info-badge">🤖 ${data.model}</span>
      </div>
    </div>
    
    <div class="result-section">
      <details>
        <summary style="cursor: pointer; font-weight: bold; margin-bottom: 8px;">解析結果 (JSON)</summary>
        <div class="result-actions">
          <button type="button" class="secondary" onclick="copyToClipboard('analysisJson')">
            📋 JSONをコピー
          </button>
          <button type="button" class="secondary" onclick="downloadJson()">
            💾 JSONをダウンロード
          </button>
        </div>
        <pre id="analysisJson">${data.analysis_json}</pre>
      </details>
    </div>
    
    <div class="result-section">
      <h3>✨ LLM レビュー</h3>
      <div class="result-actions">
        <button type="button" class="secondary" onclick="copyToClipboard('reviewContent')">
          📋 レビューをコピー
        </button>
        <button type="button" class="secondary" onclick="downloadMarkdown()">
          💾 Markdownをダウンロード
        </button>
        <button type="button" class="secondary" onclick="downloadCommentedDocx()">
          📥 コメント付きDOCXをダウンロード
        </button>
      </div>
      <div class="markdown-body" id="reviewContent">
        ${data.review_html}
      </div>
    </div>
  `;

    // Remove existing results
    const existingResults = document.getElementById('results');
    if (existingResults) {
        existingResults.remove();
    }

    // Add new results
    const resultsDiv = document.createElement('div');
    resultsDiv.id = 'results';
    resultsDiv.innerHTML = resultsHtml;
    document.querySelector('.container').appendChild(resultsDiv);

    // Store data for download functions
    window.currentAnalysisData = data;
}

// Copy to clipboard function
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    const text = element.innerText || element.textContent;

    navigator.clipboard.writeText(text).then(() => {
        // Show success feedback
        const button = event.target;
        const originalText = button.textContent;
        button.textContent = '✅ コピーしました！';
        setTimeout(() => {
            button.textContent = originalText;
        }, 2000);
    }).catch(err => {
        alert('コピーに失敗しました: ' + err);
    });
}

// Download JSON function
function downloadJson() {
    const jsonText = window.currentAnalysisData?.analysis_json || document.getElementById('analysisJson').textContent;
    const blob = new Blob([jsonText], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'docx-analysis.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Download Markdown function
function downloadMarkdown() {
    const reviewText = window.currentAnalysisData?.review || document.getElementById('reviewContent').innerText;
    const blob = new Blob([reviewText], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'llm-review.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Download commented DOCX function
async function downloadCommentedDocx() {
    // Validate that we have a file selected
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('ファイルが選択されていません。先に解析を実行してください。');
        return;
    }

    const file = fileInput.files[0];

    // Show loading overlay
    loadingOverlay.classList.add('visible');

    // Prepare form data (same as analysis)
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model', document.getElementById('model').value);
    formData.append('template', document.getElementById('template').value);
    const promptValue = document.getElementById('prompt').value;
    if (promptValue) {
        formData.append('prompt', promptValue);
    }

    // Add current review text if available (for consistency)
    const currentReviewText = window.currentAnalysisData?.review;
    if (currentReviewText) {
        formData.append('review_text', currentReviewText);
    }

    try {
        // Call download API
        const response = await fetch('/api/download-commented', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            // Try to parse error message
            const data = await response.json();
            loadingOverlay.classList.remove('visible');
            alert('エラー: ' + (data.error || 'ダウンロードに失敗しました'));
            return;
        }

        // Get the blob from response
        const blob = await response.blob();

        // Create download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // Extract filename from Content-Disposition header or use default
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'reviewed.docx';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (filenameMatch && filenameMatch[1]) {
                filename = filenameMatch[1].replace(/['"]/g, '');
            }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // Hide loading overlay
        loadingOverlay.classList.remove('visible');

        // Show success feedback (only if event is available)
        if (typeof event !== 'undefined' && event.target) {
            const button = event.target;
            const originalText = button.textContent;
            button.textContent = '✅ ダウンロード完了！';
            setTimeout(() => {
                button.textContent = originalText;
            }, 2000);
        }

    } catch (error) {
        loadingOverlay.classList.remove('visible');
        alert('ダウンロードエラー: ' + error.message);
    }
}
