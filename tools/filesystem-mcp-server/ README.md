
# Filesystem MCP Server

This project provides an MCP (Model Context Protocol) server that allows safe interaction with the local filesystem. It supports reading, writing, editing, and managing files and directories within **allowed directories only**.

---

## Features

- **Safe Path Validation**: Restricts operations to `ALLOWED_DIRS` for security.
- **Tools Available**:
  - `read_file` – Read the contents of a file.
  - `write_file` – Write content to a file (create or overwrite).
  - `edit_file` – Add, delete, or replace specific lines in a file.
  - `list_directory` – List files and directories in a given path.
  - `create_directory` – Create a new directory.
  - `search_files` – Search for files by name pattern.
  - `get_file_info` – Retrieve metadata about a file or directory.

---

## Project Structure
