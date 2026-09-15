import os
import threading
import time
import serial
from flask import Flask, render_template_string, jsonify, request, Response
import cv2
import numpy as np
import board
import busio
import adafruit_mlx90640

app = Flask(__name__)

# --- GLOBAL TELEMETRY STORAGE ---
telemetry_data = {
    "gas1": 0, "gas2": 0, "gas3": 0,
    "distance": 0, "mode": "A"
}

# --- SERIAL CONFIGURATION ---
SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200
ser = None

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
except Exception as e:
    print(f"Warning: Serial connection failed ({e}).")

# --- CAMERA INITIALIZATION ---
camera_ready = False
try:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    # 4_HZ is the sweet spot for the Pi Zero's processing power
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ 
    camera_ready = True
    print("MLX90640 Thermal Camera Initialized!")
except Exception as e:
    print(f"Warning: Camera init failed. ({e})")

# --- BACKGROUND TASKS ---
def read_serial_loop():
    global ser, telemetry_data
    while True:
        if ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    parts = line.split(',')
                    temp_data = {}
                    for part in parts:
                        if ':' in part:
                            key, val = part.split(':')
                            temp_data[key.lower()] = val
                    
                    if "gas1" in temp_data:
                        telemetry_data.update({
                            "gas1": int(temp_data["gas1"]),
                            "gas2": int(temp_data["gas2"]),
                            "gas3": int(temp_data["gas3"]),
                            "distance": int(temp_data["dist"]),
                            "mode": temp_data["mode"]
                        })
            except Exception:
                pass
        time.sleep(0.05)

def generate_camera_frames():
    global camera_ready
    mlx_frame = [0] * 768 
    
    while True:
        if not camera_ready:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "CAMERA OFFLINE", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(1)
            continue
            
        try:
            mlx.getFrame(mlx_frame)
            data_array = np.array(mlx_frame).reshape((24, 32))
            
            # Use percentiles to ignore dead/noisy outlier pixels
            t_min = np.percentile(data_array, 3) 
            t_max = np.percentile(data_array, 97) 
            if t_max == t_min: t_max = t_min + 0.1 
            
            # Clip the array so any dead pixels are forced to the min/max limits
            data_array = np.clip(data_array, t_min, t_max)
                
            norm_img = 255 * ((data_array - t_min) / (t_max - t_min))
            norm_img = norm_img.astype(np.uint8)
            
            heatmap = cv2.applyColorMap(norm_img, cv2.COLORMAP_INFERNO)
            
            # Apply a slight blur to smooth out the blocky pixels
            heatmap = cv2.GaussianBlur(heatmap, (5, 5), 0)
            heatmap_resized = cv2.resize(heatmap, (640, 480), interpolation=cv2.INTER_CUBIC)
            
            cv2.putText(heatmap_resized, f"Max: {t_max:.1f} C", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            ret, buffer = cv2.imencode('.jpg', heatmap_resized)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
        except ValueError:
            # Common Pi Zero clock-stretching glitch. Skip and try the next frame.
            continue
        except Exception as e:
            # Print the exact error to the terminal
            print(f"CAMERA ERROR: {e}")
            # Send an error image to the dashboard so it doesn't show a broken HTML icon
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "SENSOR SYNC ERROR", (140, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.5)
            
        time.sleep(0.05)

# --- FLASK ROUTES ---
@app.route('/')
def index():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/telemetry')
def get_telemetry():
    return jsonify(telemetry_data)

@app.route('/api/command', methods=['POST'])
def send_command():
    global ser
    cmd = request.json.get('command')
    if ser and ser.is_open:
        ser.write(f"{cmd}\n".encode('utf-8'))
        return jsonify({"status": "success", "sent": cmd})
    return jsonify({"status": "error", "message": "Serial disconnected"}), 500

@app.route('/api/shutdown', methods=['POST'])
def shutdown_pi():
    os.system("sudo poweroff")
    return jsonify({"status": "shutting down"})

@app.route('/video_feed')
def video_feed():
    return Response(generate_camera_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- INLINE HTML DASHBOARD FRONTEND ---
HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Sewer & Mine Scout Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #121216; color: #f0f0f5; 
            margin: 0; padding: 12px; height: 100vh; overflow: hidden; 
            display: flex; flex-direction: column; gap: 12px;
        }
        
        /* HEADER */
        .header { flex-shrink: 0; display: flex; align-items: center; gap: 15px; }
        .header h2 { margin: 0; color: #aaa; font-weight: normal; font-size: 1.4rem; white-space: nowrap; }
        .alert-banner { flex-grow: 1; padding: 12px; font-weight: bold; font-size: 1.1rem; border-radius: 6px; text-transform: uppercase; text-align: center; margin: 0; }
        .safe { background: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
        .warning { background: #e65100; color: white; animation: blink 1.5s infinite; }
        .danger { background: #b71c1c; color: white; animation: blink 0.8s infinite; }
        
        /* MAIN LAYOUT: 2 Columns */
        .main-content {
            display: grid;
            grid-template-columns: 400px 1fr;
            gap: 15px;
            flex-grow: 1; min-height: 0;
        }
        
        .panel { background: #1e1e24; border-radius: 8px; border: 1px solid #2a2a35; padding: 15px; display: flex; flex-direction: column; }
        .panel-title { margin: 0 0 10px 0; font-size: 1rem; color: #888; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #333; padding-bottom: 5px;}
        
        /* LEFT COLUMN: Camera & Controls */
        .left-col { display: flex; flex-direction: column; gap: 15px; }
        .cam-container { width: 100%; aspect-ratio: 4/3; background: #000; border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; margin-bottom: 15px;}
        .cam-container img { width: 100%; height: 100%; object-fit: contain; }
        
        /* D-Pad Controls Layout */
        .mode-toggles { display: flex; gap: 10px; margin-bottom: 15px; }
        .d-pad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; max-width: 220px; margin: 0 auto 15px auto; }
        .btn { background: #3949ab; color: white; border: none; padding: 12px; font-size: 1rem; font-weight: bold; border-radius: 6px; cursor: pointer; transition: background 0.2s;}
        .btn:active { background: #283593; }
        .btn-full { width: 100%; }
        .btn-stop { background: #d32f2f; }
        .btn-stop:active { background: #b71c1c; }
        .btn-warn { background: #fbc02d; color: black; margin-top: auto;}
        
        /* RIGHT COLUMN: Data */
        .right-col { display: flex; flex-direction: column; gap: 15px; min-width: 0;}
        
        /* KPI Cards (Top Row) */
        .kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; flex-shrink: 0; }
        .kpi-card { background: #23232b; padding: 15px 10px; border-radius: 6px; text-align: center; border-left: 4px solid #555; }
        .kpi-card h3 { margin: 0; font-size: 0.85rem; color: #999; text-transform: uppercase; }
        .kpi-card h1 { margin: 8px 0 0 0; font-size: 1.8rem; font-weight: normal; }
        .border-red { border-color: #ff5252; }
        .border-blue { border-color: #448aff; }
        .border-green { border-color: #69f0ae; }
        
        /* Chart Container (Takes remaining height) */
        .chart-container { flex-grow: 1; min-height: 0; position: relative; background: #1a1a20; border-radius: 6px; padding: 10px; border: 1px solid #2a2a35;}
        
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <h2>🛰️ Mine Scout UI</h2>
        <div id="safety-alert" class="alert-banner safe">Initializing Sensors...</div>
    </div>

    <div class="main-content">
        
        <div class="left-col">
            <div class="panel" style="flex-grow: 1;">
                <h3 class="panel-title">Thermal Vision</h3>
                <div class="cam-container">
                    <img src="/video_feed" alt="Camera Stream">
                </div>
                
                <h3 class="panel-title">Navigation</h3>
                <div class="mode-toggles">
                    <button class="btn btn-full" onclick="sendCommand('MODE:A')">Auto Pilot</button>
                    <button class="btn btn-full" style="background:#5e35b1;" onclick="sendCommand('MODE:M')">Manual</button>
                </div>
                
                <div class="d-pad">
                    <div style="visibility:hidden;"></div>
                    <button class="btn" onclick="sendCommand('CMD:F')">W</button>
                    <div style="visibility:hidden;"></div>
                    
                    <button class="btn" onclick="sendCommand('CMD:L')">A</button>
                    <button class="btn btn-stop" onclick="sendCommand('CMD:S')">BRK</button>
                    <button class="btn" onclick="sendCommand('CMD:R')">D</button>
                    
                    <div style="visibility:hidden;"></div>
                    <button class="btn" onclick="sendCommand('CMD:B')">S</button>
                    <div style="visibility:hidden;"></div>
                </div>
                
                <button class="btn btn-warn btn-full" onclick="shutdownSystem()">⚠️ SHUTDOWN ROBOT</button>
            </div>
        </div>

        <div class="right-col">
            
            <div class="kpi-row">
                <div class="kpi-card">
                    <h3>Nav Mode</h3>
                    <h1 id="current-mode">Auto</h1>
                </div>
                <div class="kpi-card">
                    <h3>Clearance</h3>
                    <h1 id="dist-val">0 cm</h1>
                </div>
                <div class="kpi-card border-red">
                    <h3>Sensor 1</h3>
                    <h1 id="gas1-val" style="color:#ff5252;">0</h1>
                </div>
                <div class="kpi-card border-blue">
                    <h3>Sensor 2</h3>
                    <h1 id="gas2-val" style="color:#448aff;">0</h1>
                </div>
                <div class="kpi-card border-green">
                    <h3>Sensor 3</h3>
                    <h1 id="gas3-val" style="color:#69f0ae;">0</h1>
                </div>
            </div>

            <div class="panel" style="flex-grow: 1; padding: 10px;">
                <h3 class="panel-title" style="margin-left:5px;">Live Environmental Gas Trends</h3>
                <div class="chart-container">
                    <canvas id="gasChart"></canvas>
                </div>
            </div>
            
        </div>
    </div>

    <script>
        // Set chart defaults for a darker, sleeker look
        Chart.defaults.color = '#888';
        Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
        
        const ctx = document.getElementById('gasChart').getContext('2d');
        const gasChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(40).fill(''), // Keep more data points on screen
                datasets: [
                    { label: 'Sensor 1', borderColor: '#ff5252', backgroundColor: 'rgba(255,82,82,0.1)', data: Array(40).fill(0), borderWidth: 2, pointRadius: 0, tension: 0.4, fill: true },
                    { label: 'Sensor 2', borderColor: '#448aff', backgroundColor: 'rgba(68,138,255,0.1)', data: Array(40).fill(0), borderWidth: 2, pointRadius: 0, tension: 0.4, fill: true },
                    { label: 'Sensor 3', borderColor: '#69f0ae', backgroundColor: 'rgba(105,240,174,0.1)', data: Array(40).fill(0), borderWidth: 2, pointRadius: 0, tension: 0.4, fill: true }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                scales: { 
                    x: { display: false }, 
                    y: { display: true, min: 0, max: 1023, grid: { color: '#333' } } 
                },
                plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8 } } },
                interaction: { mode: 'index', intersect: false }
            }
        });

        setInterval(async () => {
            try {
                let response = await fetch('/api/telemetry');
                let data = await response.json();
                
                document.getElementById('gas1-val').innerText = data.gas1;
                document.getElementById('gas2-val').innerText = data.gas2;
                document.getElementById('gas3-val').innerText = data.gas3;
                document.getElementById('dist-val').innerText = data.distance + " cm";
                document.getElementById('current-mode').innerText = data.mode === "A" ? "Auto" : "Manual";

                gasChart.data.datasets[0].data.push(data.gas1);
                gasChart.data.datasets[1].data.push(data.gas2);
                gasChart.data.datasets[2].data.push(data.gas3);
                gasChart.data.datasets[0].data.shift();
                gasChart.data.datasets[1].data.shift();
                gasChart.data.datasets[2].data.shift();
                gasChart.update();

                let maxGas = Math.max(data.gas1, data.gas2, data.gas3);
                let alertBanner = document.getElementById('safety-alert');
                
                if (maxGas > 650) {
                    alertBanner.innerText = "❌ DANGER: Toxic Environment - Do Not Enter";
                    alertBanner.className = "alert-banner danger";
                } else if (maxGas > 350) {
                    alertBanner.innerText = "⚠️ WARNING: Elevated Gas Levels Detected";
                    alertBanner.className = "alert-banner warning";
                } else {
                    alertBanner.innerText = "✅ SAFE: Atmosphere Normal";
                    alertBanner.className = "alert-banner safe";
                }
            } catch (e) {}
        }, 500);

        async function sendCommand(cmd) {
            await fetch('/api/command', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({command: cmd}) });
        }

        async function shutdownSystem() {
            if(confirm("Are you sure you want to completely shut down the Pi?")) {
                await fetch('/api/shutdown', { method: 'POST' });
                document.body.innerHTML = "<h1 style='color:#ff5252; text-align:center; margin-top:20vh; font-size:3rem;'>System Shutting Down...<br>Safe to disconnect power in 15 seconds.</h1>";
            }
        }

        window.addEventListener('keydown', (e) => {
            if (e.key.toLowerCase() === 'w') sendCommand('CMD:F');
            if (e.key.toLowerCase() === 's') sendCommand('CMD:B');
            if (e.key.toLowerCase() === 'a') sendCommand('CMD:L');
            if (e.key.toLowerCase() === 'd') sendCommand('CMD:R');
            if (e.key === ' ') sendCommand('CMD:S');
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    threading.Thread(target=read_serial_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
