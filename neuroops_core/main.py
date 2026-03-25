import threading
import time
from pipeline import run_pipeline
import uvicorn
from api import app

def start_pipeline():
    time.sleep(2)  # wait for uvicorn to fully start
    run_pipeline()

if __name__ == "__main__":
    t = threading.Thread(target=start_pipeline, daemon=True)
    t.start()
    print("[neuro-ops] starting API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")