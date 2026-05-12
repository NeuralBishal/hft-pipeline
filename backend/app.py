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
<html>
<head>
    <title>HFT Pipeline Analyzer</title>
    <style>
        body { font-family: 'Courier New', monospace; max-width: 800px; margin: 50px auto; padding: 20px; background: #0a0e27; color: #00ff88; }
        .container { background: #1a1f3a; border-radius: 10px; padding: 30px; box-shadow: 0 0 20px rgba(0,255,136,0.2); }
        h1 { text-align: center; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }
        .upload-area { border: 2px dashed #00ff88; border-radius: 10px; padding: 40px; text-align: center; cursor: pointer; margin: 20px 0; }
        .upload-area:hover { background: rgba(0,255,136,0.1); }
        button { background: #00ff88; color: #0a0e27; border: none; padding: 10px 30px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        button:hover { background: #00cc66; }
        .results { margin-top: 30px; padding: 20px; background: #0a0e27; border-radius: 5px; display: none; }
        .metric { display: inline-block; width: 45%; margin: 10px; padding: 10px; background: #1a1f3a; border-radius: 5px; }
        .metric-value { font-size: 24px; font-weight: bold; }
        .positive { color: #00ff88; }
        .negative { color: #ff4444; }
        .loading { text-align: center; display: none; }
        .badge { display: inline-block; background: #00ff88; color: #0a0e27; padding: 5px 10px; border-radius: 5px; font-size: 12px; margin-left: 10px; }
        .c-badge { background: #ff6600; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 HFT Pipeline Analyzer <span class="badge {{badge_class}}">{{mode}}</span></h1>
        <p style="text-align: center">Upload any stock CSV (Timestamp,Open,High,Low,Close,Volume) and get HFT-grade analysis!</p>
        
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <p>📁 Click to upload CSV file</p>
            <input type="file" id="fileInput" accept=".csv" style="display: none">
        </div>
        
        <div style="text-align: center">
            <button onclick="analyze()">⚡ Analyze Now ⚡</button>
        </div>
        
        <div class="loading" id="loading">
            <p>🔄 Processing with {{mode}} engine...</p>
        </div>
        
        <div class="results" id="results">
            <h3>📊 Analysis Results</h3>
            <div class="metric"><div>📈 Strategy Return</div><div class="metric-value" id="totalReturn">-</div></div>
            <div class="metric"><div>🎯 Prediction Accuracy</div><div class="metric-value" id="accuracy">-</div></div>
            <div class="metric"><div>📊 Total Predictions</div><div class="metric-value" id="predictions">-</div></div>
            <div class="metric"><div>✅ Correct Predictions</div><div class="metric-value" id="correct">-</div></div>
            <div class="metric"><div>💼 Buy & Hold Return</div><div class="metric-value" id="buyHold">-</div></div>
            <div class="metric"><div>⚡ Alpha vs Market</div><div class="metric-value" id="alpha">-</div></div>
            <div class="metric"><div>🚀 Throughput</div><div class="metric-value" id="throughput">-</div></div>
            <div class="metric"><div>⏱️ Processing Time</div><div class="metric-value" id="time">-</div></div>
            <p id="message" style="text-align: center; margin-top: 20px; color: #00ff88"></p>
        </div>
    </div>

    <script>
        async function analyze() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            if (!file) { alert('Please select a CSV file first!'); return; }
            
            const formData = new FormData();
            formData.append('file', file);
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            
            try {
                const response = await fetch('/analyze', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('totalReturn').innerHTML = data.total_return + '%';
                    document.getElementById('totalReturn').className = 'metric-value ' + (data.total_return > 0 ? 'positive' : 'negative');
                    document.getElementById('accuracy').innerHTML = data.accuracy + '%';
                    document.getElementById('predictions').innerHTML = data.predictions;
                    document.getElementById('correct').innerHTML = data.correct;
                    document.getElementById('buyHold').innerHTML = data.buy_hold + '%';
                    document.getElementById('buyHold').className = 'metric-value ' + (data.buy_hold > 0 ? 'positive' : 'negative');
                    document.getElementById('alpha').innerHTML = data.alpha + '%';
                    document.getElementById('alpha').className = 'metric-value ' + (data.alpha > 0 ? 'positive' : 'negative');
                    document.getElementById('throughput').innerHTML = data.throughput.toLocaleString() + ' bars/sec';
                    document.getElementById('time').innerHTML = data.elapsed_seconds + ' sec';
                    document.getElementById('message').innerHTML = data.message;
                    document.getElementById('results').style.display = 'block';
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error: ' + error);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
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