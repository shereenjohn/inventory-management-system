"""
Authentication module for Cognito token management.
Handles token refresh and storage with full automation.
"""
import os
import json
import httpx
import time
import boto3
from typing import Optional, Dict, Any
from dotenv import load_dotenv, set_key

class CognitoAuth:
    """Manages Cognito authentication and token refresh."""
    
    def __init__(self, client_id: str, refresh_token: str, endpoint: str, 
                 region: str, username: str = None, password: str = None, 
                 env_path: str = ".env"):
        """
        Initialize the Cognito authentication manager.
        
        Args:
            client_id: Cognito app client ID
            refresh_token: Cognito refresh token
            endpoint: Cognito token endpoint
            region: AWS region
            username: Cognito username for fallback auth
            password: Cognito password for fallback auth
            env_path: Path to .env file for token persistence
        """
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.endpoint = endpoint
        self.region = region
        self.username = username
        self.password = password
        self.env_path = env_path
        self.id_token = os.getenv("COGNITO_TOKEN")
        self.last_refresh_time = time.time()
    
    async def get_valid_token(self) -> Optional[str]:
        """
        Get a valid ID token, refreshing if necessary.
        
        Returns:
            Valid ID token or None if refresh fails
        """
        # Check if token is likely expired (default Cognito expiry is 1 hour)
        current_time = time.time()
        if not self.id_token or current_time - self.last_refresh_time > 3500:  # Refresh if older than ~58 minutes
            await self.full_auth_flow()
            
        return self.id_token
    
    async def refresh_token_if_needed(self) -> bool:
        """
        Refresh the ID token using the refresh token.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        if not self.client_id or not self.refresh_token or not self.endpoint:
            print("Missing Cognito configuration. Cannot refresh token.")
            return False
            
        try:
            print("Refreshing Cognito token...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.endpoint,
                    headers={"Content-Type": "application/x-amz-json-1.1", 
                             "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"},
                    json={
                        "AuthFlow": "REFRESH_TOKEN_AUTH",
                        "ClientId": self.client_id,
                        "AuthParameters": {
                            "REFRESH_TOKEN": self.refresh_token
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    id_token = data.get("AuthenticationResult", {}).get("IdToken")
                    
                    if id_token:
                        # Update token in memory
                        self.id_token = id_token
                        self.last_refresh_time = time.time()
                        
                        # Update token in environment
                        os.environ["COGNITO_TOKEN"] = id_token
                        
                        # Also update .env file for persistence
                        set_key(self.env_path, "COGNITO_TOKEN", id_token)
                        
                        print("Cognito token refreshed successfully")
                        return True
                
                print(f"Failed to refresh token: {response.status_code}")
                if response.status_code != 200:
                    print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            return False
    
    async def get_new_tokens(self) -> bool:
        """
        Get completely new tokens using username and password.
        Use this when refresh token has expired.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.username or not self.password or not self.client_id:
            print("Missing username/password. Cannot get new tokens.")
            return False
            
        try:
            print("Getting new tokens with username/password...")
            
            # Create boto3 client
            client = boto3.client('cognito-idp', region_name=self.region)
            
            # Start authentication process
            response = client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': self.username,
                    'PASSWORD': self.password
                }
            )
            
            # Extract tokens
            auth_result = response.get('AuthenticationResult', {})
            id_token = auth_result.get('IdToken')
            refresh_token = auth_result.get('RefreshToken')
            
            if id_token and refresh_token:
                # Update tokens in memory
                self.id_token = id_token
                self.refresh_token = refresh_token
                self.last_refresh_time = time.time()
                
                # Update tokens in environment
                os.environ["COGNITO_TOKEN"] = id_token
                os.environ["COGNITO_REFRESH_TOKEN"] = refresh_token
                
                # Update tokens in .env file
                set_key(self.env_path, "COGNITO_TOKEN", id_token)
                set_key(self.env_path, "COGNITO_REFRESH_TOKEN", refresh_token)
                
                print("New tokens obtained successfully")
                return True
            
            return False
        
        except Exception as e:
            print(f"Error getting new tokens: {str(e)}")
            return False
    
    async def full_auth_flow(self) -> bool:
        """
        Complete authentication flow with fallbacks.
        1. Try to refresh token if available
        2. Fall back to username/password if provided
        
        Returns:
            True if authentication successful, False otherwise
        """
        # Try to refresh token
        if self.refresh_token:
            refresh_success = await self.refresh_token_if_needed()
            if refresh_success:
                return True
        
        # Fallback: try username/password
        if self.username and self.password:
            return await self.get_new_tokens()
            
        return False

# Global auth instance
cognito_auth = None

async def initialize_auth():
    """Initialize the global auth instance."""
    global cognito_auth
    
    # Load environment variables
    load_dotenv()
    
    client_id = os.getenv("COGNITO_CLIENT_ID")
    refresh_token = os.getenv("COGNITO_REFRESH_TOKEN")
    endpoint = os.getenv("COGNITO_ENDPOINT")
    region = os.getenv("AWS_REGION", "us-east-1")
    username = os.getenv("COGNITO_USERNAME")
    password = os.getenv("COGNITO_PASSWORD")
    
    if client_id and endpoint:
        cognito_auth = CognitoAuth(
            client_id=client_id,
            refresh_token=refresh_token,
            endpoint=endpoint,
            region=region,
            username=username,
            password=password
        )
        
        # Try to authenticate immediately
        await cognito_auth.full_auth_flow()
        
        return True
    else:
        print("Warning: Missing Cognito configuration for token refresh")
        return False

async def get_auth_header() -> Dict[str, str]:
    """Get the Authorization header with a valid token."""
    print("Getting auth header...")
    
    if cognito_auth:
        token = await cognito_auth.get_valid_token()
        if token:
            print("Got valid token from Cognito auth")
            return {"Authorization": f"Bearer {token}"}
    
    # Fall back to environment variable
    token = os.getenv("COGNITO_TOKEN")
    if token:
        print("Using token from environment")
        print(f"Token starts with: {token[:20]}...")
        return {"Authorization": f"Bearer {token}"}
    
    print("WARNING: No authorization token available")
    return {}