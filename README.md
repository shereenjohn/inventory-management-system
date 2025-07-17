\# Inventory Management System with Natural Language Interface



This project consists of two main components:

1\. \*\*Inventory Service\*\*: A serverless REST API for managing inventory

2\. \*\*MCP Server\*\*: A natural language interface that converts text to API calls



\## Project Structure



\- `inventory-service/`: AWS SAM implementation of the inventory service

\- `mcp-server/`: FastAPI server with OpenAI integration for natural language processing

\- `openapi.yaml`: API specification for the inventory service



\## Setup Instructions



\### Inventory Service (AWS)



1\. Install AWS SAM CLI: \[Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)

2\. Configure AWS credentials: `aws configure`

3\. Deploy the service:

cd inventory-service

sam build

sam deploy --guided

4\. Note the API URL from the output



\### MCP Server



1\. Install dependencies:

cd mcp-server

pip install -r requirements.txt

2\. Configure environment variables in `.env`:

INVENTORY\_API\_URL=your\_api\_url

OPENAI\_API\_KEY=your\_openai\_api\_key

COGNITO\_TOKEN=your\_cognito\_token     # If using authentication

COGNITO\_REFRESH\_TOKEN=your\_refresh\_token

COGNITO\_CLIENT\_ID=your\_client\_id

COGNITO\_USER\_POOL\_ID=your\_user\_pool\_id

COGNITO\_ENDPOINT=https://cognito-idp.us-east-1.amazonaws.com/

AWS\_REGION=us-east-1

3\. Start the server:

python run.py

4\. Start the UI:

python ui.py

5\. Access the UI at http://localhost:7860



\## API Examples



\### Inventory Service



Get current inventory:

```bash

curl -X GET https://your-api-url

Update inventory:

bashcurl -X POST -H "Content-Type: application/json" -d '{"item":"tshirts","change":-3}' https://your-api-url

MCP Server

The MCP server accepts natural language inputs like:



"How many t-shirts do we have?"

"I sold 3 shirts"

"Add 5 pants to inventory"



Design Decisions

Inventory Service



Serverless Architecture: Chosen for scalability and cost-efficiency

Infrastructure as Code: AWS SAM for reproducible deployments

OOP Design: Singleton pattern for stateful Lambda

RESTful API: Simple, standard interface



MCP Server



OpenAI Integration: Provides natural language understanding

OpenAPI Specification: Used to understand API capabilities

Modular Design: Separate components for inventory client, LLM service, etc.

Conversational UI: Gradio interface for easy interaction



