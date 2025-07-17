"""
Parser for OpenAPI specifications to understand the inventory API.
This module extracts endpoint information from OpenAPI specs stored in a local file.
"""
import json
import yaml
import os
from typing import Dict, Any, List, Optional

class OpenAPIParser:
    """Parser for OpenAPI specifications."""
    
    def __init__(self, spec_path: str):
        """
        Initialize the OpenAPI parser.
        
        Args:
            spec_path: Path to the OpenAPI specification file
        """
        self.spec_path = spec_path
        self.spec = None
        self.endpoints = {}
    
    async def load_spec(self) -> Dict[str, Any]:
        """
        Load the OpenAPI specification from file.
        
        Returns:
            The parsed specification
        """
        if self.spec is not None:
            return self.spec
        
        # Check if file exists
        if not os.path.exists(self.spec_path):
            raise FileNotFoundError(f"OpenAPI spec file not found: {self.spec_path}")
            
        # Read the file
        with open(self.spec_path, 'r') as f:
            content = f.read()
        
        # Parse based on file extension
        if self.spec_path.endswith('.json'):
            self.spec = json.loads(content)
        else:
            # Assume YAML for all other extensions
            self.spec = yaml.safe_load(content)
                
        await self.parse_endpoints()
        return self.spec
    
    async def parse_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """
        Parse the endpoints from the specification.
        
        Returns:
            Dictionary of endpoints with their details
        """
        if self.spec is None:
            await self.load_spec()
            
        paths = self.spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete']:
                    endpoint_id = f"{method.upper()}_{path}"
                    self.endpoints[endpoint_id] = {
                        'path': path,
                        'method': method.upper(),
                        'summary': details.get('summary', ''),
                        'parameters': details.get('parameters', []),
                        'requestBody': details.get('requestBody', {}),
                        'responses': details.get('responses', {})
                    }
                    
        return self.endpoints
    
    def get_inventory_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """
        Get inventory-related endpoints.
        
        Returns:
            Dictionary of inventory endpoints
        """
        inventory_endpoints = {}
        
        for endpoint_id, details in self.endpoints.items():
            if 'inventory' in details['path']:
                inventory_endpoints[endpoint_id] = details
                
        return inventory_endpoints
    
    def get_api_description(self) -> str:
        """
        Generate a human-readable description of the API.
        
        Returns:
            Formatted API description for LLM prompt
        """
        if not self.endpoints:
            return "API documentation not available."
            
        inventory_endpoints = self.get_inventory_endpoints()
        
        description = "Inventory API Endpoints:\n\n"
        
        for endpoint_id, details in inventory_endpoints.items():
            description += f"- {details['method']} {details['path']}\n"
            description += f"  Summary: {details['summary']}\n"
            
            # Add request body info for POST/PUT
            if details['method'] in ['POST', 'PUT'] and details.get('requestBody'):
                content = details['requestBody'].get('content', {})
                schema = next(iter(content.values()), {}).get('schema', {})
                
                if schema:
                    description += "  Request Body:\n"
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])
                    
                    for prop, prop_details in properties.items():
                        req_status = "required" if prop in required else "optional"
                        description += f"    - {prop}: {prop_details.get('type')} ({req_status}) - {prop_details.get('description', '')}\n"
            
            # Add response info
            description += "  Responses:\n"
            for status, response in details.get('responses', {}).items():
                description += f"    - {status}: {response.get('description', '')}\n"
                
            description += "\n"
            
        return description