import streamlit as st
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Intelligent AI Agent",
    page_icon="ðŸ¤–",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'drive_authenticated' not in st.session_state:
        st.session_state.drive_authenticated = False
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None
    if 'drive_auth' not in st.session_state:
        st.session_state.drive_auth = None
    if 'drive_service' not in st.session_state:
        st.session_state.drive_service = None

def display_chat_history():
    """Display chat history"""
    st.markdown("### ðŸ’¬ Conversation History")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="ðŸ¤–" if message["role"] == "assistant" else "ðŸ‘¤"):
            st.write(message["content"])
            # Show context sources if available
            if message.get("sources"):
                with st.expander("ðŸ“ Sources Used"):
                    for source in message["sources"]:
                        st.write(f"â€¢ **{source['name']}** (ID: {source['id']})")

def main():
    # Initialize session state
    init_session_state()
    
    # Header
    st.markdown("<h1 style='text-align: center; color: #1f77b4;'>ðŸ¤– Intelligent AI Agent</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>ChatGPT-3.5 Turbo with Google Drive Context Integration</p>", unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## âš™ï¸ Configuration")
        
        # API Key Status
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            st.success("âœ… OpenRouter API Key Found")
        else:
            st.error("âŒ OpenRouter API Key Missing")
            st.info("Please set OPENROUTER_API_KEY in your .env file")
            return
        
        # Google Drive Authentication
        st.markdown("### ðŸ” Google Drive Authentication")
        
        if not st.session_state.drive_authenticated:
            if st.button("ðŸ”— Connect to Google Drive", type="primary"):
                try:
                    with st.spinner("Authenticating with Google Drive..."):
                        from utils.auth import GoogleDriveAuth
                        drive_auth = GoogleDriveAuth()
                        service = drive_auth.authenticate()
                        
                        if service:
                            # Store all authentication data in session state
                            st.session_state.drive_authenticated = True
                            st.session_state.drive_auth = drive_auth
                            st.session_state.drive_service = service
                            
                            # Reset orchestrator so it gets recreated with Drive service
                            st.session_state.orchestrator = None
                            
                            st.success("âœ… Successfully connected to Google Drive!")
                            logger.info("Google Drive authentication successful - service stored in session")
                            st.rerun()
                        else:
                            st.error("âŒ Authentication failed")
                except Exception as e:
                    st.error(f"âŒ Authentication error: {str(e)}")
                    logger.error(f"Authentication error: {e}")
        else:
            st.success("âœ… Google Drive Connected")
            if st.button("ðŸ”„ Refresh Connection"):
                st.session_state.drive_authenticated = False
                st.session_state.drive_auth = None
                st.session_state.drive_service = None
                st.session_state.orchestrator = None
                st.rerun()
        
        # Model Parameters
        st.markdown("### ðŸŽ›ï¸ Model Parameters")
        temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
        max_tokens = st.slider("Max Tokens", 100, 4000, 1000, 100)
        
        # File Search Settings
        st.markdown("### ðŸ“ Drive Search Settings")
        search_limit = st.slider("Max Files to Search", 1, 20, 5, 1)
        
        # Clear Chat
        if st.button("ðŸ—‘ï¸ Clear Chat History", type="secondary"):
            st.session_state.messages = []
            st.rerun()

    # Initialize orchestrator (FIXED: Always check for Drive service)
    if st.session_state.orchestrator is None and openrouter_key:
        try:
            from agent.orchestrator import IntelligentOrchestrator
            
            # Get Drive service from session state
            drive_service = st.session_state.drive_service if st.session_state.drive_authenticated else None
            
            st.session_state.orchestrator = IntelligentOrchestrator(
                drive_service=drive_service,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if drive_service:
                logger.info("Orchestrator initialized WITH Google Drive service")
                st.sidebar.info("ðŸ”— Orchestrator connected to Google Drive")
            else:
                logger.info("Orchestrator initialized WITHOUT Google Drive service")
                st.sidebar.warning("âš ï¸ Orchestrator running without Drive access")
                
        except Exception as e:
            st.error(f"Failed to initialize orchestrator: {e}")
            logger.error(f"Orchestrator initialization error: {e}")
            return
    
    # Update orchestrator parameters if they changed
    elif st.session_state.orchestrator:
        st.session_state.orchestrator.chat_agent.update_parameters(temperature, max_tokens)
    
    # Chat interface
    display_chat_history()
    
    # User input
    user_input = st.chat_input("Ask me anything... I can search your Google Drive for context!")
    
    if user_input and st.session_state.orchestrator:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Display user message immediately
        with st.chat_message("user", avatar="ðŸ‘¤"):
            st.write(user_input)
        
        # Generate response
        with st.chat_message("assistant", avatar="ðŸ¤–"):
            with st.spinner("Thinking and searching your Drive..."):
                try:
                    response_data = st.session_state.orchestrator.process_query(
                        user_input, 
                        search_limit=search_limit
                    )
                    
                    # Display response
                    st.write(response_data["response"])
                    
                    # Add to chat history
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response_data["response"],
                        "sources": response_data.get("sources", [])
                    })
                    
                    # Show context info
                    if response_data.get("context_used"):
                        st.success(f"ðŸ“ Used context from {len(response_data['sources'])} files")
                    elif st.session_state.drive_authenticated:
                        st.info("ðŸ’­ No relevant files found - answered using general knowledge")
                    else:
                        st.warning("ðŸ“ Google Drive not connected - answered using general knowledge only")
                    
                except Exception as e:
                    error_msg = f"Sorry, I encountered an error: {str(e)}"
                    st.error(error_msg)
                    logger.error(f"Query processing error: {e}")
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": error_msg
                    })
        
        st.rerun()

if __name__ == "__main__":
    main()