@echo off
echo Installing Ollama models for Job Email Automation...
echo.
echo This downloads ~5-8 GB. Make sure Ollama is installed from https://ollama.com
echo.

ollama pull llama3.2-vision
if errorlevel 1 (
  echo.
  echo llama3.2-vision failed. Trying llava as fallback...
  ollama pull llava
)

ollama pull llama3.2
if errorlevel 1 (
  echo.
  echo llama3.2 failed. Trying llama3.1 as fallback...
  ollama pull llama3.1
)

echo.
echo Done! Installed models:
ollama list
echo.
echo Start the app with start-backend.bat and start-frontend.bat
pause
