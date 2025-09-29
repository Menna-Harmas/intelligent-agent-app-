import os
import logging
from typing import Dict, List, Optional, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatGPTAgent:
    """
    Wrapper class for ChatGPT-3.5 Turbo via OpenRouter API.
    Handles context injection and structured conversation management.
    """
    
    def __init__(
        self, 
        model: str = "openai/gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        api_key: Optional[str] = None
    ):
        """
        Initialize the ChatGPT agent.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Get API key
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Please set OPENROUTER_API_KEY environment variable.")
        
        # Initialize OpenAI client with OpenRouter configuration
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "Intelligent Agent Wrapper"
            }
        )
        
        logger.info(f"ChatGPT Agent initialized with model: {self.model}")
    
    def create_system_prompt(self, context: Optional[str] = None) -> str:
        """
        Create a dynamic system prompt with optional context.
        """
        base_prompt = """You are an intelligent AI assistant with access to the user's Google Drive files.

Your main capabilities:
- Provide helpful, accurate responses using both general knowledge and specific file content
- When file content is provided, use it as the primary source for answers
- Always mention which specific files you're referencing when using their content
- Be thorough and detailed in your responses
- If no relevant files are found, clearly state this and provide general knowledge

IMPORTANT: When provided with file content below, prioritize using that information in your response."""
        
        if context and context.strip():
            context_prompt = f"""

==== CONTENT FROM USER'S GOOGLE DRIVE FILES ====
{context}
==== END OF DRIVE CONTENT ====

CRITICAL INSTRUCTION: The content above is from the user's actual Google Drive files. Use this information to provide accurate, detailed responses. Always reference the specific file names when using their content in your answer."""
            return base_prompt + context_prompt
        
        return base_prompt + "\n\nNote: No relevant file content was found in the user's Google Drive for this query. I'll provide a response based on general knowledge."
    
    def generate_response(
        self, 
        user_input: str, 
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using ChatGPT with context injection.
        """
        try:
            # Build messages list
            messages = [
                {"role": "system", "content": self.create_system_prompt(context)}
            ]
            
            # Add conversation history if provided (keep recent)
            if conversation_history:
                for msg in conversation_history[-6:]:  # Keep last 6 messages
                    if msg.get("role") in ["user", "assistant"]:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
            
            # Add current user input
            messages.append({"role": "user", "content": user_input})
            
            logger.info(f"Sending request to {self.model}")
            logger.info(f"Total messages: {len(messages)}")
            if context:
                logger.info(f"Context provided: {len(context)} characters")
            
            # Make API call with increased max_tokens for comprehensive responses
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=min(self.max_tokens, 2000),  # Allow longer responses
                stream=False
            )
            
            # Extract response
            assistant_message = response.choices[0].message.content
            
            # Prepare response data
            response_data = {
                "response": assistant_message,
                "model": self.model,
                "tokens_used": {
                    "prompt": getattr(response.usage, 'prompt_tokens', None) if hasattr(response, 'usage') else None,
                    "completion": getattr(response.usage, 'completion_tokens', None) if hasattr(response, 'usage') else None,
                    "total": getattr(response.usage, 'total_tokens', None) if hasattr(response, 'usage') else None
                },
                "context_used": context is not None and len(context.strip()) > 0,
                "finish_reason": response.choices[0].finish_reason
            }
            
            logger.info(f"Response generated successfully")
            if hasattr(response, 'usage'):
                logger.info(f"Tokens used: {response.usage.total_tokens}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise Exception(f"ChatGPT API Error: {str(e)}")
    
    def validate_connection(self) -> bool:
        """Test the connection to OpenRouter API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello, please respond with 'Connection successful!'"}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            return "Connection successful" in response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Connection validation failed: {str(e)}")
            return False
    
    def update_parameters(
        self, 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> None:
        """Update model parameters dynamically."""
        if temperature is not None:
            self.temperature = max(0.0, min(2.0, temperature))
            
        if max_tokens is not None:
            self.max_tokens = max(100, min(4000, max_tokens))
        
        logger.info(f"Parameters updated - Temperature: {self.temperature}, Max Tokens: {self.max_tokens}")
