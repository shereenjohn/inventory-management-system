"""
Service for interacting with OpenAI LLM.
This module handles all LLM-related operations.
"""
import json
import openai
from typing import Dict, Any, List

class LLMService:
    """Service for interacting with OpenAI API."""
    
    def __init__(self, api_key: str, api_description: str):
        """
        Initialize the LLM service.
        
        Args:
            api_key: OpenAI API key
            api_description: Description of the inventory API
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.api_description = api_description
        self.system_prompt = self._create_system_prompt(api_description)
    
    def _create_system_prompt(self, api_description: str) -> str:
        """Create the system prompt for the LLM."""
        return f"""
You are a friendly inventory management assistant that processes natural language queries.

The inventory API has the following endpoints:

{api_description}

IMPORTANT RULES:

1. For queries about the current inventory (e.g., "How many shirts do we have?"), use:
   GET /inventory

2. For adding items (e.g., "I got 5 shirts", "Add 3 pants"), use:
   POST /inventory with {{"item": "tshirts", "change": positive_number}}

3. For removing items (e.g., "I sold 2 shirts"), use:
   POST /inventory with {{"item": "tshirts", "change": negative_number}}

4. IMPORTANT: ONLY ask for clarification if NO quantity is specified. If the user says "remove 4 shirts", 
   DO NOT ask "how many shirts" - the quantity is already clear.

5. For multiple operations in one query (e.g., "add 2 shirts and 3 pants"), you MUST include 
   a separate JSON object for EACH operation:
   POST /inventory with {{"item": "tshirts", "change": 2}}
   POST /inventory with {{"item": "pants", "change": 3}}

6. When responding to users:
   - Use "t-shirts" not "tshirts" when speaking to humans
   - For adding items, say "added X to the inventory"
   - For removing items, say "removed X from the inventory"
   - Always include current inventory after any operation
   - Be friendly and helpful in your tone
   - End responses with a question like "Anything else you'd like to do?" whenever it makes sense and whenever it is needed, and do not ask such kind of questions "Anything else you'd like to do?" when you say "Feel free to let me know what you'd like to do" since it is typycally asking the same question twice

7. ALWAYS include the exact API call in your response, using this format:
   - GET /inventory (for checking inventory)
   - POST /inventory with {{"item": "tshirts" or "pants", "change": number}} (for updates)

8. NEVER include technical language like "- with" or "you can do the following" in your response.
   Just provide a natural, conversational response as if you're a helpful assistant.
"""
    
    async def process_query(self, query: str, inventory_context: Dict[str, Any]) -> str:
        """
        Process a natural language query with inventory context.
        
        Args:
            query: User's natural language query
            inventory_context: Current inventory state
            
        Returns:
            LLM response
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Current inventory: {json.dumps(inventory_context)}\n\nUser query: {query}"}
        ]
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.2  # Slightly higher temperature for more natural responses
        )
        
        return response.choices[0].message.content
    
    async def get_structured_operations(self, query: str, inventory_context: Dict[str, Any]) -> str:
        """
        Get structured operations data from the LLM.
        Used as a fallback when regular parsing fails.
        
        Args:
            query: User's natural language query
            inventory_context: Current inventory state
            
        Returns:
            JSON string with operation details
        """
        structured_prompt = f"""
You are an AI assistant that extracts inventory operations from natural language.

The inventory API can:
1. GET inventory information
2. UPDATE inventory by adding or removing items

Based on the following user query, determine what operation(s) should be performed.
If multiple operations are mentioned (e.g., "add 2 shirts and remove 3 pants"), 
return an array of operations.

Return a JSON object or array with the following structure:

For GET operations:
{{"operation_type": "get"}}

For UPDATE operations:
{{"operation_type": "update", "item": "tshirts" or "pants", "change": number}}
Where "change" is positive for adding and negative for removing.

For multiple operations, return an array like:
[
  {{"operation_type": "update", "item": "tshirts", "change": 2}},
  {{"operation_type": "update", "item": "pants", "change": -3}}
]

Current inventory: {json.dumps(inventory_context)}
User query: {query}

Return ONLY the JSON object or array, nothing else.
"""
        
        messages = [
            {"role": "system", "content": structured_prompt}
        ]
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0
        )
        
        return response.choices[0].message.content