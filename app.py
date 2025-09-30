import streamlit as st
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Intelligent AI Agent",
    page_icon="🤖",
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
    if 'drive_service' not in st.session_state:
        st.session_state.drive_service = None
    if 'auth_attempted' not in st.session_state:
        st.session_state.auth_attempted = False

def get_api_key():
    """Get OpenRouter API key from environment or secrets"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("OPENROUTER_API_KEY")
        except:
            pass
    return api_key

def check_credentials():
    """Check if Google credentials are available"""
    has_local = os.path.exists("credentials.json")
    has_oauth_secrets = False
    has_refresh_token = False
    
    try:
        if hasattr(st, "secrets"):
            has_oauth_secrets = (
                "GOOGLE_CLIENT_ID" in st.secrets and
                "GOOGLE_CLIENT_SECRET" in st.secrets
            )
            has_refresh_token = "GOOGLE_REFRESH_TOKEN" in st.secrets
    except Exception as e:
        logger.warning(f"Failed to check secrets: {e}")
    
    return has_local, has_oauth_secrets, has_refresh_token

def display_chat_history():
    """Display chat history"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"], 
                            avatar="🤖" if message["role"] == "assistant" else "👤"):
            st.write(message["content"])
            
            # Show context sources if available
            if message.get("sources"):
                with st.expander("📁 Sources Used"):
                    for source in message["sources"]:
                        st.write(f"• **{source['name']}** ({source.get('type', 'Unknown')})")

def main():
    # Initialize session state
    init_session_state()
    
    # Header
    st.markdown("""
    # 🤖 Intelligent AI Agent
    ### ChatGPT with Google Drive Context Integration
    """)
    
    # Check API key first
    openrouter_key = get_api_key()
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # API Key Status
        if openrouter_key:
            st.success("✅ OpenRouter API Key Found")
        else:
            st.error("❌ OpenRouter API Key Missing")
            st.info("""
            **Setup:**
            1. Get your API key from [OpenRouter](https://openrouter.ai)
            2. Add to `.env` file or Streamlit secrets:
            ```
            OPENROUTER_API_KEY = "your-key-here"
            ```
            """)
            st.stop()
        
        # Google Drive Authentication
        st.markdown("### 🔐 Google Drive")
        
        has_local, has_oauth_secrets, has_refresh_token = check_credentials()
        
        # Show credential status
        if has_refresh_token:
            st.success("✅ Refresh token configured")
        elif has_oauth_secrets:
            st.info("⚠️ OAuth credentials found - authentication required")
        elif has_local:
            st.success("✅ Local credentials found")
        else:
            st.warning("⚠️ No Google Drive credentials")
            st.info("""
            **Setup Options:**
            
            **Streamlit Cloud:**
            Add to secrets:
            ```
            GOOGLE_CLIENT_ID = "your_id"
            GOOGLE_CLIENT_SECRET = "your_secret"
            ```
            
            **Local:**
            Place `credentials.json` in project root
            """)
        
        # Authentication logic
        if not st.session_state.drive_authenticated:
            if has_local or has_oauth_secrets or has_refresh_token:
                if st.button("🔗 Connect Google Drive", type="primary", key="connect_drive"):
                    st.session_state.auth_attempted = True
                    st.rerun()
                
                # Handle authentication
                if st.session_state.auth_attempted:
                    with st.spinner("Authenticating..."):
                        try:
                            from utils.auth import GoogleDriveAuth
                            drive_auth = GoogleDriveAuth()
                            service = drive_auth.authenticate()
                            
                            if service:
                                st.session_state.drive_authenticated = True
                                st.session_state.drive_service = service
                                st.session_state.orchestrator = None
                                st.session_state.auth_attempted = False
                                st.success("✅ Connected to Google Drive!")
                                logger.info("Google Drive authentication successful")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Authentication error: {str(e)}")
                            logger.error(f"Authentication error: {e}")
                            st.session_state.auth_attempted = False
        else:
            st.success("✅ Google Drive Connected")
            if st.button("🔄 Disconnect", key="disconnect_drive"):
                st.session_state.drive_authenticated = False
                st.session_state.drive_service = None
                st.session_state.orchestrator = None
                st.session_state.auth_attempted = False
                st.rerun()
        
        # Model Parameters
        st.markdown("### 🎛️ Model Parameters")
        temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
        max_tokens = st.slider("Max Tokens", 100, 4000, 1500, 100)
        
        # Drive Search Settings
        st.markdown("### 📁 Search Settings")
        search_limit = st.slider("Max Files to Search", 1, 10, 5, 1)
        
        # Clear Chat
        if st.button("🗑️ Clear Chat", type="secondary"):
            st.session_state.messages = []
            if st.session_state.orchestrator:
                st.session_state.orchestrator.conversation_history = []
            st.rerun()
    
    # Initialize orchestrator if needed
    if st.session_state.orchestrator is None:
        try:
            from agent.orchestrator import IntelligentOrchestrator
            
            drive_service = (st.session_state.drive_service 
                           if st.session_state.drive_authenticated else None)
            
            st.session_state.orchestrator = IntelligentOrchestrator(
                drive_service=drive_service,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if drive_service:
                logger.info("✅ Orchestrator initialized WITH Google Drive")
            else:
                logger.info("⚠️ Orchestrator initialized WITHOUT Google Drive")
                
        except Exception as e:
            st.error(f"Failed to initialize: {e}")
            logger.error(f"Initialization error: {e}")
            st.stop()
    
    # Update orchestrator parameters
    elif st.session_state.orchestrator:
        st.session_state.orchestrator.chat_agent.update_parameters(temperature, max_tokens)
    
    # Chat interface
    st.markdown("### 💬 Chat")
    display_chat_history()
    
    # User input
    user_input = st.chat_input("Ask me anything... I can search your Google Drive!")
    
    if user_input and st.session_state.orchestrator:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.write(user_input)
        
        # Generate response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking..."):
                try:
                    response_data = st.session_state.orchestrator.process_query(
                        user_input,
                        search_limit=search_limit
                    )
                    
                    # Display response
                    st.write(response_data["response"])
                    
                    # Add to history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_data["response"],
                        "sources": response_data.get("sources", [])
                    })
                    
                    # Show context info
                    if response_data.get("context_used"):
                        st.success(f"📁 Used {len(response_data['sources'])} file(s)")
                    elif st.session_state.drive_authenticated:
                        st.info("💭 No relevant files found")
                    else:
                        st.info("💡 Google Drive not connected")
                        
                except Exception as e:
                    error_msg = f"Sorry, I encountered an error: {str(e)}"
                    st.error(error_msg)
                    logger.error(f"Query error: {e}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
        
        st.rerun()

if __name__ == "__main__":
    main()
