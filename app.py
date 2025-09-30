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
# Helper: Google Drive Auth
# ----------------------------

def get_drive_service():
    """Authenticate using service account from Streamlit secrets."""
    try:
        # Load JSON from secret
        service_account_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        return build('drive', 'v3', credentials=creds)
    except KeyError:
        st.error("❌ Missing 'GOOGLE_SERVICE_ACCOUNT_JSON' in Streamlit Secrets.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Google Drive auth failed: {str(e)}")
        st.stop()

# ----------------------------
# File Reading Helpers
# ----------------------------

def search_files(service, query):
    """Search Drive files by name (basic keyword)."""
    try:
        results = service.files().list(
            q=f"name contains '{query}' and trashed=false",
            fields="files(id, name, mimeType)",
            pageSize=10
        ).execute()
        return results.get('files', [])
    except Exception as e:
        st.warning(f"⚠️ Search failed: {e}")
        return []

def read_file_content(service, file_id, mime_type, name):
    """Extract text from file based on type."""
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)

        if mime_type == 'text/plain':
            return fh.read().decode('utf-8')
        elif mime_type == 'application/vnd.google-apps.document':
            exported = service.files().export_media(fileId=file_id, mimeType='text/plain')
            export_fh = io.BytesIO()
            export_downloader = MediaIoBaseDownload(export_fh, exported)
            done = False
            while not done:
                _, done = export_downloader.next_chunk()
            export_fh.seek(0)
            return export_fh.read().decode('utf-8')
        elif mime_type == 'application/pdf':
            reader = PdfReader(fh)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif mime_type in ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            df = pd.read_csv(fh) if mime_type == 'text/csv' else pd.read_excel(fh)
            return df.to_string(index=False)
        else:
            return f"[Unsupported: {mime_type}]"
    except Exception as e:
        return f"[Error reading {name}: {str(e)}]"

# ----------------------------
# LLM via OpenRouter
# ----------------------------

def ask_llm(prompt):
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
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
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"LLM Error: {str(e)}"

# ----------------------------
# Streamlit UI
# ----------------------------

st.set_page_config(page_title="Intelligent Agent", page_icon="🧠")
st.title("🧠 Intelligent Agent with Google Drive")

query = st.text_input("Ask a question (agent will search your Google Drive):")

if query:
    with st.spinner("🔍 Authenticating & searching Drive..."):
        drive = get_drive_service()
        keywords = " ".join(query.split()[:3])
        files = search_files(drive, keywords)

    if files:
        st.success(f"📚 Found {len(files)} file(s)")
        context = ""
        for f in files[:3]:
            with st.spinner(f"📥 Reading {f['name']}..."):
                text = read_file_content(drive, f['id'], f['mimeType'], f['name'])
                context += f"\n\n--- {f['name']} ---\n{text[:2000]}"

        prompt = f"""
Use ONLY the following context to answer the question.
If the answer isn't in the context, say: "I don't have enough information."

Context:
{context}

Question: {query}
Answer:
        """.strip()

        with st.spinner("💬 Thinking..."):
            answer = ask_llm(prompt)

        st.subheader("🤖 Answer")
        st.write(answer)
    else:
        st.warning("No files found. Did you share a folder with the service account?")
        st.code("streamlit-drive-access@intelligent-agent-473521.iam.gserviceaccount.com")