"""
Utility functions for the MCP server.
Contains helper functions for text processing and parsing.
"""
import re
from typing import Optional, Tuple, List

def clean_response(response: str) -> str:
    """Clean the LLM response for display to the user."""
    # Remove API endpoint references
    cleaned = re.sub(r'GET /inventory', "", response)
    cleaned = re.sub(r'POST /inventory', "", cleaned)
    
    # Remove JSON patterns
    cleaned = re.sub(r'{\s*"item":\s*"[^"]+",\s*"change":\s*[^}]+}', "", cleaned)
    
    # Remove code blocks
    cleaned = re.sub(r'```[^`]*```', "", cleaned)
    
    # Remove instruction patterns
    cleaned = re.sub(r'For inventory checks, you can use[^.]*\.', "", cleaned)
    cleaned = re.sub(r'For updates, you can use[^.]*\.', "", cleaned)
    cleaned = re.sub(r'To check the current inventory of all items, you can use[^.]*\.', "", cleaned)
    
    # Clean up whitespace
    cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    return cleaned.strip()

def identify_item_from_query(query: str) -> Optional[str]:
    """
    Identify which inventory item is mentioned in the query.
    
    Args:
        query: User's query
        
    Returns:
        Item identifier ('tshirts', 'pants') or None if ambiguous
    """
    query_lower = query.lower()
    
    # Check for t-shirts
    if any(word in query_lower for word in ["shirt", "tshirt", "t-shirt", "tee"]):
        return "tshirts"
    
    # Check for pants
    if any(word in query_lower for word in ["pant", "trouser", "slack"]):
        return "pants"
    
    # No clear item identified
    return None

def extract_operation_params(llm_response: str, query: str) -> List[Tuple[str, int]]:
    """
    Extract operation parameters from LLM response.
    
    Args:
        llm_response: Raw LLM response
        query: Original user query
        
    Returns:
        List of (item, change) tuples
    """
    operations = []
    json_pattern = r'{\s*"item":\s*"([^"]+)",\s*"change":\s*(-?\d+)\s*}'
    matches = re.findall(json_pattern, llm_response)
    
    for match in matches:
        item, change_str = match
        if item in ["tshirts", "pants"]:
            operations.append((item, int(change_str)))
    
    return operations

def detect_operation_type(query: str) -> str:
    """
    Detect the type of inventory operation from the query text.
    
    Args:
        query: User's query
        
    Returns:
        Operation type: "check", "add", "remove", "remove_all", or "unknown"
    """
    query_lower = query.lower()
    
    # Check for inventory check operations
    if any(phrase in query_lower for phrase in [
        "how many", "current", "inventory", "stock", "do we have", 
        "count", "what's in", "what is in"
    ]):
        return "check"
    
    # Check for add operations
    if any(phrase in query_lower for phrase in [
        "add", "got", "received", "purchased", "bought", "new", 
        "more", "increase", "added"
    ]):
        return "add"
    
    # Check for remove operations
    if any(phrase in query_lower for phrase in [
        "remove", "sold", "shipped", "decreased", "took", "gave", 
        "delivered", "less", "reduce", "removed"
    ]):
        return "remove"
    
    # Check for remove all operations
    if any(phrase in query_lower for phrase in [
        "remove all", "delete all", "clear", "empty", "zero out",
        "get rid of all", "eliminate all"
    ]):
        return "remove_all"
    
    # Default to check if we can't determine
    return "unknown"