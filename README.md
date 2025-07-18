# Inventory Management System with NLP Interface

A natural language-powered inventory management system that lets you interact with inventory data using plain English. The system consists of two main components: an Inventory Service (AWS Lambda) and a Model Control Plane (MCP) Server that processes natural language.


---

## ✨ Key Features

- **Natural Language Interface**: Manage inventory using everyday English.
- **Multi-Operation Support**: Handle complex queries like "add 3 shirts and remove 2 pants."
- **Clarification System**: Intelligently asks for more information when needed.
- **Serverless Backend**: Scalable AWS Lambda-based inventory service.
- **In-Memory Storage**: Fast data access with singleton pattern implementation.
- **AI-Powered**: Uses OpenAI's GPT models for language understanding.
- **Error Handling**: Gracefully manages edge cases like insufficient inventory.
- **OpenAPI Integration**: Dynamic API discovery and specification.

---

## 🏗️ Project Structure

inventory-management-system/
├── inventory-service/              # Serverless inventory API
│   ├── src/inventory/app.py        # Lambda function handler
│   ├── template.yaml               # SAM template
│   ├── samconfig.toml              # SAM configuration
│   └── openapi.yaml                # API specification
│
├── mcp-server/                     # Natural language processor
│   ├── app/
│   │   ├── init.py
│   │   ├── main.py                 # FastAPI application
│   │   ├── inventory.py            # Inventory client
│   │   ├── llm_service.py          # OpenAI integration
│   │   ├── openapi_parser.py       # OpenAPI spec parser
│   │   ├── auth.py                 # Authentication handling
│   │   └── utils.py                # Utility functions
│   ├── run.py                      # Server startup
│   ├── ui.py                       # Gradio UI for demo
│   ├── requirements.txt            # Python dependencies
│   └── openapi.yaml                # Copy of API specification
│
├── openapi.yaml                    # API specification
└── README.md                       # Project documentation


---

## 📋 Requirements

- Python 3.9+
- AWS Account with configured credentials
- AWS CLI
- AWS SAM CLI
- OpenAI API Key
- FastAPI and Uvicorn
- httpx for async HTTP requests
- pydantic for data validation
- gradio (for optional UI)

---

## 📦 Installation & Setup

### Step 1: Clone the Repository

```bash
git clone [https://github.com/shereenjohn/inventory-management-system.git](https://github.com/shereenjohn/inventory-management-system.git)
cd inventory-management-system
Step 2: Deploy the Inventory Service
Bash

cd inventory-service
# Build the SAM application
sam build
# Deploy to AWS
sam deploy --guided
Follow the prompts during guided deployment:

Stack Name: inventory-service

AWS Region: Your preferred region

Confirm changes before deployment: Y

Allow SAM CLI to create IAM roles: Y

Important: Note the ApiGatewayApi URL from the deployment output. You'll need this for the MCP server.

Step 3: Set Up the MCP Server
Bash

cd ../mcp-server

# Install dependencies
pip install -r requirements.txt

# Create .env file with your configuration
# Replace with your actual API URL and OpenAI key
echo "INVENTORY_API_URL=your_api_gateway_url" > .env
echo "OPENAI_API_KEY=your_openai_api_key" >> .env

# If using authentication (optional)
echo "COGNITO_TOKEN=your_cognito_token" >> .env
echo "COGNITO_REFRESH_TOKEN=your_refresh_token" >> .env
echo "COGNITO_CLIENT_ID=your_client_id" >> .env
echo "COGNITO_USER_POOL_ID=your_user_pool_id" >> .env
echo "COGNITO_ENDPOINT=[https://cognito-idp.us-east-1.amazonaws.com/](https://cognito-idp.us-east-1.amazonaws.com/)" >> .env
echo "AWS_REGION=us-east-1" >> .env

# Start the server
python run.py
Step 4: Start the UI (Optional)
Bash

# In a separate terminal
cd mcp-server
python ui.py
Access the UI at http://localhost:7860.

🖥️ Usage Examples
Natural Language Queries
You can interact with the system using queries like:

"How many t-shirts do we have?"

"Add 5 pants to inventory"

"I sold 3 shirts yesterday"

"Add 2 shirts and remove 1 pant"

"What's our current inventory?"

"We received 10 new shirts"

"A customer bought 3 pants"

"Update inventory: +5 t-shirts, -3 pants"

API Examples
Inventory Service
Bash

# Check inventory
curl -X GET https://your-api-url

# Update inventory (add 5 t-shirts)
curl -X POST -H "Content-Type: application/json" \
  -d '{"item":"tshirts","change":5}' https://your-api-url

# Update inventory (remove 3 pants)
curl -X POST -H "Content-Type: application/json" \
  -d '{"item":"pants","change":-3}' https://your-api-url
MCP Server
Bash

# Check current inventory
curl -X POST -H "Content-Type: application/json" \
  -d '{"text":"How many shirts do we have?"}' http://localhost:8001/query

# Add items
curl -X POST -H "Content-Type: application/json" \
  -d '{"text":"Add 5 shirts to inventory"}' http://localhost:8001/query

# Multiple operations
curl -X POST -H "Content-Type: application/json" \
  -d '{"text":"Add 3 shirts and remove 2 pants"}' http://localhost:8001/query
🛠️ Technologies Used
Backend: Python 3.9+, FastAPI, AWS Lambda, AWS API Gateway, AWS SAM

Natural Language Processing: OpenAI GPT-3.5, Regular Expressions

API & Documentation: OpenAPI 3.0, YAML

Development Tools: httpx, pydantic, python-dotenv, uvicorn, gradio

🧠 Design Approach
Serverless Architecture: For scalability and cost-efficiency.

Singleton Pattern: For in-memory data storage as required by the project.

Hybrid NLP Approach: Regex for common queries and OpenAI GPT for complex phrasings.

Clarification System: Handles ambiguous queries.

OpenAPI Integration: For dynamic API discovery and specification.

Modular Design: Separation of concerns with dedicated modules.

📝 Limitations & Future Improvements
Data Persistence: Currently uses in-memory storage; could be extended with a database like DynamoDB.

Limited Items: Only tracks t-shirts and pants as specified; can be expanded.

Authentication: Basic implementation that could be enhanced for production use.

Testing: Could be expanded with comprehensive unit and integration tests.mon queries with LLM for complex ones
OpenAPI Integration: For dynamic API discovery
