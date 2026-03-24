@echo off
REM Trump Trade Monitor — Windows launcher

IF NOT EXIST config.json (
    echo config.json not found. Running setup first...
    call setup.bat
)

REM Start the FastAPI server
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
