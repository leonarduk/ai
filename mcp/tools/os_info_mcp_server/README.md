# OS Info MCP Server

A Model Context Protocol (MCP) server for monitoring CPU and memory usage on the local system.

## Features

Real-time system resource monitoring using `psutil`.

### Available Tools

- **get_cpu_usage** - Get current CPU usage percentage
- **get_memory_usage** - Get detailed memory usage information
- **get_system_info** - Get comprehensive system CPU and memory information

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### get_cpu_usage

Returns the current CPU usage percentage.

**Parameters:**
- `interval` (number, optional): Sampling interval in seconds (default: 1)

**Example:**
```json
{
  "interval": 2
}
```

**Response:**
```json
{
  "cpu_percentage": 15.3,
  "timestamp": 1234567890.123
}
```

### get_memory_usage

Returns detailed memory usage statistics.

**Parameters:** None

**Response:**
```json
{
  "total": 17179869184,
  "available": 8589934592,
  "used": 8589934592,
  "percent": 50.0,
  "free": 8589934592,
  "active": 6442450944,
  "inactive": 2147483648,
  "timestamp": 1234567890.123
}
```

### get_system_info

Returns comprehensive system information including CPU and memory with human-readable formatting.

**Parameters:** None

**Response:**
```json
{
  "cpu": {
    "percentage": 15.3,
    "count_logical": 8,
    "count_physical": 4
  },
  "memory": {
    "total_bytes": 17179869184,
    "available_bytes": 8589934592,
    "used_bytes": 8589934592,
    "percent": 50.0,
    "free_bytes": 8589934592
  },
  "formatted": {
    "memory_total": "16.00 GB",
    "memory_available": "8.00 GB",
    "memory_used": "8.00 GB"
  },
  "timestamp": 1234567890.123
}
```

## Configuration

No environment variables required.

## Use Cases

- **System Monitoring:** Track resource usage during development or testing
- **Performance Analysis:** Monitor resource consumption of running applications
- **Diagnostics:** Identify resource bottlenecks or memory leaks
- **Automation:** Trigger actions based on resource thresholds

## Notes

- All byte values are provided in raw format for precise calculations
- Human-readable formatted values are provided in the `formatted` section
- CPU percentage represents overall system usage across all cores
- Memory statistics include active, inactive, free, and available memory
- Timestamps are Unix epoch times (seconds since January 1, 1970)

## Platform Support

Supported on all major platforms:
- Windows
- macOS
- Linux

The `psutil` library handles platform-specific differences automatically.

## Performance

- Minimal overhead on system resources
- CPU sampling interval can be adjusted for accuracy vs speed tradeoff
- Memory queries are instantaneous (no sampling period required)
