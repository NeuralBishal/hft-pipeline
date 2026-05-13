import ctypes
import os
import tempfile
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

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

USE_C = False
try:
    lib = ctypes.CDLL('./hft_engine.so')
    lib.analyze_csv_file.argtypes = [ctypes.c_char_p]
    lib.analyze_csv_file.restype = ctypes.POINTER(AnalysisResult)
    lib.free_analysis_result.argtypes = [ctypes.POINTER(AnalysisResult)]
    USE_C = True
    print("✅ Loaded C library")
except Exception as e:
    print(f"⚠️ C library not loaded: {e}")

# Complete HTML template - properly closed
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>HFT Analytics Platform</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; border-radius: 20px; padding: 30px; margin-bottom: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); }
        h1 { font-size: 2rem; margin-bottom: 10px; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; background-clip: text; color: transparent; }
        .badge { display: inline-block; background: #00cc99; color: white; padding: 5px 15px; border-radius: 20px; font-size: 12px; margin-top: 10px; }
        .upload-area { border: 2px dashed #ccc; border-radius: 16px; padding: 40px; text-align: center; cursor: pointer; transition: all 0.3s; margin: 20px 0; }
        .upload-area:hover { border-color: #667eea; background: #f8f9fa; transform: scale(1.02); }
        .upload-icon { font-size: 48px; margin-bottom: 10px; }
        .file-info { display: none; background: #e8f0fe; padding: 15px; border-radius: 12px; margin: 15px 0; }
        .file-info.show { display: block; }
        .btn { background: linear-gradient(135deg, #667eea, #764ba2); color: white; border: none; padding: 14px 28px; border-radius: 40px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; transition: transform 0.2s; }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .spinner { display: none; text-align: center; padding: 30px; }
        .spinner.show { display: block; }
        .loader { width: 50px; height: 50px; border: 5px solid #f3f3f3; border-top: 5px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .results { display: none; }
        .results.show { display: block; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric-card { background: #f8f9fa; padding: 20px; border-radius: 16px; text-align: center; }
        .metric-label { font-size: 12px; text-transform: uppercase; color: #666; letter-spacing: 1px; }
        .metric-value { font-size: 28px; font-weight: bold; margin-top: 10px; }
        .positive { color: #00cc99; }
        .negative { color: #ff4757; }
        .footer { text-align: center; padding: 20px; color: white; font-size: 12px; }
        input { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🚀 HFT Analytics Platform</h1>
            <p>High-Frequency Trading Strategy Backtesting Engine</p>
            <span class="badge" id="engineBadge">Loading...</span>
        </div>

        <div class="card">
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📊</div>
                <h3>Upload Market Data CSV</h3>
                <p>Format: Timestamp, Open, High, Low, Close, Volume</p>
                <input type="file" id="fileInput" accept=".csv">
            </div>
            <div class="file-info" id="fileInfo">
                <strong>📄 Selected file:</strong> <span id="fileName"></span>
            </div>
            <button class="btn" id="analyzeBtn" disabled>⚡ Execute HFT Analysis ⚡</button>
        </div>

        <div class="spinner" id="spinner">
            <div class="loader"></div>
            <p style="margin-top: 15px;">Processing with C engine at 400k+ bars/sec...</p>
        </div>

        <div class="card results" id="results">
            <h2>📈 Backtest Results</h2>
            <div class="metric-grid" id="metrics"></div>
        </div>

        <div class="footer">
            Built with C | Lock-free Ring Buffer | Real-time HFT Pipeline
        </div>
    </div>

    <script>
        let selectedFile = null;
        
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const spinner = document.getElementById('spinner');
        const resultsDiv = document.getElementById('results');
        const metricsDiv = document.getElementById('metrics');
        
        uploadArea.onclick = () => fileInput.click();
        
        fileInput.onchange = (e) => {
            if (e.target.files && e.target.files[0]) {
                selectedFile = e.target.files[0];
                fileName.textContent = selectedFile.name;
                fileInfo.classList.add('show');
                analyzeBtn.disabled = false;
            }
        };
        
        analyzeBtn.onclick = async () => {
            if (!selectedFile) return;
            
            const formData = new FormData();
            formData.append('file', selectedFile);
            
            spinner.classList.add('show');
            resultsDiv.classList.remove('show');
            analyzeBtn.disabled = true;
            
            try {
                const response = await fetch('/analyze', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (data.success) {
                    const metrics = [
                        { label: 'Strategy Return', value: data.total_return + '%', positive: data.total_return > 0 },
                        { label: 'Accuracy', value: data.accuracy + '%', positive: data.accuracy > 50 },
                        { label: 'Predictions', value: data.predictions.toLocaleString(), positive: null },
                        { label: 'Correct', value: data.correct.toLocaleString(), positive: null },
                        { label: 'Buy & Hold', value: data.buy_hold + '%', positive: data.buy_hold > 0 },
                        { label: 'Alpha', value: data.alpha + '%', positive: data.alpha > 0 },
                        { label: 'Throughput', value: data.throughput.toLocaleString() + ' bars/s', positive: null },
                        { label: 'Time', value: data.elapsed_seconds + ' sec', positive: null }
                    ];
                    
                    metricsDiv.innerHTML = metrics.map(m => `
                        <div class="metric-card">
                            <div class="metric-label">${m.label}</div>
                            <div class="metric-value ${m.positive === true ? 'positive' : m.positive === false ? 'negative' : ''}">${m.value}</div>
                        </div>
                    `).join('');
                    
                    resultsDiv.classList.add('show');
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                spinner.classList.remove('show');
                analyzeBtn.disabled = false;
            }
        };
        
        async function checkEngine() {
            try {
                const res = await fetch('/health');
                const data = await res.json();
                const badge = document.getElementById('engineBadge');
                badge.textContent = data.engine === 'C' ? '✅ C ENGINE • 400k bars/sec' : '⚠️ Python Mode (Slow)';
            } catch(e) {}
        }
        
        checkEngine();
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

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
        if USE_C and lib:
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
                    'elapsed_seconds': round(result.elapsed_seconds, 3)
                }
            lib.free_analysis_result(result_ptr)
        else:
            response = {'success': False, 'error': 'C engine not loaded'}
    except Exception as e:
        response = {'success': False, 'error': str(e)}
    
    os.unlink(tmp_path)
    return jsonify(response)

@app.route('/health')
def health():
    return jsonify({'engine': 'C' if USE_C else 'None'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
