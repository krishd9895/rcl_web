from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import subprocess
import os
import json
import requests
import secrets
import shutil

app = FastAPI()
security = HTTPBasic()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get credentials from environment variables
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    if not AUTH_USERNAME or not AUTH_PASSWORD:
        return  # No authentication if credentials aren't set
        
    correct_username = secrets.compare_digest(credentials.username, AUTH_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, AUTH_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# Modified HTML template with login status
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Rclone Browser</title>
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --item-hover: #f5f5f5;
            --border-color: #eee;
            --button-bg: #3498db;
            --button-hover: #2980b9;
            --header-bg: #f8f9fa;
            --modal-bg: #ffffff;
            --modal-shadow: rgba(0, 0, 0, 0.1);
            --folder-color: #e67e22;
            --file-color: #16a085;
        }

        [data-theme="dark"] {
            --bg-color: #1a1a1a;
            --text-color: #e0e0e0;
            --item-hover: #2d2d2d;
            --border-color: #333;
            --button-bg: #2980b9;
            --button-hover: #3498db;
            --header-bg: #2d2d2d;
            --modal-bg: #2d2d2d;
            --modal-shadow: rgba(255, 255, 255, 0.1);
            --folder-color: #f39c12;
            --file-color: #1abc9c;
        }

        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-color);
            transition: background-color 0.3s, color 0.3s;
        }

        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            padding: 10px 20px;
            background: var(--header-bg);
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            z-index: 1000;
            border-bottom: 1px solid var(--border-color);
        }

        .content-wrapper {
            margin-top: 60px;
        }

        .modal {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--modal-bg);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px var(--modal-shadow);
            z-index: 1001;
            max-width: 500px;
            width: 90%;
        }

        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
        }

        .button {
            background: var(--button-bg);
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.3s;
        }

        .button:hover {
            background: var(--button-hover);
        }

        .item {
            padding: 10px;
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.3s;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .item:hover {
            background-color: var(--item-hover);
        }

        .folder {
            color: var(--folder-color);
            font-weight: bold;
        }

        .file {
            color: var(--file-color);
        }

        .download-link {
            color: var(--button-bg);
            text-decoration: none;
        }

        .breadcrumb {
            margin-bottom: 20px;
            color: var(--text-color);
        }

        .breadcrumb a {
            color: var(--button-bg);
            text-decoration: none;
        }

        .config-upload {
            text-align: center;
            margin: 50px auto;
            max-width: 500px;
        }

        #configMessage {
            margin-top: 10px;
            padding: 10px;
            border-radius: 4px;
        }

        .error-message {
            background: #ff595e;
            color: white;
        }

        .success-message {
            background: #8ac926;
            color: white;
        }
    </style>
</head>
<body>
    <div class="header">
        <button id="settingsBtn" class="button" style="display: none;">⚙️ Settings</button>
        <button id="themeToggle" class="button">🌓</button>
    </div>

    <div class="content-wrapper">
        <div id="uploadSection" class="config-upload" style="display: none;">
            <h2>Upload Rclone Configuration</h2>
            <form id="uploadForm" enctype="multipart/form-data" onsubmit="uploadConfig(event)">
                <input type="file" id="configFile" accept=".conf" required>
                <button type="submit" class="button">Upload Config</button>
            </form>
            <div id="configMessage"></div>
        </div>

        <div id="mainContent">
            <div class="breadcrumb" id="breadcrumb"></div>
            <div id="content"></div>
        </div>
    </div>

    <div id="settingsModal" class="modal">
        <h3>Update Configuration</h3>
        <form id="updateConfigForm" enctype="multipart/form-data" onsubmit="uploadConfig(event)">
            <input type="file" id="updateConfigFile" accept=".conf" required>
            <button type="submit" class="button">Update Config</button>
        </form>
        <div id="updateConfigMessage"></div>
        <button class="button" onclick="closeSettingsModal()" style="margin-top: 10px;">Close</button>
    </div>
    <div id="modalOverlay" class="modal-overlay" onclick="closeSettingsModal()"></div>

    <script>
        // Theme management
        const theme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', theme);

        document.getElementById('themeToggle').addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });

        // Settings modal
        function showSettingsModal() {
            document.getElementById('settingsModal').style.display = 'block';
            document.getElementById('modalOverlay').style.display = 'block';
        }

        function closeSettingsModal() {
            document.getElementById('settingsModal').style.display = 'none';
            document.getElementById('modalOverlay').style.display = 'none';
        }

        // Load remotes function
        async function loadRemotes() {
            try {
                const response = await fetch("/api/remotes");
                if (response.status === 401) {
                    window.location.reload();  // Trigger browser's auth prompt
                    return;
                }
                const remotes = await response.json();
                const content = document.getElementById("content");
                let html = "<div class='items'>";
                remotes.forEach(remote => {
                    html += `
                        <div class="item folder">
                            🗄️ <a href="#" onclick="loadPath('${remote}')">${remote}</a>
                        </div>`;
                });
                html += "</div>";
                content.innerHTML = html;
                document.getElementById('breadcrumb').innerHTML = 'Home';
            } catch (error) {
                showMessage('Error loading remotes: ' + error.message, true);
            }
        }

        // Load path function
        async function loadPath(remote, path = "") {
            try {
                const response = await fetch(`/api/list/${remote}/${path}`);
                if (response.status === 401) {
                    window.location.reload();  // Trigger browser's auth prompt
                    return;
                }
                const data = await response.json();
                
                const content = document.getElementById("content");
                const breadcrumb = document.getElementById("breadcrumb");
                
                // Update breadcrumb
                const parts = path.split("/").filter(p => p);
                let breadcrumbHtml = `<a href="#" onclick="loadRemotes()">Home</a> / <a href="#" onclick="loadPath('${remote}')">/${remote}</a>`;
                let currentPath = "";
                parts.forEach(part => {
                    currentPath += "/" + part;
                    breadcrumbHtml += ` / <a href="#" onclick="loadPath('${remote}', '${currentPath.slice(1)}')">${part}</a>`;
                });
                breadcrumb.innerHTML = breadcrumbHtml;
                
                // Update content
                let html = "<div class='items'>";
                data.folders.forEach(folder => {
                    const folderPath = path ? `${path}/${folder}` : folder;
                    html += `
                        <div class="item folder">
                            📁 <a href="#" onclick="loadPath('${remote}', '${folderPath}')">${folder}</a>
                        </div>`;
                });
                
                data.files.forEach(file => {
                    const filePath = path ? `${path}/${file.name}` : file.name;
                    html += `
                        <div class="item file">
                            📄 ${file.name} (${formatSize(file.size)})
                            <a class="download-link" href="/download/${remote}/${filePath}" target="_blank">⬇️ Download</a>
                        </div>`;
                });
                html += "</div>";
                content.innerHTML = html;
            } catch (error) {
                showMessage('Error loading path: ' + error.message, true);
            }
        }

        function formatSize(bytes) {
            const sizes = ["B", "KB", "MB", "GB", "TB"];
            if (bytes === 0) return "0 B";
            const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
            return Math.round(bytes / Math.pow(1024, i), 2) + " " + sizes[i];
        }

        // Check if config exists and show appropriate UI
        async function checkConfigExists() {
            try {
                const response = await fetch('/api/config/check');
                const data = await response.json();
                
                if (data.exists) {
                    document.getElementById('uploadSection').style.display = 'none';
                    document.getElementById('mainContent').style.display = 'block';
                    document.getElementById('settingsBtn').style.display = 'block';
                    loadRemotes();  // Load remotes when config exists
                } else {
                    document.getElementById('uploadSection').style.display = 'block';
                    document.getElementById('mainContent').style.display = 'none';
                    document.getElementById('settingsBtn').style.display = 'none';
                }
            } catch (error) {
                showMessage('Error checking configuration', true);
            }
        }

        async function uploadConfig(event) {
            event.preventDefault();
            const formData = new FormData();
            const fileInput = event.target.querySelector('input[type="file"]');
            formData.append('config_file', fileInput.files[0]);

            try {
                const response = await fetch('/api/config/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                if (response.ok) {
                    showMessage('Configuration updated successfully!', false);
                    setTimeout(() => window.location.reload(), 2000);
                } else {
                    showMessage(result.detail || 'Failed to upload config', true);
                }
            } catch (error) {
                showMessage('Error uploading config file', true);
            }
        }

        function showMessage(message, isError) {
            const messageDiv = document.getElementById('configMessage');
            const updateMessageDiv = document.getElementById('updateConfigMessage');
            messageDiv.textContent = message;
            updateMessageDiv.textContent = message;
            messageDiv.className = isError ? 'error-message' : 'success-message';
            updateMessageDiv.className = isError ? 'error-message' : 'success-message';
            setTimeout(() => {
                messageDiv.textContent = '';
                updateMessageDiv.textContent = '';
                messageDiv.className = '';
                updateMessageDiv.className = '';
            }, 5000);
        }

        // Initialize
        document.getElementById('settingsBtn').addEventListener('click', showSettingsModal);
        checkConfigExists();
    </script>
</body>
</html>
"""

# Add new endpoint to check if config exists
@app.get("/api/config/check")
async def check_config(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    config_path = "/config/rclone/rclone.conf"
    return {"exists": os.path.exists(config_path) and os.path.getsize(config_path) > 0}

# Modified upload endpoint
@app.post("/api/config/upload")
async def upload_config(
    config_file: UploadFile = File(...),
    credentials: HTTPBasicCredentials = Depends(verify_credentials)
):
    if not config_file.filename.endswith('.conf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be a .conf file")
    
    config_dir = "/config/rclone"
    config_path = os.path.join(config_dir, "rclone.conf")
    
    # Create backup of existing config if it exists
    if os.path.exists(config_path):
        backup_path = f"{config_path}.backup"
        shutil.copy2(config_path, backup_path)
    
    try:
        # Save the new config file
        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, "wb") as buffer:
            shutil.copyfileobj(config_file.file, buffer)
        
        # Verify the new config file
        try:
            subprocess.run(["rclone", "listremotes"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # If verification fails, restore backup if it exists
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, config_path)
            raise HTTPException(status_code=400, detail="Invalid rclone configuration file")
        
        return {"message": "Configuration updated successfully"}
        
    except Exception as e:
        # Restore backup if it exists
        if 'backup_path' in locals() and os.path.exists(backup_path):
            shutil.copy2(backup_path, config_path)
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")
    
    finally:
        # Clean up backup file
        if 'backup_path' in locals() and os.path.exists(backup_path):
            os.remove(backup_path)

# Add authentication to all routes
@app.get("/", response_class=HTMLResponse)
async def root(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return HTML_TEMPLATE

@app.get("/api/auth-status")
async def auth_status(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return {
        "auth_required": bool(AUTH_USERNAME and AUTH_PASSWORD),
        "username": credentials.username if (AUTH_USERNAME and AUTH_PASSWORD) else None
    }

@app.get("/api/remotes")
async def list_remotes(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    output = subprocess.check_output(["rclone", "listremotes"], text=True)
    return [remote.strip(":") for remote in output.split()]

@app.get("/api/list/{remote}/{path:path}")
async def list_directory(
    remote: str, 
    path: str = "", 
    credentials: HTTPBasicCredentials = Depends(verify_credentials)
):
    command = ["rclone", "lsjson", f"{remote}:{path}"]
    output = subprocess.check_output(command, text=True)
    
    items = json.loads(output)
    
    folders = []
    files = []
    
    for item in items:
        if item["IsDir"]:
            folders.append(item["Name"])
        else:
            files.append({
                "name": item["Name"],
                "size": item["Size"],
                "modified": item["ModTime"]
            })
    
    return {"folders": sorted(folders), "files": sorted(files, key=lambda x: x["name"])}

@app.get("/download/{remote}/{path:path}")
async def download_file(
    remote: str, 
    path: str, 
    background_tasks: BackgroundTasks,
    credentials: HTTPBasicCredentials = Depends(verify_credentials)
):
    try:
        temp_dir = f"/tmp/rclone_download_{os.urandom(8).hex()}"
        os.makedirs(temp_dir, exist_ok=True)
        
        local_path = os.path.join(temp_dir, os.path.basename(path))
        
        process = subprocess.run(
            ["rclone", "copy", f"{remote}:{path}", temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        
        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail="File not found or failed to download")
        
        return FileResponse(
            local_path,
            filename=os.path.basename(path),
            background=background_tasks.add_task(cleanup_temp_files, temp_dir)
        )
    
    except subprocess.CalledProcessError as e:
        if 'temp_dir' in locals():
            cleanup_temp_files(temp_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {e.stderr}"
        )
    except Exception as e:
        if 'temp_dir' in locals():
            cleanup_temp_files(temp_dir)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while downloading the file: {str(e)}"
        )

def cleanup_temp_files(temp_dir: str):
    try:
        if os.path.exists(temp_dir):
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temporary files: {e}")
