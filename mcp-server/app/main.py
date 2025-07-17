"""
MCP Server - Model Control Plane for Inventory Management

This server acts as a natural language interface to the inventory service,
converting user queries into appropriate API calls.
"""

import os
import re
import json
from typing import Dict, Any, List, Tuple, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from .inventory import InventoryClient
from .llm_service import LLMService
from .openapi_parser import OpenAPIParser
from .auth import initialize_auth

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INVENTORY_API_URL = os.getenv("INVENTORY_API_URL")
OPENAPI_SPEC_PATH = os.getenv("OPENAPI_SPEC_PATH", "openapi.yaml")

# Validate required environment variables
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not INVENTORY_API_URL:
    raise ValueError("INVENTORY_API_URL environment variable is required")

# Models
class Query(BaseModel):
    """Natural language query from the user"""
    text: str
    conversation_id: Optional[str] = None

class QueryResponse(BaseModel):
    """Response to the user's query"""
    original_query: str
    output: str
    inventory: Dict[str, Any]
    conversation_id: Optional[str] = None

class Operation(BaseModel):
    """Represents an inventory operation"""
    operation_type: str  # "get" or "update" or "unknown_item"
    item: Optional[str] = None  # "tshirts" or "pants" or None for "get"
    change: Optional[int] = None  # Amount to change inventory by

# Initialize FastAPI
app = FastAPI(
    title="MCP Server",
    description="Natural language interface for inventory management",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAPI parser with local file path
openapi_parser = OpenAPIParser(spec_path=OPENAPI_SPEC_PATH)

# Initialize inventory client
inventory_client = InventoryClient(base_url=INVENTORY_API_URL)

# Create LLM service (will be initialized in startup event)
llm_service = None

# Simple conversation memory
conversation_states = {}

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global llm_service
    
    # Initialize auth
    auth_initialized = await initialize_auth()
    if auth_initialized:
        print("Auth module initialized successfully")
    
    # Load OpenAPI spec
    try:
        await openapi_parser.load_spec()
        print(f"OpenAPI spec loaded from: {OPENAPI_SPEC_PATH}")
    except Exception as e:
        print(f"Warning: Could not load OpenAPI spec: {e}")
        print("Using default API description")
    
    # Get API description
    api_description = openapi_parser.get_api_description()
    
    # Initialize LLM service with API description
    llm_service = LLMService(
        api_key=OPENAI_API_KEY,
        api_description=api_description
    )
    
    print("MCP Server initialized successfully!")
    print(f"Using API at: {INVENTORY_API_URL}")

def clean_response(response: str) -> str:
    """Remove technical details from LLM response."""
    # Remove API calls and JSON
    response = re.sub(r'```json\s*\{[^}]*\}\s*```', '', response)
    response = re.sub(r'```.*?```', '', response, flags=re.DOTALL)
    response = re.sub(r'GET /inventory', '', response)
    response = re.sub(r'POST /inventory', '', response)
    response = re.sub(r'{\s*"[^"]+"\s*:\s*[^}]+}', '', response)
    
    # Remove other technical artifacts
    response = re.sub(r'Operation: .*', '', response)
    response = re.sub(r'Action: .*', '', response)
    response = re.sub(r'- with.*?[\.\n]', '', response)
    response = re.sub(r'To [^\.]+, you can do the following:', '', response)
    
    # Clean up bullet points that might be left behind
    response = re.sub(r'^\s*-\s*', '', response, flags=re.MULTILINE)
    
    # Clean up whitespace
    response = re.sub(r'\n\s*\n', '\n\n', response)
    response = re.sub(r'\s{2,}', ' ', response)
    
    return response.strip()

def extract_operations_from_llm_response(llm_response: str) -> List[Operation]:
    """
    Extract operations from the LLM's structured response.
    
    The LLM should return a JSON structure with operation details,
    which we extract and convert to Operation objects.
    """
    operations = []
    
    # Check for GET operation
    if "GET /inventory" in llm_response:
        operations.append(Operation(operation_type="get"))
    
    # Check for POST operations
    json_pattern = r'{\s*"item":\s*"([^"]+)",\s*"change":\s*(-?\d+)\s*}'
    matches = re.findall(json_pattern, llm_response)
    
    for match in matches:
        item, change_str = match
        if item in ["tshirts", "pants"]:
            operations.append(Operation(
                operation_type="update",
                item=item,
                change=int(change_str)
            ))
    
    return operations

def needs_quantity_clarification(query: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if the query needs quantity clarification.
    
    Returns:
        Tuple of (needs_clarification, item_type, action)
    """
    query_lower = query.lower()
    
    # Check for queries that specify an action and item but no quantity
    patterns = [
        # Add operations without quantity
        (r'(?:add|buy|receive|get)\s+(?:some|more|new|the|a|an)*\s*(?:t-?shirts?|shirts?|tees?)(?!\s+\d+)', "tshirts", "add"),
        (r'(?:add|buy|receive|get)\s+(?:some|more|new|the|a|an)*\s*(?:pants?|trousers?)(?!\s+\d+)', "pants", "add"),
        
        # Remove operations without quantity
        (r'(?:remove|sell|sold|ship|delete)\s+(?:some|the|a|an)*\s*(?:t-?shirts?|shirts?|tees?)(?!\s+\d+)', "tshirts", "remove"),
        (r'(?:remove|sell|sold|ship|delete)\s+(?:some|the|a|an)*\s*(?:pants?|trousers?)(?!\s+\d+)', "pants", "remove"),
    ]
    
    for pattern, item, action in patterns:
        if re.search(pattern, query_lower):
            # Make sure there's no number in the query that might be the quantity
            if not re.search(r'\d+', query_lower):
                return True, item, action
    
    return False, None, None

def extract_operations_from_query(query: str) -> List[Operation]:
    """
    Extract operations directly from the user query without LLM.
    Used for simple, clear operations to avoid unnecessary clarification.
    """
    operations = []
    query_lower = query.lower()
    
    # Track processed operations to avoid duplicates
    processed_operations = set()
    
    # Check for inventory check operations
    if re.search(r'how many|what.*inventory|stock|do we have|current|tell me|show me|levels|count', query_lower):
        if not re.search(r'add|remove|sell|sold|buy|bought|ship|receive|update|\+|-', query_lower):
            operations.append(Operation(operation_type="get"))
            return operations
    
    # Check for unsupported items first
    unknown_items = re.findall(r'\b(\d+)\s*(?:\w+\s+)*(?:shoes|socks|hats|caps|jackets|sweaters|hoodies)\b', query_lower)
    if unknown_items and len(unknown_items) > 0:
        # Return a special operation for unknown items
        operations.append(Operation(operation_type="unknown_item"))
        return operations
    
    # Handle compound operations with commas or "and"
    segments = re.split(r'\s+and\s+|,\s*', query_lower)
    
    for segment in segments:
        # Skip empty segments
        if not segment.strip():
            continue
            
        # Look for t-shirt operations with quantities - MORE FLEXIBLE PATTERNS
        shirt_patterns = [
            # Add operations (with + symbol)
            (r'(?:add|\+)\s*(\d+)(?:\s+\w+)*\s*(?:t-?shirts?|shirts?|tees?)', "tshirts", 1),
            # Add operations (without + symbol)
            (r'(?:add|buy|bought|receive|received|get|got)\s+(\d+)(?:\s+\w+)*\s*(?:t-?shirts?|shirts?|tees?)', "tshirts", 1),
            # Remove operations (with - symbol)
            (r'(?:remove|-)\s*(\d+)(?:\s+\w+)*\s*(?:t-?shirts?|shirts?|tees?)', "tshirts", -1),
            # Remove operations (without - symbol)
            (r'(?:remove|sell|sold|ship|shipped)\s+(\d+)(?:\s+\w+)*\s*(?:t-?shirts?|shirts?|tees?)', "tshirts", -1),
        ]
        
        # Look for pants operations with quantities - MORE FLEXIBLE PATTERNS
        pants_patterns = [
            # Add operations (with + symbol)
            (r'(?:add|\+)\s*(\d+)(?:\s+\w+)*\s*(?:pants?|trousers?)', "pants", 1),
            # Add operations (without + symbol)
            (r'(?:add|buy|bought|receive|received|get|got)\s+(\d+)(?:\s+\w+)*\s*(?:pants?|trousers?)', "pants", 1),
            # Remove operations (with - symbol)
            (r'(?:remove|-)\s*(\d+)(?:\s+\w+)*\s*(?:pants?|trousers?)', "pants", -1),
            # Remove operations (without - symbol)
            (r'(?:remove|sell|sold|ship|shipped)\s+(\d+)(?:\s+\w+)*\s*(?:pants?|trousers?)', "pants", -1),
        ]
        
        # Process all patterns
        patterns_found = False
        for patterns in [shirt_patterns, pants_patterns]:
            for pattern, item, multiplier in patterns:
                matches = re.finditer(pattern, segment)
                for match in matches:
                    try:
                        quantity = int(match.group(1))
                        
                        # Create a unique key for this operation
                        op_key = f"{item}_{quantity * multiplier}"
                        
                        # Only add if we haven't processed this exact operation yet
                        if op_key not in processed_operations:
                            operations.append(Operation(
                                operation_type="update",
                                item=item,
                                change=quantity * multiplier
                            ))
                            processed_operations.add(op_key)
                            patterns_found = True
                    except (ValueError, IndexError):
                        pass
        
        # Only check symbol pattern if no other patterns matched
        if not patterns_found:
            # Additional pattern for +/- notation with item name
            symbol_pattern = r'([+-])(\d+)(?:\s+\w+)*\s*(?:t-?shirts?|shirts?|tees?|pants?|trousers?)'
            matches = re.finditer(symbol_pattern, segment)
            for match in matches:
                try:
                    symbol = match.group(1)
                    quantity = int(match.group(2))
                    multiplier = 1 if symbol == '+' else -1
                    item = "tshirts" if any(word in segment for word in ["shirt", "tshirt", "t-shirt", "tee"]) else "pants"
                    
                    # Create a unique key for this operation
                    op_key = f"{item}_{quantity * multiplier}"
                    
                    # Only add if we haven't processed this exact operation yet
                    if op_key not in processed_operations:
                        operations.append(Operation(
                            operation_type="update",
                            item=item,
                            change=quantity * multiplier
                        ))
                        processed_operations.add(op_key)
                except (ValueError, IndexError):
                    pass
    
    # Add a GET operation if we found update operations
    if operations and all(op.operation_type == "update" for op in operations):
        operations.append(Operation(operation_type="get"))
    
    return operations

def is_asking_clarification(response: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if the response is asking for clarification about an item.
    
    Returns:
        Tuple of (is_asking, item_type, action)
    """
    clarification_patterns = [
        (r'how many (t-?shirts?|shirts?|tees?) (?:did you |would you like to )?(sell|add|remove|buy)', "tshirts"),
        (r'how many (pants?|trousers?) (?:did you |would you like to )?(sell|add|remove|buy)', "pants"),
        (r'specify (?:the )?(?:number|quantity) of (t-?shirts?|shirts?|tees?)', "tshirts"),
        (r'specify (?:the )?(?:number|quantity) of (pants?|trousers?)', "pants"),
        (r'how many (t-?shirts?|shirts?|tees?) would you like', "tshirts"),
        (r'how many (pants?|trousers?) would you like', "pants"),
    ]
    
    response_lower = response.lower()
    
    for pattern, item in clarification_patterns:
        match = re.search(pattern, response_lower)
        if match:
            action = "add"
            if len(match.groups()) > 1 and match.group(2) in ["sell", "remove"]:
                action = "remove"
            elif "remove" in response_lower or "sell" in response_lower:
                action = "remove"
            
            return True, item, action
    
    # More generic patterns
    if re.search(r'how many (items|pieces|units)', response_lower):
        # Try to determine item from context
        if "shirt" in response_lower or "tshirt" in response_lower or "t-shirt" in response_lower:
            action = "add" if "add" in response_lower else "remove"
            return True, "tshirts", action
        elif "pant" in response_lower or "trouser" in response_lower:
            action = "add" if "add" in response_lower else "remove"
            return True, "pants", action
        
    return False, None, None

def handle_clarification_response(query: str, conversation_state: Dict[str, Any]) -> Optional[Operation]:
    """
    Handle a response to a clarification question.
    
    Returns:
        Operation if a valid clarification response, None otherwise
    """
    if not conversation_state.get("awaiting_clarification"):
        return None
    
    # Try to extract a number from the query
    number_match = re.search(r'\b(\d+)\b', query)
    if not number_match:
        return None
    
    quantity = int(number_match.group(1))
    item = conversation_state.get("item")
    action = conversation_state.get("action")
    
    if not item or not action:
        return None
    
    # Convert action to change value
    change = quantity if action == "add" else -quantity
    
    return Operation(
        operation_type="update",
        item=item,
        change=change
    )

@app.post("/query", response_model=QueryResponse)
async def process_query(query: Query):
    """
    Process a natural language query about inventory.
    
    Args:
        query: The natural language query
        
    Returns:
        Processed result with explanation and inventory data
    """
    try:
        # Get conversation state if it exists
        conversation_id = query.conversation_id or "default"
        conversation_state = conversation_states.get(conversation_id, {})
        
        # Get current inventory for context
        current_inventory = await inventory_client.get_inventory()
        print(f"Starting inventory: {current_inventory}")
        
        # Check if query needs quantity clarification
        needs_clarification, clarification_item, clarification_action = needs_quantity_clarification(query.text)
        if needs_clarification and clarification_item and clarification_action:
            print(f"Query needs quantity clarification for {clarification_item}, action {clarification_action}")
            
            # Update conversation state
            conversation_states[conversation_id] = {
                "awaiting_clarification": True,
                "item": clarification_item,
                "action": clarification_action,
                "last_query": query.text
            }
            
            # Generate clarification message
            item_display = "t-shirts" if clarification_item == "tshirts" else "pants"
            action_display = "add" if clarification_action == "add" else "remove"
            
            user_message = f"I see you want to {action_display} some {item_display}. How many {item_display} would you like to {action_display}?"
            user_message += f" Current inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
            
            return QueryResponse(
                original_query=query.text,
                output=user_message,
                inventory=current_inventory,
                conversation_id=conversation_id
            )
        
        # Check if this is a response to a clarification question
        clarification_operation = None
        if conversation_state.get("awaiting_clarification"):
            clarification_operation = handle_clarification_response(query.text, conversation_state)
            
            if clarification_operation:
                print(f"Handling clarification response: {clarification_operation}")
                
                if clarification_operation.operation_type == "update":
                    # Update inventory based on clarification
                    current_inventory, _, _ = await inventory_client.safe_update_inventory(
                        clarification_operation.item, clarification_operation.change
                    )
                    
                    # Generate a confirmation message
                    item_display = "t-shirts" if clarification_operation.item == "tshirts" else "pants"
                    if clarification_operation.change > 0:
                        action_display = "added"
                        preposition = "to"
                    else:
                        action_display = "removed"
                        preposition = "from"
                    
                    user_message = f"Got it! I've {action_display} {abs(clarification_operation.change)} {item_display} {preposition} the inventory."
                    user_message += f" Current inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
                    user_message += "\nIs there anything else you'd like me to help with?"
                    
                    # Reset conversation state
                    conversation_states[conversation_id] = {}
                    
                    return QueryResponse(
                        original_query=query.text,
                        output=user_message,
                        inventory=current_inventory,
                        conversation_id=conversation_id
                    )
        
        # First, try to extract operations directly from the query
        direct_operations = extract_operations_from_query(query.text)
        if direct_operations:
            print(f"Extracted operations directly from query: {direct_operations}")
            
            # Check for unknown item operations
            if any(op.operation_type == "unknown_item" for op in direct_operations):
                user_message = "I'm sorry, but I can only track t-shirts and pants in the inventory. "
                user_message += f"Current inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
                user_message += "\nIs there anything else you'd like me to help with?"
                
                return QueryResponse(
                    original_query=query.text,
                    output=user_message,
                    inventory=current_inventory,
                    conversation_id=conversation_id
                )
            
            # Process all direct operations
            for operation in direct_operations:
                if operation.operation_type == "get":
                    # Refresh inventory data
                    current_inventory = await inventory_client.get_inventory()
                elif operation.operation_type == "update" and operation.item and operation.change is not None:
                    # Update inventory
                    print(f"Updating inventory: {operation.item} by {operation.change}")
                    current_inventory, _, _ = await inventory_client.safe_update_inventory(
                        operation.item, operation.change
                    )
            
            # Filter to just get update operations
            update_operations = [op for op in direct_operations if op.operation_type == "update"]
            
            if not update_operations:
                # Only GET operations
                user_message = f"The current inventory is: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
            elif len(update_operations) == 1:
                # Single update operation
                operation = update_operations[0]
                item_display = "t-shirts" if operation.item == "tshirts" else "pants"
                
                if operation.change > 0:
                    action_display = "added"
                    preposition = "to"
                else:
                    action_display = "removed"
                    preposition = "from"
                    
                user_message = f"Got it! I've {action_display} {abs(operation.change)} {item_display} {preposition} the inventory."
                user_message += f" Current inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
            else:
                # Multiple update operations
                operation_messages = []
                
                for operation in update_operations:
                    item_display = "t-shirts" if operation.item == "tshirts" else "pants"
                    
                    if operation.change > 0:
                        action_display = "added"
                        preposition = "to"
                    else:
                        action_display = "removed"
                        preposition = "from"
                        
                    operation_messages.append(f"I've {action_display} {abs(operation.change)} {item_display} {preposition} the inventory")
                
                user_message = "Got it! " + " and ".join(operation_messages) + "."
                user_message += f" Current inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
            
            user_message += "\nIs there anything else you'd like me to help with?"
            
            return QueryResponse(
                original_query=query.text,
                output=user_message,
                inventory=current_inventory,
                conversation_id=conversation_id
            )
        
        # If no direct operations, process with LLM
        llm_response = await llm_service.process_query(query.text, current_inventory)
        print(f"LLM response: {llm_response}")
        
        # Extract operations from LLM response
        operations = extract_operations_from_llm_response(llm_response)
        print(f"Extracted operations from LLM: {operations}")
        
        # If no operations were found but we should have operations, try structured output
        if not operations and any(word in query.text.lower() for word in ["add", "sell", "sold", "remove", "bought"]):
            print("Attempting to get structured output from LLM")
            structured_response = await llm_service.get_structured_operations(query.text, current_inventory)
            print(f"Structured response: {structured_response}")
            
            try:
                # Parse JSON response
                parsed = json.loads(structured_response)
                
                # Handle both single operation and multiple operations
                if isinstance(parsed, dict):
                    # Single operation
                    if parsed.get("operation_type") == "get":
                        operations.append(Operation(operation_type="get"))
                    elif parsed.get("operation_type") == "update":
                        item = parsed.get("item")
                        change = parsed.get("change")
                        if item in ["tshirts", "pants"] and isinstance(change, int):
                            operations.append(Operation(
                                operation_type="update",
                                item=item,
                                change=change
                            ))
                elif isinstance(parsed, list):
                    # Multiple operations
                    for op in parsed:
                        if op.get("operation_type") == "get":
                            operations.append(Operation(operation_type="get"))
                        elif op.get("operation_type") == "update":
                            item = op.get("item")
                            change = op.get("change")
                            if item in ["tshirts", "pants"] and isinstance(change, int):
                                operations.append(Operation(
                                    operation_type="update",
                                    item=item,
                                    change=change
                                ))
            except Exception as e:
                print(f"Error parsing structured response: {e}")
        
        # Process operations
        for operation in operations:
            if operation.operation_type == "get":
                # Refresh inventory data
                current_inventory = await inventory_client.get_inventory()
            elif operation.operation_type == "update" and operation.item and operation.change is not None:
                # Update inventory
                print(f"Updating inventory: {operation.item} by {operation.change}")
                current_inventory, _, _ = await inventory_client.safe_update_inventory(
                    operation.item, operation.change
                )
        
        # Clean the response for display
        user_message = clean_response(llm_response)
        
        # Check if the LLM is asking for clarification
        is_asking, item, action = is_asking_clarification(user_message)
        if is_asking and item:
            print(f"Detected clarification request for {item}, action {action}")
            
            # Update conversation state
            conversation_states[conversation_id] = {
                "awaiting_clarification": True,
                "item": item,
                "action": action,
                "last_query": query.text
            }
        else:
            # Reset conversation state
            conversation_states[conversation_id] = {}
        
        # Ensure the response includes current inventory
        if "Current inventory:" not in user_message:
            user_message += f"\nCurrent inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}"
        else:
            # Replace inventory counts with current values
            user_message = re.sub(
                r'Current inventory:.*?(?=\n|$)', 
                f"Current inventory: T-shirts: {current_inventory.get('tshirts', 0)}, Pants: {current_inventory.get('pants', 0)}", 
                user_message
            )
        
        # Add conversational follow-up if missing
        if not any(phrase in user_message.lower() for phrase in 
                  ["anything else", "help you with", "can i do", "would you like"]):
            user_message += "\nIs there anything else you'd like me to help with?"
        
        return QueryResponse(
            original_query=query.text,
            output=user_message,
            inventory=current_inventory,
            conversation_id=conversation_id
        )
        
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001)