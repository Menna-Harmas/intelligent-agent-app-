import streamlit as st
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    if 'drive_auth' not in st.session_state:
        st.session_state.drive_auth = None
    if 'drive_service' not in st.session_state:
        st.session_state.drive_service = None

def check_credentials():
    """Check if Google credentials are available"""
    has_local = os.path.exists("credentials.json")
    has_oauth_secrets = False
    has_service_account = False
    
    try:
        if hasattr(st, "secrets"):
            # Check for OAuth credentials (preferred for user's personal Drive)
            has_oauth_secrets = ("GOOGLE_CLIENT_ID" in st.secrets and 
                               "GOOGLE_CLIENT_SECRET" in st.secrets)
            # Check for service account (fallback)
            has_service_account = "GOOGLE_SERVICE_ACCOUNT_JSON" in st.secrets
    except Exception as e:
        logger.warning(f"Failed to check secrets: {e}")
        pass
    
    return has_local, has_oauth_secrets, has_service_account

def display_chat_history():
    """Display chat history"""
    st.markdown("### 💬 Conversation History")
    for message in st.session_state.messages:
        with st.chat_message(message["role"], 
                           avatar="🤖" if message["role"] == "assistant" else "👤"):
            st.write(message["content"])
            # Show context sources if available
            if message.get("sources"):
                with st.expander("📁 Sources Used"):
                    for source in message["sources"]:
                        st.write(f"• **{source['name']}** (ID: {source['id']})")

def main():
    # Initialize session state
    init_session_state()
    
    # Header
    st.markdown("""
    # 🤖 Intelligent AI Agent
    ### ChatGPT-3.5 Turbo with Google Drive Context Integration
    """, unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # API Key Status
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_key:
            try:
                openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
            except:
                pass
        
        if openrouter_key:
            st.success("✅ OpenRouter API Key Found")
        else:
            st.error("❌ OpenRouter API Key Missing")
            st.info("Please set OPENROUTER_API_KEY in your .env file or Streamlit secrets")
            return
        
        # Google Drive Authentication
        st.markdown("### 🔐 Google Drive Authentication")
        
        # Check credential availability
        has_local, has_oauth_secrets, has_service_account = check_credentials()
        
        # Show credential status and priority
        if has_oauth_secrets:
            st.success("✅ OAuth credentials found (Personal Drive Access)")
            st.info("🔑 Using OAuth for accessing **your personal** Google Drive")
        elif has_local:
            st.success("✅ Local OAuth credentials.json found")
        elif has_service_account:
            st.warning("⚠️ Service Account found (Limited Access)")
            st.info("📋 Service accounts can only access files **shared with them**")
        else:
            st.error("❌ Google Drive credentials not found")
            st.info("""
            **To enable Google Drive integration:**
            
            **Option 1: OAuth (Recommended - Access YOUR personal Drive)**
            1. Go to your app settings in Streamlit Cloud
            2. Navigate to "Secrets" section
            3. Add your Google OAuth credentials:
            ```
            GOOGLE_CLIENT_ID = "your_client_id.apps.googleusercontent.com"
            GOOGLE_CLIENT_SECRET = "your_client_secret"
            ```
            
            **Option 2: Local Development**
            1. Download OAuth `credentials.json` from Google Cloud Console
            2. Place it in your project root directory
            
            **Note:** Service accounts can only access files shared with them, 
            not your personal Drive files.
            """)
        
        # Authentication button logic
        if not st.session_state.drive_authenticated:
            if has_local or has_oauth_secrets or has_service_account:
                auth_method = "OAuth" if (has_local or has_oauth_secrets) else "Service Account"
                
                if st.button(f"🔗 Connect to Google Drive ({auth_method})", type="primary"):
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
                                st.success("✅ Successfully connected to Google Drive!")
                                logger.info("Google Drive authentication successful - service stored in session")
                                st.rerun()
                    except Exception as e:
                        st.error(f"❌ Authentication error: {str(e)}")
                        logger.error(f"Authentication error: {e}")
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
        
        # File Search Settings
        st.markdown("### 📁 Drive Search Settings")
        search_limit = st.slider("Max Files to Search", 1, 20, 5, 1)
        
        # Clear Chat
        if st.button("🗑️ Clear Chat History", type="secondary"):
            st.session_state.messages = []
            st.rerun()
    
    # Initialize orchestrator
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
                st.sidebar.info("🔗 Orchestrator connected to Google Drive")
            else:
                logger.info("Orchestrator initialized WITHOUT Google Drive service") 
                st.sidebar.warning("⚠️ Orchestrator running without Drive access")
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
        with st.chat_message("user", avatar="👤"):
            st.write(user_input)
        
        # Generate response
        with st.chat_message("assistant", avatar="🤖"):
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
                        st.success(f"📁 Used context from {len(response_data['sources'])} files")
                    elif st.session_state.drive_authenticated:
                        st.info("💭 No relevant files found - answered using general knowledge")
                    else:
                        st.warning("📁 Google Drive not connected - answered using general knowledge only")
                        
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
