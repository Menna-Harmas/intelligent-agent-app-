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
    if 'auth_error_details' not in st.session_state:
        st.session_state.auth_error_details = None

def show_auth_help():
    """Show authentication help information."""
    st.markdown("### 🆘 Authentication Help")
    
    # Check environment
    is_cloud = False
    try:
        if hasattr(st, 'secrets'):
            secrets_dict = dict(st.secrets)
            is_cloud = len(secrets_dict) > 0 or 'STREAMLIT_SHARING' in os.environ
    except:
        pass
    
    if is_cloud:
        st.markdown("""
        **For Streamlit Cloud deployment:**
        
        1. Go to your app settings in Streamlit Cloud
        2. Click on "Secrets" tab
        3. Add these secrets:
        ```
        GOOGLE_CLIENT_ID = "your-client-id-here"
        GOOGLE_CLIENT_SECRET = "your-client-secret-here"
        GOOGLE_PROJECT_ID = "your-project-id-here"
        ```
        
        **To get these values:**
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Select your project or create a new one
        3. Go to "APIs & Services" > "Credentials"
        4. Create OAuth 2.0 Client ID (Web application)
        5. Add your Streamlit Cloud URL to authorized redirect URIs
        """)
    else:
        st.markdown("""
        **For local development:**
        
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Create or select a project
        3. Go to "APIs & Services" > "Credentials"
        4. Create OAuth 2.0 Client ID
        5. Download credentials.json file
        6. Place it in your project root directory
        """)

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
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("🔗 Connect to Google Drive", type="primary"):
                    try:
                        with st.spinner("Authenticating with Google Drive..."):
                            # Import the updated auth code
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
                                st.session_state.auth_error_details = None
                                st.success("✅ Successfully connected to Google Drive!")
                                logger.info("Google Drive authentication successful")
                                st.rerun()
                            else:
                                st.error("❌ Authentication failed")
                                
                    except Exception as e:
                        error_msg = str(e)
                        st.session_state.auth_error_details = error_msg
                        st.error(f"❌ Authentication error: Google Drive authentication failed")
                        logger.error(f"Authentication error: {e}")
            
            with col2:
                if st.button("❓ Help"):
                    show_auth_help()
            
            # Show detailed error in expander if there's an error
            if st.session_state.auth_error_details:
                with st.expander("🔍 Error Details", expanded=False):
                    st.code(st.session_state.auth_error_details)
                    
                    # Show specific help based on error
                    if "Streamlit secrets not configured" in st.session_state.auth_error_details:
                        st.warning("💡 You need to configure Google OAuth credentials in Streamlit secrets")
                        show_auth_help()
                    elif "credentials.json" in st.session_state.auth_error_details:
                        st.warning("💡 Missing credentials.json file for local development")
                        show_auth_help()
        else:
            st.success("✅ Google Drive Connected")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("🔄 Refresh Connection"):
                    st.session_state.drive_authenticated = False
                    st.session_state.drive_auth = None
                    st.session_state.drive_service = None
                    st.session_state.orchestrator = None
                    st.session_state.auth_error_details = None
                    st.rerun()
            
            with col2:
                if st.button("🚪 Disconnect"):
                    if st.session_state.drive_auth:
                        st.session_state.drive_auth.logout()
                    st.session_state.drive_authenticated = False
                    st.session_state.drive_auth = None
                    st.session_state.drive_service = None
                    st.session_state.orchestrator = None
                    st.session_state.auth_error_details = None
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
