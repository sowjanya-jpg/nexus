import os
import time
import random
import requests
import pandas as pd
from datetime import datetime

API_STREAM_URL = "http://localhost:8000/api/v1/ingest/stream"
LANDING_DIR = "./data_landing"

# Ensure data landing directory exists for batch data
os.makedirs(LANDING_DIR, exist_ok=True)

machines = ["CNC-01", "CNC-02", "ROBOT-ARM-01", "PRESS-05", "CONVEYOR-03"]
operators = ["Alice", "Bob", "Charlie", "Diana"]
states = ["ACTIVE", "ACTIVE", "ACTIVE", "IDLE", "DOWN", "MAINTENANCE"]

def generate_sensor_reading(machine_id: str) -> dict:
    """
    Generate simulated IoT sensor metrics for a machine.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # CNC machines run hot and vibrate, conveyor is slow but steady
    if "CNC" in machine_id:
        temp = random.normalvariate(72.5, 5.0)
        vibration = random.normalvariate(1.8, 0.4)
        speed = random.normalvariate(12000, 150)
    elif "ROBOT" in machine_id:
        temp = random.normalvariate(45.0, 2.0)
        vibration = random.normalvariate(0.5, 0.1)
        speed = random.normalvariate(1500, 50)
    else: # Conveyor, press
        temp = random.normalvariate(35.0, 1.5)
        vibration = random.normalvariate(0.9, 0.2)
        speed = random.normalvariate(200, 10)

    # Induce an anomaly occasionally
    if random.random() < 0.05:
        temp += 30.0 # Overheating
        vibration *= 3.0 # Heavy mechanical wear
        print(f"⚠️ [ANOMALY INDUCED] Machine {machine_id} reporting severe metrics!")
        
    return {
        "timestamp": timestamp,
        "machine_id": machine_id,
        "temperature_celsius": round(temp, 2),
        "vibration_amplitude_mms": round(vibration, 3),
        "rotational_speed_rpm": round(speed, 1),
        "system_load_pct": round(random.uniform(20.0, 95.0), 1)
    }

def generate_status_log(machine_id: str) -> dict:
    """
    Generate batch transaction/log data.
    """
    return {
        "log_id": f"LOG-{random.randint(100000, 999999)}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "machine_id": machine_id,
        "operator": random.choice(operators),
        "current_state": random.choice(states),
        "shift_type": "DAY" if datetime.utcnow().hour in range(6, 18) else "NIGHT",
        "error_code": f"ERR-{random.randint(100, 999)}" if random.random() < 0.1 else "NONE"
    }

def main():
    print("🚀 NEXUS Forge Manufacturing Data Simulator Started.")
    print(f"Streaming data endpoint: {API_STREAM_URL}")
    print(f"Batch landing directory: {LANDING_DIR}")
    print("Generating events... Press Ctrl+C to stop.")
    
    count = 0
    batch_logs = []
    
    while True:
        try:
            # 1. Stream IoT sensor readings (every second, pick a random machine)
            machine = random.choice(machines)
            iot_event = generate_sensor_reading(machine)
            
            # Post to FastAPI streaming ingestion endpoint
            try:
                response = requests.post(
                    API_STREAM_URL, 
                    json=iot_event, 
                    params={"topic": "iot-sensor-stream"},
                    timeout=1.0
                )
                if response.status_code == 200:
                    print(f"📡 [Streamed] {machine} -> Temp: {iot_event['temperature_celsius']}°C, Vibr: {iot_event['vibration_amplitude_mms']} mm/s")
                else:
                    print(f"❌ Failed to stream: {response.text}")
            except requests.exceptions.ConnectionError:
                print("⏳ Stream failed: Backend API offline, buffering...")
                
            # 2. Accumulate status logs for batch output
            status_event = generate_status_log(machine)
            batch_logs.append(status_event)
            
            count += 1
            
            # Every 15 cycles (15 seconds), write batch data to landing directory
            if count % 15 == 0:
                batch_file = f"{LANDING_DIR}/machine_logs_{int(time.time())}.csv"
                df = pd.DataFrame(batch_logs)
                df.to_csv(batch_file, index=False)
                print(f"📦 [Batch CSV Created] Saved {len(batch_logs)} events to {batch_file}")
                batch_logs = [] # Reset buffer
                
            time.sleep(1.0)
            
        except KeyboardInterrupt:
            print("\nShutting down simulator.")
            break
        except Exception as e:
            print(f"Simulator error: {e}")
            time.sleep(2.0)

if __name__ == "__main__":
    main()
