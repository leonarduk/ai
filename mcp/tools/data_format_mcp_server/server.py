#!/usr/bin/env python3
"""
MCP Server for data format operations (JSON, XML)
Provides tools for parsing and generating JSON and XML
"""

import asyncio
import json
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from pathlib import Path
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("data-format-server")

def load_env():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

load_env()

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="json_parse",
            description="Parse a JSON string into a Python object",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_string": {"type": "string", "description": "JSON string to parse"}
                },
                "required": ["json_string"]
            }
        ),
        Tool(
            name="json_generate",
            description="Generate a JSON string from a Python object",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {"type": "object", "description": "Python object to convert to JSON"},
                    "indent": {"type": "integer", "description": "Indentation level (default: 2)"}
                },
                "required": ["data"]
            }
        ),
        Tool(
            name="json_validate",
            description="Validate if a string is valid JSON",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_string": {"type": "string", "description": "JSON string to validate"}
                },
                "required": ["json_string"]
            }
        ),
        Tool(
            name="xml_parse",
            description="Parse an XML string into a structured format",
            inputSchema={
                "type": "object",
                "properties": {
                    "xml_string": {"type": "string", "description": "XML string to parse"}
                },
                "required": ["xml_string"]
            }
        ),
        Tool(
            name="xml_generate",
            description="Generate an XML string from a structured format",
            inputSchema={
                "type": "object",
                "properties": {
                    "root_tag": {"type": "string", "description": "Root element tag name"},
                    "data": {"type": "object", "description": "Data to convert to XML"},
                    "pretty": {"type": "boolean", "description": "Pretty print the XML (default: true)"}
                },
                "required": ["root_tag", "data"]
            }
        ),
        Tool(
            name="xml_validate",
            description="Validate if a string is well-formed XML",
            inputSchema={
                "type": "object",
                "properties": {
                    "xml_string": {"type": "string", "description": "XML string to validate"}
                },
                "required": ["xml_string"]
            }
        )
    ]

def dict_to_xml(parent, data):
    """Convert a dictionary to XML elements"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                for item in value:
                    child = ET.SubElement(parent, key)
                    dict_to_xml(child, item)
            elif isinstance(value, dict):
                child = ET.SubElement(parent, key)
                dict_to_xml(child, value)
            else:
                child = ET.SubElement(parent, key)
                child.text = str(value)
    else:
        parent.text = str(data)

def xml_to_dict(element):
    """Convert XML element to dictionary"""
    result = {}
    
    # Add attributes
    if element.attrib:
        result['@attributes'] = element.attrib
    
    # Add text content
    if element.text and element.text.strip():
        if len(element) == 0:  # No children
            return element.text.strip()
        result['#text'] = element.text.strip()
    
    # Add children
    for child in element:
        child_data = xml_to_dict(child)
        if child.tag in result:
            # Multiple children with same tag - make it a list
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data
    
    return result if result else None

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "json_parse":
            json_string = arguments["json_string"]
            parsed = json.loads(json_string)
            result = {
                "success": True,
                "data": parsed
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "json_generate":
            data = arguments["data"]
            indent = arguments.get("indent", 2)
            json_string = json.dumps(data, indent=indent)
            return [TextContent(type="text", text=json_string)]
        
        elif name == "json_validate":
            json_string = arguments["json_string"]
            try:
                json.loads(json_string)
                result = {
                    "valid": True,
                    "message": "JSON is valid"
                }
            except json.JSONDecodeError as e:
                result = {
                    "valid": False,
                    "message": str(e)
                }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "xml_parse":
            xml_string = arguments["xml_string"]
            root = ET.fromstring(xml_string)
            parsed = {
                "root_tag": root.tag,
                "data": xml_to_dict(root)
            }
            return [TextContent(type="text", text=json.dumps(parsed, indent=2))]
        
        elif name == "xml_generate":
            root_tag = arguments["root_tag"]
            data = arguments["data"]
            pretty = arguments.get("pretty", True)
            
            root = ET.Element(root_tag)
            dict_to_xml(root, data)
            
            xml_string = ET.tostring(root, encoding='unicode')
            
            if pretty:
                dom = minidom.parseString(xml_string)
                xml_string = dom.toprettyxml(indent="  ")
                # Remove empty lines
                xml_string = '\n'.join([line for line in xml_string.split('\n') if line.strip()])
            
            return [TextContent(type="text", text=xml_string)]
        
        elif name == "xml_validate":
            xml_string = arguments["xml_string"]
            try:
                ET.fromstring(xml_string)
                result = {
                    "valid": True,
                    "message": "XML is well-formed"
                }
            except ET.ParseError as e:
                result = {
                    "valid": False,
                    "message": str(e)
                }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
