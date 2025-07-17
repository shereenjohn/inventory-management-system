"""
Inventory Management Service - Simplified OOP implementation
"""
import json
from typing import Dict, Any


class InventoryManager:
    """
    Manages inventory operations using an in-memory data store.
    Implements the Singleton pattern to maintain state between Lambda invocations.
    """
    _instance = None
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(InventoryManager, cls).__new__(cls)
            cls._instance._inventory = {
                "tshirts": 20,
                "pants": 15
            }
        return cls._instance
    
    def get_inventory(self) -> Dict[str, int]:
        """Get current inventory state."""
        return self._inventory.copy()
    
    def update_inventory(self, item: str, change: int) -> Dict[str, int]:
        """
        Update inventory for a specific item.
        
        Raises:
            ValueError: If item is invalid or resulting quantity would be negative
        """
        # Validate item
        if item not in self._inventory:
            raise ValueError(f"Invalid item: {item}")
        
        # Calculate and validate new count
        new_count = self._inventory[item] + change
        if new_count < 0:
            raise ValueError(f"Cannot reduce {item} below zero")
        
        # Update inventory
        self._inventory[item] = new_count
        return self.get_inventory()
    
    def process_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an API Gateway request.
        """
        try:
            # Extract HTTP method
            http_method = event.get('httpMethod')
            
            # Handle GET requests
            if http_method == 'GET':
                return self.get_inventory()
            
            # Handle POST requests
            elif http_method == 'POST':
                # Parse and validate request body
                body = self._parse_body(event)
                item, change = self._validate_update_request(body)
                return self.update_inventory(item, change)
            
            # Direct Lambda invocation (no HTTP method)
            elif http_method is None:
                # Check if this is a direct POST with item/change
                if 'item' in event and 'change' in event:
                    try:
                        return self.update_inventory(event['item'], int(event['change']))
                    except ValueError as e:
                        return {"error": str(e)}
                # Default to GET
                return self.get_inventory()
            
            # Unknown method
            else:
                return {"error": f"Method {http_method} not allowed"}
                
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return {"error": f"Internal server error: {str(e)}"}
    
    def _parse_body(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse request body from API Gateway event."""
        body = event.get('body', '{}')
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in request body")
        return body if isinstance(body, dict) else {}
    
    def _validate_update_request(self, body: Dict[str, Any]) -> tuple:
        """Validate inventory update request and return (item, change)."""
        item = body.get('item')
        change = body.get('change')
        
        if not item:
            raise ValueError("Item is required")
        
        if change is None:
            raise ValueError("Change is required")
        
        try:
            change = int(change)
        except (ValueError, TypeError):
            raise ValueError("Change must be an integer")
        
        return item, change


# Create singleton instance
inventory_manager = InventoryManager()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler function."""
    # Log the event for debugging
    print("Event received:", json.dumps(event))
    
    # Process the request
    result = inventory_manager.process_request(event)
    
    # Format for API Gateway Proxy integration
    return {
        'statusCode': 200 if 'error' not in result else 400,
        'body': json.dumps(result),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    }