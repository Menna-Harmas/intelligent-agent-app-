import streamlit as st
import json
import requests
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pandas as pd
from PyPDF2 import PdfReader

# ----------------------------
# Configuration
# ----------------------------
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
MODEL = "openai/gpt-4o"  # or "openai/gpt-3.5-turbo"

# ----------------------------
# Helper Functions
# ----------------------------

def get_drive_service():
    """Create Google Drive service using Streamlit secrets."""
    try:
        service_account_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Failed to authenticate with Google Drive: {e}")
        st.stop()

def search_files(service, query):
    """Search for files in Drive by name (basic)."""
    results = service.files().list(
        q=f"name contains '{query}' and trashed=false",
        fields="files(id, name, mimeType)",
        pageSize=10
    ).execute()
    return results.get('files', [])

def read_file_content(service, file_id, mime_type, file_name):
    """Download and extract text from file based on MIME type."""
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.seek(0)

        if mime_type == 'text/plain':
            return fh.read().decode('utf-8')
        elif mime_type == 'application/vnd.google-apps.document':
            # Export Google Docs as plain text
            exported = service.files().export_media(fileId=file_id, mimeType='text/plain')
            export_fh = io.BytesIO()
            export_downloader = MediaIoBaseDownload(export_fh, exported)
            done = False
            while not done:
                status, done = export_downloader.next_chunk()
            export_fh.seek(0)
            return export_fh.read().decode('utf-8')
        elif mime_type == 'application/pdf':
            pdf_reader = PdfReader(fh)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return text
        elif mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv']:
            df = pd.read_csv(fh) if mime_type == 'text/csv' else pd.read_excel(fh)
            return df.to_string(index=False)
        else:
            return f"[Unsupported file type: {mime_type}]"
    except Exception as e:
        return f"[Error reading file {file_name}: {str(e)}]"

def query_openrouter(prompt):
    """Send prompt to OpenRouter."""
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error calling OpenRouter: {str(e)}"

# ----------------------------
# Streamlit App
# ----------------------------

st.set_page_config(page_title="Intelligent Agent", page_icon="🧠")
st.title("🧠 Intelligent Agent with Google Drive & ChatGPT")

# Input
user_query = st.text_input("Ask a question (the agent will search your Drive for relevant info):")

if user_query:
    with st.spinner("🔍 Searching Google Drive..."):
        drive_service = get_drive_service()
        # Simple: use keywords from query to search
        keywords = user_query.split()[:3]  # first 3 words
        found_files = []
        for kw in keywords:
            found_files.extend(search_files(drive_service, kw))
        # Deduplicate
        seen = set()
        unique_files = []
        for f in found_files:
            if f['id'] not in seen:
                unique_files.append(f)
                seen.add(f['id'])

    if unique_files:
        st.success(f"📚 Found {len(unique_files)} relevant file(s)")
        context = ""
        for file in unique_files[:3]:  # limit to 3 files
            with st.spinner(f"📥 Reading {file['name']}..."):
                content = read_file_content(drive_service, file['id'], file['mimeType'], file['name'])
                context += f"\n\n--- FILE: {file['name']} ---\n{content[:2000]}..."  # truncate

        # Build final prompt
        full_prompt = f"""
You are an intelligent assistant. Use the following context from Google Drive to answer the user's question.
If the context doesn't contain the answer, say so.

Context:
{context}

User Question: {user_query}
Answer:
        """.strip()

        with st.spinner("💬 Generating answer with AI..."):
            answer = query_openrouter(full_prompt)

        st.subheader("🤖 Answer")
        st.write(answer)

        with st.expander("📄 View Retrieved Context"):
            st.text(context)
    else:
        st.warning("No relevant files found in your Drive. Try different keywords.")