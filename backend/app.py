import ctypes
import os
import tempfile
import json
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Define the result structure to match C
class AnalysisResult(ctypes.Structure):
    _fields_ = [
        ('total_return', ctypes.c_double),
        ('accuracy', ctypes.c_double),
        ('predictions', ctypes.c_int),
        ('correct', ctypes.c_int),
        ('buy_hold', ctypes.c_double),
        ('alpha', ctypes.c_double),
        ('throughput', ctypes.c_double),
        ('elapsed_seconds', ctypes.c_double),
        ('total_bars', ctypes.c_int),
        ('error_message', ctypes.c_char * 256)
    ]

# Try to load C library
USE_C = False
try:
    # Try different possible paths
    possible_paths = [
        './backend/hft_engine.so',
        './hft_engine.so',
        '/opt/render/project/src/backend/hft_engine.so'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            lib = ctypes.CDLL(path)
            lib.analyze_csv_file.argtypes = [ctypes.c_char_p]
            lib.analyze_csv_file.restype = ctypes.POINTER(AnalysisResult)
            lib.free_analysis_result.argtypes = [ctypes.POINTER(AnalysisResult)]
            USE_C = True
            print(f"✅ Loaded C library from {path}")
            break
except Exception as e:
    print(f"⚠️ Could not load C library: {e}")

# HTML template (same as before, but add mode indicator)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HFT Analytics Platform | Quantitative Trading Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e9edf2 100%);
            min-height: 100vh;
            color: #1a1a2e;
        }

        /* Navbar */
        .navbar {
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #0066cc, #00cc99);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }

        .logo h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #0066cc, #00cc99);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }

        .badge {
            background: #00cc99;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        /* Main Container */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        /* Upload Card */
        .upload-card {
            background: white;
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.03), 0 1px 3px rgba(0,0,0,0.05);
            border: 1px solid rgba(0,0,0,0.05);
        }

        .upload-area {
            border: 2px dashed #cbd5e1;
            border-radius: 16px;
            padding: 2.5rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            background: #fafbfc;
        }

        .upload-area:hover {
            border-color: #0066cc;
            background: #f0f4f9;
        }

        .upload-area.drag-over {
            border-color: #00cc99;
            background: #e6f7f0;
        }

        .upload-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }

        .file-info {
            margin-top: 1rem;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 12px;
            display: none;
        }

        .file-info.show {
            display: block;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            border: 1px solid rgba(0,0,0,0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
        }

        .stat-label {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #64748b;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e;
        }

        .stat-value.positive {
            color: #00cc99;
        }

        .stat-value.negative {
            color: #ff4757;
        }

        .stat-sub {
            font-size: 0.75rem;
            color: #94a3b8;
            margin-top: 0.5rem;
        }

        /* Chart Container */
        .chart-container {
            background: white;
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            border: 1px solid rgba(0,0,0,0.05);
        }

        .chart-title {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #334155;
        }

        canvas {
            max-height: 300px;
        }

        /* Results Panel */
        .results-panel {
            background: white;
            border-radius: 20px;
            padding: 1.5rem;
            display: none;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            border: 1px solid rgba(0,0,0,0.05);
        }

        .results-panel.show {
            display: block;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Button */
        .analyze-btn {
            background: linear-gradient(135deg, #0066cc, #0052a3);
            color: white;
            border: none;
            padding: 12px 32px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 40px;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 1.5rem;
            width: 100%;
        }

        .analyze-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,102,204,0.3);
        }

        .analyze-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Loading Spinner */
        .spinner {
            display: none;
            text-align: center;
            padding: 2rem;
        }

        .spinner.show {
            display: block;
        }

        .spinner-circle {
            width: 40px;
            height: 40px;
            border: 3px solid #e2e8f0;
            border-top-color: #0066cc;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 1rem;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Preview Table */
        .preview-table {
            margin-top: 1rem;
            overflow-x: auto;
            font-size: 0.8rem;
        }

        .preview-table table {
            width: 100%;
            border-collapse: collapse;
        }

        .preview-table th, .preview-table td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }

        .preview-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #475569;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 2rem;
            color: #94a3b8;
            font-size: 0.8rem;
        }

        @media (max-width: 768px) {
            .container { padding: 1rem; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .stat-value { font-size: 1.5rem; }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <div class="logo">
                <div class="logo-icon">📊</div>
                <h1>HFT Analytics</h1>
                <span class="badge" id="engineBadge">Loading...</span>
            </div>
            <div style="font-size: 0.8rem; color: #64748b;">
                Quantitative Trading Dashboard
            </div>
        </div>
    </nav>

    <div class="container">
        <!-- Upload Card -->
        <div class="upload-card">
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📁</div>
                <h3>Upload Market Data</h3>
                <p style="color: #64748b; margin-top: 8px;">CSV format: Timestamp, Open, High, Low, Close, Volume</p>
                <input type="file" id="fileInput" accept=".csv" style="display: none;">
            </div>
            <div class="file-info" id="fileInfo">
                <strong>Selected file:</strong> <span id="fileName"></span>
                <div class="preview-table" id="previewTable"></div>
            </div>
            <button class="analyze-btn" id="analyzeBtn" disabled>⚡ Run HFT Analysis ⚡</button>
        </div>

        <!-- Loading Spinner -->
        <div class="spinner" id="spinner">
            <div class="spinner-circle"></div>
            <p>Processing with C engine...</p>
            <p style="font-size: 0.8rem; color: #64748b;">Lock-free ring buffer | 400k+ bars/sec</p>
        </div>

        <!-- Results Panel -->
        <div class="results-panel" id="resultsPanel">
            <div class="stats-grid" id="statsGrid"></div>
            <div class="chart-container">
                <div class="chart-title">📈 Performance Comparison</div>
                <canvas id="performanceChart"></canvas>
            </div>
            <div style="margin-top: 1rem; padding: 1rem; background: #f0f4f9; border-radius: 12px;">
                <p style="font-size: 0.9rem; color: #475569; margin-bottom: 8px;">🔬 What this means:</p>
                <ul style="margin-left: 1.5rem; color: #64748b; font-size: 0.85rem;">
                    <li><strong>Accuracy > 50%</strong> means better than random guessing</li>
                    <li><strong>Positive Alpha</strong> means strategy outperformed buy & hold</li>
                    <li><strong>Throughput</strong> shows C engine speed (Python would be 50x slower)</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            Built with C engine • Lock-free ring buffer • Real-time HFT pipeline
        </div>
    </div>

    <script>
        let selectedFile = null;
        let csvPreview = [];

        // Check engine health
        async function checkEngine() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                const badge = document.getElementById('engineBadge');
                if (data.engine === 'C') {
                    badge.textContent = 'C ENGINE • 400k bars/sec';
                    badge.style.background = '#00cc99';
                } else {
                    badge.textContent = 'Python (SLOW)';
                    badge.style.background = '#ff4757';
                }
            } catch(e) {
                document.getElementById('engineBadge').textContent = 'Engine: Unknown';
            }
        }

        // Preview CSV file
        function previewCSV(file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const text = e.target.result;
                const lines = text.split('\n').slice(0, 6); // First 5 rows
                const headers = lines[0].split(',');
                
                let html = '<table><thead><tr>';
                headers.forEach(h => html += `<th>${h.trim()}</th>`);
                html += '</tr></thead><tbody>';
                
                for (let i = 1; i < lines.length && i < 6; i++) {
                    const cells = lines[i].split(',');
                    if (cells.length >= 6) {
                        html += '<tr>';
                        cells.slice(0, 6).forEach(c => html += `<td>${c.trim()}</td>`);
                        html += '</tr>';
                    }
                }
                html += '</tbody></table><p style="margin-top: 8px; color: #64748b;">Preview: first 5 rows</p>';
                document.getElementById('previewTable').innerHTML = html;
            };
            reader.readAsText(file);
        }

        // Upload area handlers
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileNameSpan = document.getElementById('fileName');
        const analyzeBtn = document.getElementById('analyzeBtn');

        uploadArea.onclick = () => fileInput.click();
        
        uploadArea.ondragover = (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        };
        
        uploadArea.ondragleave = () => {
            uploadArea.classList.remove('drag-over');
        };
        
        uploadArea.ondrop = (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file && file.name.endsWith('.csv')) {
                handleFile(file);
            } else {
                alert('Please upload a CSV file');
            }
        };

        fileInput.onchange = (e) => {
            if (e.target.files[0]) handleFile(e.target.files[0]);
        };

        function handleFile(file) {
            selectedFile = file;
            fileNameSpan.textContent = file.name;
            fileInfo.classList.add('show');
            analyzeBtn.disabled = false;
            previewCSV(file);
        }

        // Analyze function
        analyzeBtn.onclick = async () => {
            if (!selectedFile) return;
            
            const formData = new FormData();
            formData.append('file', selectedFile);
            
            document.getElementById('spinner').classList.add('show');
            document.getElementById('resultsPanel').classList.remove('show');
            analyzeBtn.disabled = true;
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (data.success) {
                    displayResults(data);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error: ' + error);
            } finally {
                document.getElementById('spinner').classList.remove('show');
                analyzeBtn.disabled = false;
            }
        };

        function displayResults(data) {
            const statsGrid = document.getElementById('statsGrid');
            
            const stats = [
                { label: 'Strategy Return', value: data.total_return + '%', positive: data.total_return > 0 },
                { label: 'Buy & Hold', value: data.buy_hold + '%', positive: data.buy_hold > 0 },
                { label: 'Alpha', value: data.alpha + '%', positive: data.alpha > 0 },
                { label: 'Accuracy', value: data.accuracy + '%', positive: data.accuracy > 50 },
                { label: 'Predictions', value: data.predictions.toLocaleString(), positive: null },
                { label: 'Correct', value: data.correct.toLocaleString(), positive: null },
                { label: 'Throughput', value: data.throughput.toLocaleString() + ' bars/sec', positive: null },
                { label: 'Processing Time', value: data.elapsed_seconds + ' sec', positive: null }
            ];
            
            statsGrid.innerHTML = stats.map(stat => `
                <div class="stat-card">
                    <div class="stat-label">${stat.label}</div>
                    <div class="stat-value ${stat.positive === true ? 'positive' : stat.positive === false ? 'negative' : ''}">${stat.value}</div>
                </div>
            `).join('');
            
            // Create chart
            const ctx = document.getElementById('performanceChart').getContext('2d');
            if (window.performanceChart) window.performanceChart.destroy();
            
            window.performanceChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Strategy Return', 'Buy & Hold', 'Alpha'],
                    datasets: [{
                        label: 'Return (%)',
                        data: [data.total_return, data.buy_hold, data.alpha],
                        backgroundColor: ['#00cc99', '#0066cc', '#ff4757'],
                        borderRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { position: 'top' },
                        tooltip: { callbacks: { label: (ctx) => `${ctx.raw}%` } }
                    }
                }
            });
            
            document.getElementById('resultsPanel').classList.add('show');
        }

        checkEngine();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    mode = "C ENGINE (FAST)" if USE_C else "Python (Slow)"
    badge_class = "c-badge" if USE_C else ""
    return render_template_string(HTML_TEMPLATE, mode=mode, badge_class=badge_class)

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    
    try:
        if USE_C:
            # Call C library
            result_ptr = lib.analyze_csv_file(tmp_path.encode('utf-8'))
            result = result_ptr.contents
            
            if result.error_message.decode():
                response = {'success': False, 'error': result.error_message.decode()}
            else:
                response = {
                    'success': True,
                    'total_return': round(result.total_return, 2),
                    'accuracy': round(result.accuracy, 2),
                    'predictions': result.predictions,
                    'correct': result.correct,
                    'buy_hold': round(result.buy_hold, 2),
                    'alpha': round(result.alpha, 2),
                    'throughput': round(result.throughput, 0),
                    'elapsed_seconds': round(result.elapsed_seconds, 3),
                    'total_bars': result.total_bars,
                    'message': f"✅ C Engine: {result.predictions} predictions in {result.elapsed_seconds:.3f}s ({round(result.throughput):,} bars/sec)"
                }
            lib.free_analysis_result(result_ptr)
        else:
            # Python fallback (keep your existing analyze_csv_python function)
            response = {'success': False, 'error': 'C library not loaded'}
    
    except Exception as e:
        response = {'success': False, 'error': str(e)}
    
    os.unlink(tmp_path)
    return jsonify(response)

@app.route('/health')
def health():
    return jsonify({
        'status': 'HFT Pipeline Ready',
        'engine': 'C' if USE_C else 'Python',
        'version': '3.0'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)