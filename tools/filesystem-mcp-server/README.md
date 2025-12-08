# Filesystem MCP Server

This project provides an MCP (Model Context Protocol) server that allows safe interaction with the local filesystem. It supports reading, writing, editing, and managing files and directories within **allowed directories only**.

---

## Features

- **Safe Path Validation**: Restricts operations to `ALLOWED_DIRS` for security.
- **Tools Available**:
  
  **Basic File Operations:**
  - `read_file` – Read the contents of a file.
  - `write_file` – Write content to a file (create or overwrite).
  - `edit_file` – Add, delete, or replace specific lines in a file.
  
  **Directory Operations:**
  - `list_directory` – List files and directories in a given path.
  - `create_directory` – Create a new directory.
  - `search_files` – Search for files by name pattern.
  - `get_file_info` – Retrieve metadata about a file or directory.
  
  **CSV Operations:**
  - `csv_read` – Read and parse CSV files with optional delimiter and header handling.
  - `csv_write` – Write data to CSV files with custom delimiters and headers.
  
  **Excel Operations:**
  - `excel_read` – Read Excel files and extract data by sheet.
  - `excel_write` – Write data to Excel files with custom sheet names and headers.
  
  **Compression Operations:**
  - `zip_compress` – Compress files or directories into ZIP archives.
  - `zip_decompress` – Extract files from ZIP archives.
  - `gzip_compress` – Compress files using GZIP.
  - `gzip_decompress` – Decompress GZIP files.

---

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `ALLOWED_DIRS` in `server.py` to specify which directories can be accessed:

```python
ALLOWED_DIRS = [
    Path(r"C:\Users\steph\workspace")
]
```

## Usage

Run the server:

```bash
python server.py
```

The server communicates via stdio using the MCP protocol.
