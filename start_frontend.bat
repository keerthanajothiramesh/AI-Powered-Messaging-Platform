@echo off
echo Starting Frontend on http://localhost:5173
cd /d "%~dp0\frontend"

if not exist "node_modules" (
    echo Installing npm packages...
    npm install
)

npm run dev
