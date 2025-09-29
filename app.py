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
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_api_key():
    """Get API key from environment or secrets."""
    try:
        # Try environment variable first
        env_key = os.getenv("OPENROUTER_API_KEY")
        if env_key:
            logger.info("✅ API key from environment")
            return env_key
        
        # Try Streamlit secrets
        if hasattr(st, 'secrets'):
            try:
                secrets_dict = dict(st.secrets)  # Convert to dict to avoid errors
                if 'OPENROUTER_API_KEY' in secrets_dict:
                    logger.info("✅ API key from Streamlit secrets")
                    return secrets_dict["OPENROUTER_API_KEY"]
            except:
                pass
        
        return None
    except:
        return None

def init_session_state():
    """Initialize session state."""
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

def main():
    init_session_state()
    
    st.markdown("# 🤖 **Intelligent AI Agent**")
    st.markdown("### ChatGPT-3.5 Turbo with Google Drive Context Integration")
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # API Key Status
        openrouter_key = get_api_key()
        if openrouter_key:
            st.success("✅ OpenRouter API Key Found")
        else:
            st.error("❌ OpenRouter API Key Missing")
            st.error("Add OPENROUTER_API_KEY to .env file or Streamlit secrets")
            return
        
        # Google Drive Authentication 
        st.markdown("### 🔐 Google Drive Authentication")
        
        if not st.session_state.drive_authenticated:
            if st.button("🔗 Connect to Google Drive", type="primary"):
                try:
                    with st.spinner("Authenticating with Google Drive..."):
                        # Import the NEW auth code
                        from utils.auth import GoogleDriveAuth
                        
                        # Create auth instance
                        drive_auth = GoogleDriveAuth()
                        
                        # Attempt authentication
                        service = drive_auth.authenticate()
                        
                        if service:
                            st.session_state.drive_authenticated = True
                            st.session_state.drive_auth = drive_auth
                            st.session_state.drive_service = service
                            st.session_state.orchestrator = None  # Reset orchestrator
                            
                            st.success("✅ Successfully connected to Google Drive!")
                            logger.info("Google Drive authentication successful")
                            st.rerun()
                        else:
                            st.error("❌ Authentication failed")
                            
                except Exception as e:
                    st.error(f"❌ Authentication error: {str(e)}")
                    logger.error(f"Authentication error: {e}")
                    
                    # Show detailed error in expander
                    with st.expander("🔍 Error Details"):
                        st.code(str(e))
        else:
            st.success("✅ Google Drive Connected")
            if st.button("🔄 Refresh Connection"):
                st.session_state.drive_authenticated = False
                st.session_state.drive_auth = None
                st.session_state.drive_service = None
                st.session_state.orchestrator = None
                st.rerun()
        
        # Model Parameters
        st.markdown("### 🎛️ Model Parameters")
        temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
        max_tokens = st.slider("Max Tokens", 100, 4000, 1000, 100)
        
        # Clear Chat
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
    
    # Initialize orchestrator
    if st.session_state.orchestrator is None and openrouter_key:
        try:
            from agent.orchestrator import IntelligentOrchestrator
            
            drive_service = st.session_state.drive_service if st.session_state.drive_authenticated else None
            
            st.session_state.orchestrator = IntelligentOrchestrator(
                drive_service=drive_service,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if drive_service:
                logger.info("Orchestrator initialized WITH Google Drive")
            else:
                logger.info("Orchestrator initialized WITHOUT Google Drive")
                
        except Exception as e:
            st.error(f"Failed to initialize orchestrator: {e}")
            return
    
    # Update parameters
    elif st.session_state.orchestrator:
        st.session_state.orchestrator.chat_agent.update_parameters(temperature, max_tokens)
    
    # Chat interface
    st.markdown("### 💬 Conversation")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # User input
    user_input = st.chat_input("Ask me anything...")
    
    if user_input and st.session_state.orchestrator:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.write(user_input)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response_data = st.session_state.orchestrator.process_query(user_input)
                    st.write(response_data["response"])
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_data["response"]
                    })
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": error_msg
                    })
        
        st.rerun()

if __name__ == "__main__":
    main()
