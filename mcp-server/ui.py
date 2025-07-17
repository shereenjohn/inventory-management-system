import gradio as gr
import requests
import json

# MCP Server URL
MCP_API_URL = "http://localhost:8001/query"

# Function to call the MCP server
def query_mcp_server(message, history):
    # Call the MCP server
    response = requests.post(
        MCP_API_URL, 
        json={"text": message}
    )
    
    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        return data["output"]
    else:
        return f"Error: Failed to get response from server. Status code: {response.status_code}"

# Create Gradio interface
demo = gr.ChatInterface(
    fn=query_mcp_server,
    title="Inventory Management Assistant",
    description="Ask questions or make changes to inventory using natural language.",
    examples=[
        "How many t-shirts do we have?",
        "I sold 3 t-shirts",
        "Add 5 pants to inventory",
        "What's my current stock?",
        "Remove all shirts"
    ],
    theme="soft"
)

# Launch the interface
if __name__ == "__main__":
    demo.launch()