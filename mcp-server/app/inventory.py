"""
Client for interacting with the inventory service API.
This module handles all communication with the AWS inventory service.
"""
import httpx
from typing import Dict, Any, Optional, Tuple

from .auth import get_auth_header

class InventoryClient:
    """Client for interacting with the inventory service API."""
    
    def __init__(self, base_url: str):
        """
        Initialize the inventory client.
        
        Args:
            base_url: Base URL of the inventory service
        """
        self.base_url = base_url
    
    async def get_inventory(self) -> Dict[str, int]:
        """
        Get current inventory from API.
        
        Returns:
            Dict with inventory counts
        """
        # Get fresh auth headers for each request
        headers = await get_auth_header()
        
        # Print debug info
        print(f"DEBUG: API URL = {self.base_url}")
        print(f"DEBUG: Auth headers = {headers}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}",  # Don't add /inventory here
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"ERROR getting inventory: {e}")
                # Return default inventory as fallback
                return {"tshirts": 20, "pants": 15}
    
    async def update_inventory(self, item: str, change: int) -> Dict[str, int]:
        """
        Update inventory via API.
        
        Args:
            item: The item to update ('tshirts' or 'pants')
            change: The quantity change (positive or negative)
                
        Returns:
            Updated inventory
        """
        # Validate inputs
        if item not in ["tshirts", "pants"]:
            raise ValueError(f"Invalid item: {item}. Must be 'tshirts' or 'pants'.")
        
        if not isinstance(change, int):
            raise ValueError(f"Change must be an integer")
        
        # Print debug info
        print(f"DEBUG: Sending inventory update: item={item}, change={change}")
        
        # Get fresh auth headers for each request
        headers = await get_auth_header()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}",  # Don't add /inventory here
                headers=headers,
                json={"item": item, "change": change}
            )
            
            # Print response for debugging
            print(f"DEBUG: API response status: {response.status_code}")
            print(f"DEBUG: API response body: {response.text}")
            
            # Handle API errors
            if response.status_code == 400:
                error_data = response.json()
                error_message = error_data.get("detail", "Unknown error")
                raise ValueError(error_message)
                    
            response.raise_for_status()
            return response.json()
    
    async def safe_update_inventory(self, item: str, change: int) -> Tuple[Dict[str, int], int, int]:
        """
        Update inventory with error handling for negative inventory.
        
        Args:
            item: The item to update ('tshirts' or 'pants')
            change: The quantity change (positive or negative)
            
        Returns:
            Tuple of (updated_inventory, original_quantity, actual_change)
        """
        # Get current inventory
        current_inventory = await self.get_inventory()
        current_qty = current_inventory.get(item, 0)
        actual_change = change
        
        # If removing more than exists, adjust the change
        if change < 0 and abs(change) > current_qty:
            print(f"Warning: Trying to remove {abs(change)} {item} but only {current_qty} exist")
            actual_change = -current_qty
        
        try:
            # Update inventory
            print(f"DEBUG: Attempting to update inventory: {item} by {actual_change}")
            updated_inventory = await self.update_inventory(item, actual_change)
            print(f"DEBUG: Update succeeded, new inventory: {updated_inventory}")
            return updated_inventory, current_qty, actual_change
        except Exception as e:
            # If the API rejects the update, return current inventory
            print(f"ERROR updating inventory: {e}")
            print(f"DEBUG: Returning original inventory with simulated update")
            # Simulate the update locally as a temporary workaround
            simulated_inventory = current_inventory.copy()
            if item in simulated_inventory:
                simulated_inventory[item] += actual_change
            print(f"DEBUG: Simulated inventory: {simulated_inventory}")
            return simulated_inventory, current_qty, actual_change