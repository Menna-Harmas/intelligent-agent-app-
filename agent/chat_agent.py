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
            api_key=self.api_key
        )
        
        logger.info(f"ChatGPT Agent initialized with model: {self.model}")
    
    def generate_response(
        self,
        user_input: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using ChatGPT with optional context injection.
        """
        try:
            # Build messages list
            messages = []
            
            # Add system prompt
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                default_system = "You are a helpful AI assistant with access to Google Drive files. "
                default_system += "When context from files is provided, use it to give accurate, detailed answers. "
                default_system += "Always cite the specific files you reference in your response."
                messages.append({"role": "system", "content": default_system})
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)
            
            # Build user message with context
            user_message = user_input
            
            if context and context.strip():
                user_message = f"Context from Google Drive files:\n\n{context}\n\n---\n\nUser Question: {user_input}\n\nPlease answer based on the provided context from the files."
                logger.info(f"Including context of {len(context)} characters")
            
            messages.append({"role": "user", "content": user_message})
            
            # Generate response
            logger.info(f"Sending request to {self.model}...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extract response
            assistant_message = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            tokens_used = response.usage.total_tokens
            
            logger.info(f"Response generated successfully. Tokens used: {tokens_used}")
            
            return {
                "response": assistant_message,
                "model": self.model,
                "tokens_used": tokens_used,
                "finish_reason": finish_reason
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": f"I apologize, but I encountered an error while generating a response: {str(e)}",
                "model": self.model,
                "tokens_used": 0,
                "finish_reason": "error"
            }
