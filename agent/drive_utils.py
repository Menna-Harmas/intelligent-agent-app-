import os
import io
import logging
from typing import Dict, List, Optional, Any, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2
import docx
import pandas as pd
import markdown
import re
from utils.file_processing import FileProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveUtils:
    """
    Utility class for Google Drive operations including file search,
    content extraction, and intelligent context retrieval.
    """
    
    def __init__(self, drive_service):
        """
        Initialize with authenticated Google Drive service.
        Args:
            drive_service: Authenticated Google Drive API service object
        """
        self.service = drive_service
        self.file_processor = FileProcessor()
        
        # Supported file types and their MIME types
        self.supported_types = {
            'application/vnd.google-apps.document': 'Google Docs',
            'text/plain': 'Text File',
            'text/csv': 'CSV File',
            'application/pdf': 'PDF File',
            'text/markdown': 'Markdown File',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word Document'
        }
        
        logger.info("Google Drive Utils initialized")
    
    def search_files(
        self,
        query: Optional[str] = None,
        file_types: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for files in Google Drive with optional filtering.
        FIXED: Better filename matching for exact and partial queries.
        """
        try:
            search_query_parts = []
            
            # Build search query
            if query:
                # Clean the query - remove file extensions
                clean_query = re.sub(r'\.(pdf|docx?|txt|csv)$', '', query, flags=re.IGNORECASE)
                clean_query = clean_query.strip()
                
                logger.info(f"Original query: '{query}', Cleaned: '{clean_query}'")
                
                # Extract meaningful terms (more than 2 characters)
                terms = [term for term in re.findall(r'\w+', clean_query) if len(term) > 2]
                
                if terms:
                    # FIXED: Use OR logic for broader matching
                    name_conditions = []
                    for term in terms:
                        name_conditions.append(f"name contains '{term}'")
                    
                    if name_conditions:
                        # Use OR to match any term in filename
                        search_query_parts.append(f"({' or '.join(name_conditions)})")
                        logger.info(f"Search terms: {terms}")
            
            # Filter by supported file types
            if not file_types:
                file_types = list(self.supported_types.keys())
            
            if file_types:
                type_queries = [f"mimeType='{mime_type}'" for mime_type in file_types]
                search_query_parts.append(f"({' or '.join(type_queries)})")
            
            # Exclude trashed files
            search_query_parts.append("trashed=false")
            
            # Combine query parts
            final_query = " and ".join(search_query_parts)
            
            logger.info(f"Final Drive query: {final_query}")
            
            # Execute search
            results = self.service.files().list(
                q=final_query,
                pageSize=limit,
                fields="files(id, name, mimeType, size, modifiedTime, createdTime, webViewLink)",
                orderBy="modifiedTime desc"  # Most recent first
            ).execute()
            
            files = results.get('files', [])
            
            logger.info(f"Found {len(files)} files matching criteria")
            
            # Log all found files for debugging
            for file in files:
                logger.info(f"  - {file['name']} ({file['mimeType']})")
            
            # Enrich file data
            enriched_files = []
            for file_info in files:
                enriched_file = {
                    'id': file_info['id'],
                    'name': file_info['name'],
                    'mimeType': file_info['mimeType'],
                    'type_name': self.supported_types.get(file_info['mimeType'], 'Unknown'),
                    'size': file_info.get('size', 'Unknown'),
                    'modified': file_info.get('modifiedTime', 'Unknown'),
                    'created': file_info.get('createdTime', 'Unknown'),
                    'url': file_info.get('webViewLink', '')
                }
                enriched_files.append(enriched_file)
            
            return enriched_files
            
        except HttpError as e:
            logger.error(f"Drive API error during search: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during search: {str(e)}")
            return []
    
    def get_file_content(self, file_id: str, mime_type: str, file_name: str = "") -> Optional[str]:
        """
        Extract text content from a Google Drive file.
        """
        try:
            logger.info(f"Extracting content from file '{file_name}' (ID: {file_id}, type: {mime_type})")
            
            content = None
            
            if mime_type == 'application/vnd.google-apps.document':
                content = self._extract_google_doc_content(file_id)
            elif mime_type == 'text/plain':
                content = self._extract_text_file_content(file_id)
            elif mime_type == 'text/csv':
                content = self._extract_csv_content(file_id)
            elif mime_type == 'application/pdf':
                content = self._extract_pdf_content(file_id)
            elif mime_type == 'text/markdown':
                content = self._extract_markdown_content(file_id)
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                content = self._extract_word_content(file_id)
            else:
                logger.warning(f"Unsupported file type: {mime_type}")
                return None
            
            if content:
                logger.info(f"Successfully extracted {len(content)} characters from '{file_name}'")
                return content
            else:
                logger.warning(f"No content extracted from '{file_name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting content from '{file_name}' ({file_id}): {str(e)}")
            return None
    
    def _extract_pdf_content(self, file_id: str) -> Optional[str]:
        """Extract text content from PDF files with enhanced error handling."""
        try:
            logger.info(f"Starting PDF extraction for file_id: {file_id}")
            
            # Download PDF content
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"PDF download progress: {int(status.progress() * 100)}%")
            
            file_content.seek(0)
            
            # Try to read PDF with PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(file_content)
                text_content = ""
                
                logger.info(f"PDF has {len(pdf_reader.pages)} pages")
                
                for page_num in range(len(pdf_reader.pages)):
                    try:
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text()
                        
                        if page_text and page_text.strip():
                            text_content += f"\n--- Page {page_num + 1} ---\n"
                            text_content += page_text + "\n"
                            logger.info(f"Extracted {len(page_text)} characters from page {page_num + 1}")
                        else:
                            logger.warning(f"No text found on page {page_num + 1}")
                    
                    except Exception as page_error:
                        logger.error(f"Error extracting page {page_num + 1}: {str(page_error)}")
                        continue
                
                if text_content.strip():
                    cleaned_content = self.file_processor.clean_text(text_content)
                    logger.info(f"PDF extraction successful. Total content length: {len(cleaned_content)}")
                    return cleaned_content
                else:
                    logger.error("No text content extracted from PDF")
                    return None
                    
            except Exception as pdf_error:
                logger.error(f"PyPDF2 extraction failed: {str(pdf_error)}")
                return None
                
        except Exception as e:
            logger.error(f"Critical error in PDF extraction: {str(e)}")
            return None
    
    def _extract_google_doc_content(self, file_id: str) -> Optional[str]:
        """Extract content from Google Docs."""
        try:
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType='text/plain'
            )
            
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            content = file_content.getvalue().decode('utf-8', errors='ignore')
            return self.file_processor.clean_text(content)
            
        except Exception as e:
            logger.error(f"Error extracting Google Doc content: {str(e)}")
            return None
    
    def _extract_text_file_content(self, file_id: str) -> Optional[str]:
        """Extract content from text files."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            content = file_content.getvalue().decode('utf-8', errors='ignore')
            return self.file_processor.clean_text(content)
            
        except Exception as e:
            logger.error(f"Error extracting text file content: {str(e)}")
            return None
    
    def _extract_csv_content(self, file_id: str) -> Optional[str]:
        """Extract and summarize CSV content."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            df = pd.read_csv(file_content)
            
            summary = f"CSV Data Summary:\n"
            summary += f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
            summary += f"Column Names: {', '.join(df.columns.tolist())}\n\n"
            
            if len(df) > 0:
                summary += "Sample Data (first 5 rows):\n"
                summary += df.head().to_string(index=False)
                
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    summary += f"\n\nNumeric Column Statistics:\n"
                    summary += df[numeric_cols].describe().to_string()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error extracting CSV content: {str(e)}")
            return None
    
    def _extract_markdown_content(self, file_id: str) -> Optional[str]:
        """Extract content from Markdown files."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            content = file_content.getvalue().decode('utf-8', errors='ignore')
            
            # Convert markdown to plain text for better context
            html = markdown.markdown(content)
            # Simple HTML to text conversion
            text = re.sub('<[^<]+?>', '', html)
            return self.file_processor.clean_text(text)
            
        except Exception as e:
            logger.error(f"Error extracting Markdown content: {str(e)}")
            return None
    
    def _extract_word_content(self, file_id: str) -> Optional[str]:
        """Extract content from Word documents."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            doc = docx.Document(file_content)
            
            text_content = ""
            for paragraph in doc.paragraphs:
                text_content += paragraph.text + "\n"
            
            return self.file_processor.clean_text(text_content)
            
        except Exception as e:
            logger.error(f"Error extracting Word content: {str(e)}")
            return None
    
    def get_relevant_context(
        self,
        user_query: str,
        max_files: int = 10
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Search for and extract relevant context from Google Drive files.
        FIXED: Better filename extraction and ranking.
        """
        try:
            logger.info(f"Getting relevant context for query: '{user_query}'")
            
            # Extract potential filename from query
            filename_match = re.search(r'["\']([^"\']+\.(?:pdf|docx?|txt|csv))["\']', user_query, re.IGNORECASE)
            if filename_match:
                filename = filename_match.group(1)
                logger.info(f"Extracted exact filename from query: '{filename}'")
                search_query = filename
            else:
                # Use full query for search
                search_query = user_query
            
            # Search for files
            files = self.search_files(query=search_query, limit=max_files)
            
            if not files:
                logger.warning(f"No files found for query: '{user_query}'")
                return "", []
            
            # FIXED: Rank files by relevance to query
            def calculate_relevance(file_info):
                """Calculate relevance score based on filename similarity"""
                filename = file_info['name'].lower()
                query_terms = set(re.findall(r'\w+', user_query.lower()))
                file_terms = set(re.findall(r'\w+', filename))
                
                # Count matching terms
                matches = len(query_terms.intersection(file_terms))
                
                # Bonus for PDF files when query mentions PDF
                if 'pdf' in user_query.lower() and filename.endswith('.pdf'):
                    matches += 2
                
                # Bonus for exact or near-exact filename match
                clean_query = re.sub(r'[^a-z0-9]+', '', user_query.lower())
                clean_filename = re.sub(r'[^a-z0-9]+', '', filename)
                
                if clean_query in clean_filename or clean_filename in clean_query:
                    matches += 5
                
                return matches
            
            # Sort files by relevance
            files.sort(key=calculate_relevance, reverse=True)
            
            # Extract content from top files
            context_parts = []
            source_files = []
            successful_extractions = 0
            
            for file_info in files[:max_files]:
                logger.info(f"Processing file: {file_info['name']} (relevance: {calculate_relevance(file_info)})")
                
                content = self.get_file_content(
                    file_info['id'],
                    file_info['mimeType'],
                    file_info['name']
                )
                
                if content and len(content.strip()) > 50:
                    # Add file header
                    file_header = f"\n{'='*60}\nFile: {file_info['name']}\nType: {file_info['type_name']}\n{'='*60}\n"
                    context_parts.append(file_header + content)
                    
                    source_files.append({
                        'id': file_info['id'],
                        'name': file_info['name'],
                        'type': file_info['type_name']
                    })
                    
                    successful_extractions += 1
                    logger.info(f"✅ Successfully extracted content from '{file_info['name']}'")
                else:
                    logger.warning(f"⚠️ No usable content from '{file_info['name']}'")
                
                # Limit context to prevent overload
                if successful_extractions >= 3:
                    break
            
            # Combine all context
            combined_context = "\n".join(context_parts)
            
            logger.info(f"Context retrieval complete: {successful_extractions} files processed, {len(combined_context)} total characters")
            
            return combined_context, source_files
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {str(e)}")
            return "", []
