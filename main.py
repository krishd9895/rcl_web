from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
import json

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Rclone Browser</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .path { margin-bottom: 20px; }
        .item { padding: 10px; border-bottom: 1px solid #eee; }
        .item:hover { background-color: #f5f5f5; }
        .folder { color: #2c3e50; }
        .file { color: #34495e; }
        .download-link { color: #3498db; text-decoration: none; }
        .breadcrumb { margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="breadcrumb" id="breadcrumb"></div>
    <div id="content"></div>

    <script>
        async function loadPath(remote, path = "") {
            const response = await fetch(`/api/list/${remote}/${path}`);
            const data = await response.json();
            
            const content = document.getElementById("content");
            const breadcrumb = document.getElementById("breadcrumb");
            
            // Update breadcrumb
            const parts = path.split("/").filter(p => p);
            let breadcrumbHtml = `<a href="#" onclick="loadPath('${remote}')">/${remote}</a>`;
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
        }

        function formatSize(bytes) {
            const sizes = ["B", "KB", "MB", "GB", "TB"];
            if (bytes === 0) return "0 B";
            const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
            return Math.round(bytes / Math.pow(1024, i), 2) + " " + sizes[i];
        }

        // Load remotes on page load
        fetch("/api/remotes")
            .then(response => response.json())
            .then(remotes => {
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
            });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_TEMPLATE

@app.get("/api/remotes")
async def list_remotes():
    output = subprocess.check_output(["rclone", "listremotes"], text=True)
    return [remote.strip(":") for remote in output.split()]

@app.get("/api/list/{remote}/{path:path}")
async def list_directory(remote: str, path: str = ""):
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
async def download_file(remote: str, path: str, background_tasks: BackgroundTasks):
    try:
        # Create a unique temporary directory for this download
        temp_dir = f"/tmp/rclone_download_{os.urandom(8).hex()}"
        os.makedirs(temp_dir, exist_ok=True)
        
        local_path = os.path.join(temp_dir, os.path.basename(path))
        
        # Use rclone copy command with proper error handling
        process = subprocess.run(
            ["rclone", "copy", f"{remote}:{path}", temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        
        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail="File not found or failed to download")
        
        # Return the file with proper cleanup
        return FileResponse(
            local_path,
            filename=os.path.basename(path),
            background=background_tasks.add_task(cleanup_temp_files, temp_dir)
        )
    
    except subprocess.CalledProcessError as e:
        # Clean up any temporary files that might have been created
        if 'temp_dir' in locals():
            cleanup_temp_files(temp_dir)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {e.stderr}"
        )
    except Exception as e:
        # Clean up any temporary files that might have been created
        if 'temp_dir' in locals():
            cleanup_temp_files(temp_dir)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while downloading the file: {str(e)}"
        )

# Helper function to clean up temporary files
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
