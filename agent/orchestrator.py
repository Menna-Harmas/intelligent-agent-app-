import logging
from typing import Dict, List, Optional, Any
from agent.chat_agent import ChatGPTAgent
from utils.drive_utils import GoogleDriveUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligentOrchestrator:
    """
    Main orchestrator that coordinates between ChatGPT agent and Google Drive
    to provide contextually enhanced responses.
    """
    
    def __init__(
        self,
        drive_service=None,
        model: str = "openai/gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """
        Initialize the orchestrator.
        
        Args:
            drive_service: Authenticated Google Drive service (optional)
            model: ChatGPT model to use
            temperature: Response randomness
            max_tokens: Maximum response tokens
        """
        # Initialize ChatGPT agent
        self.chat_agent = ChatGPTAgent(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Initialize Drive utils if service provided
        self.drive_utils = None
        if drive_service:
            try:
                # Test the service before using it
                drive_service.files().list(pageSize=1).execute()
                self.drive_utils = GoogleDriveUtils(drive_service)
                logger.info("✅ Orchestrator initialized WITH Google Drive integration")
            except Exception as e:
                logger.error(f"❌ Drive service test failed: {e}")
                logger.info("🔧 Orchestrator initialized WITHOUT Google Drive integration")
        else:
            logger.info("🔧 Orchestrator initialized WITHOUT Google Drive integration (no service provided)")
        
        self.conversation_history = []
    
    def process_query(
        self,
        user_input: str,
        search_limit: int = 5,
        use_conversation_history: bool = True
    ) -> Dict[str, Any]:
        """
        Process user query with intelligent context retrieval and response generation.
        """
        try:
            logger.info(f"🔍 Processing query: {user_input[:100]}...")
            
            # Check if Drive integration is available
            context_text = ""
            source_files = []
            search_attempted = False
            
            if self.drive_utils:
                logger.info("📁 Google Drive integration available - searching for relevant context...")
                search_attempted = True
                
                try:
                    context_text, source_files = self.drive_utils.get_relevant_context(
                        user_input,
                        max_files=search_limit
                    )
                    
                    if context_text and context_text.strip():
                        logger.info(f"✅ Found relevant context from {len(source_files)} files ({len(context_text)} chars)")
                    else:
                        logger.info("ℹ️ No relevant context found in Drive files")
                        
                except Exception as e:
                    logger.error(f"❌ Error during Drive search: {e}")
                    # Continue without context rather than failing completely
                    context_text = ""
                    source_files = []
            else:
                logger.info("⚠️ No Google Drive integration available")
            
            # Get conversation history if requested
            history = self.conversation_history[-10:] if use_conversation_history else []
            
            # Generate response using ChatGPT
            logger.info("🤖 Generating response with ChatGPT...")
            response_data = self.chat_agent.generate_response(
                user_input=user_input,
                context=context_text if context_text and context_text.strip() else None,
                conversation_history=history
            )
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({
                "role": "assistant",
                "content": response_data["response"]
            })
            
            # Keep conversation history manageable (last 20 messages)
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
            
            # Prepare final response with detailed metadata
            final_response = {
                "response": response_data["response"],
                "context_used": bool(context_text and context_text.strip()),
                "sources": source_files,
                "model_info": {
                    "model": response_data["model"],
                    "tokens_used": response_data["tokens_used"],
                    "finish_reason": response_data["finish_reason"]
                },
                "search_performed": search_attempted,
                "drive_available": self.drive_utils is not None
            }
            
            logger.info("✅ Query processing completed successfully")
            return final_response
            
        except Exception as e:
            logger.error(f"💥 Critical error processing query: {str(e)}")
            return {
                "response": f"I apologize, but I encountered an error while processing your request: {str(e)}",
                "context_used": False,
                "sources": [],
                "model_info": {},
                "search_performed": False,
                "drive_available": False,
                "error": str(e)
            }
