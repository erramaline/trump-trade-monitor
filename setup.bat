@echo off
REM Trump Trade Monitor — Windows setup

REM Python dependencies
pip install -r requirements.txt

REM Frontend
cd frontend
npm install
npm run build
cd ..

REM Config
IF NOT EXIST config.json (
    copy config.example.json config.json
    echo config.json created from example.
    echo Edit config.json with your API keys before running.
)

echo Setup complete!
echo Next: edit config.json with your keys, then run:
echo    run.bat
