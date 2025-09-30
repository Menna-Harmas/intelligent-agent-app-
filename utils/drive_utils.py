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

# Configure logging
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
        """
        try:
            search_query_parts = []
            
            # Build search query
            if query:
                # Clean the query - remove file extensions and special characters
                clean_query = re.sub(r'\.(pdf|docx?|txt|csv)$', '', query, flags=re.IGNORECASE)
                clean_query = re.sub(r'[^\w\s-]', ' ', clean_query).strip()
                
                # Split into individual terms for more flexible matching
                terms = [term for term in clean_query.split() if len(term) > 2]
                
                if terms:
                    # Create search conditions - use OR for more flexible matching
                    name_conditions = []
                    for term in terms:
                        name_conditions.append(f"name contains '{term}'")
                    
                    if name_conditions:
                        # Use OR instead of AND for broader matching
                        search_query_parts.append(f"({' or '.join(name_conditions)})")
            
            # Filter by supported file types
            if not file_types:
                file_types = list(self.supported_types.keys())
            
            if file_types:
                type_queries = [f"mimeType='{mime_type}'" for mime_type in file_types]
                search_query_parts.append(f"({' or '.join(type_queries)})")
            
            # Exclude trashed files
            search_query_parts.append("trashed=false")
            
            # Combine query parts
            if len(search_query_parts) > 1:
                final_query = " and ".join(search_query_parts)
            else:
                # Default query - all supported files
                type_queries = [f"mimeType='{mime_type}'" for mime_type in self.supported_types.keys()]
                final_query = f"({' or '.join(type_queries)}) and trashed=false"
            
            logger.info(f"Searching Drive with query: {final_query}")
            
            # Execute search
            results = self.service.files().list(
                q=final_query,
                pageSize=limit,
                fields="files(id, name, mimeType, size, modifiedTime, createdTime, webViewLink)",
                orderBy="name"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} files")
            
            # Log all found files for debugging
            for file in files:
                logger.info(f"Found file: {file['name']} ({file['mimeType']})")
            
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
    
    def _extract_pdf_content(self, file_id: str) -> str:
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
    
    def _extract_google_doc_content(self, file_id: str) -> str:
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
    
    def _extract_text_file_content(self, file_id: str) -> str:
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
    
    def _extract_csv_content(self, file_id: str) -> str:
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
    
    def _extract_markdown_content(self, file_id: str) -> str:
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
    
    def _extract_word_content(self, file_id: str) -> str:
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
        FIXED: Better filename extraction and search logic.
        """
        try:
            logger.info(f"Getting relevant context for query: '{user_query}'")
            
            # FIXED: Better filename extraction patterns
            potential_filename = None
            query_lower = user_query.lower()
            
            # More precise patterns to extract just the filename
            file_patterns = [
                r'[\'"]([\w\s\-\.]+\.(?:pdf|docx?|txt|csv))[\'"]',  # "filename.ext" in quotes
                r'\bfile\s+[\'"]([\w\s\-\.]+)[\'"]',  # file "name" 
                r'\bdocument\s+[\'"]([\w\s\-\.]+)[\'"]',  # document "name"
                r'\b([\w\s\-]+\.(?:pdf|docx?|txt|csv))\b',  # filename.ext without quotes
                r'\b([\w\s\-]*cv[\w\s\-]*\.pdf)\b',  # cv files specifically
                r'\b([\w\s\-]*resume[\w\s\-]*\.(?:pdf|docx?))\b'  # resume files
            ]
            
            for pattern in file_patterns:
                matches = re.findall(pattern, user_query, re.IGNORECASE)
                if matches:
                    potential_filename = matches[0].strip()
                    logger.info(f"Found potential filename in query: '{potential_filename}'")
                    break
            
            # Extract keywords from query for fallback search
            keywords = self.file_processor.extract_keywords(user_query)
            
            # FIRST: Try exact/similar filename search
            relevant_files = []
            if potential_filename:
                logger.info(f"Searching for specific file: '{potential_filename}'")
                
                # Clean filename for search
                clean_filename = potential_filename.replace('.pdf', '').replace('.docx', '').replace('.txt', '')
                
                relevant_files = self.search_files(query=clean_filename, limit=max_files)
                
                # If exact search fails, try with individual words from filename
                if not relevant_files:
                    filename_words = clean_filename.split()
                    if len(filename_words) > 1:
                        logger.info(f"Trying search with filename words: {filename_words}")
                        relevant_files = self.search_files(query=' '.join(filename_words), limit=max_files)
            
            # SECOND: Try keyword-based search if no files found
            if not relevant_files and keywords:
                logger.info(f"No specific file found, trying keyword search: {keywords}")
                search_query = " ".join(keywords[:3])
                relevant_files = self.search_files(query=search_query, limit=max_files)
            
            # THIRD: Get all files as last resort
            if not relevant_files:
                logger.info("No files found with keywords, getting all supported files")
                relevant_files = self.search_files(limit=max_files)
            
            if not relevant_files:
                logger.info("No files found in Drive")
                return "", []
            
            logger.info(f"Found {len(relevant_files)} potentially relevant files")
            
            # Extract content from files
            context_parts = []
            source_files = []
            successful_extractions = 0
            
            # Sort files by relevance if we have a specific filename
            if potential_filename:
                clean_target = potential_filename.lower().replace('.pdf', '').replace('.docx', '').replace('.txt', '')
                relevant_files.sort(key=lambda x: self._calculate_filename_similarity(x['name'].lower(), clean_target), reverse=True)
            
            for file_info in relevant_files:
                logger.info(f"Processing file: '{file_info['name']}'")
                
                content = self.get_file_content(
                    file_info['id'], 
                    file_info['mimeType'],
                    file_info['name']
                )
                
                if content and len(content.strip()) > 50:  # Only use files with substantial content
                    # Truncate content to prevent token overflow
                    truncated_content = self.file_processor.truncate_content(content, max_length=1500)
                    
                    context_parts.append(
                        f"--- Content from file: {file_info['name']} ({file_info['type_name']}) ---\n"
                        f"{truncated_content}\n"
                    )
                    
                    source_files.append({
                        'id': file_info['id'],
                        'name': file_info['name'],
                        'type': file_info['type_name'],
                        'url': file_info['url'],
                        'modified': file_info.get('modified', 'Unknown'),
                        'created': file_info.get('created', 'Unknown')
                    })
                    
                    successful_extractions += 1
                    logger.info(f"Successfully processed '{file_info['name']}' - {len(content)} characters extracted")
                    
                    # If we found the target file, prioritize it and maybe stop
                    if potential_filename and self._calculate_filename_similarity(file_info['name'].lower(), potential_filename.lower()) > 0.7:
                        logger.info(f"Found high-match target file: '{file_info['name']}' - prioritizing")
                        # Move this file's content to the beginning
                        if len(context_parts) > 1:
                            context_parts.insert(0, context_parts.pop())
                            source_files.insert(0, source_files.pop())
                        break
                        
                else:
                    logger.warning(f"No usable content from '{file_info['name']}' - skipping")
                
                # Limit to prevent too much context
                if successful_extractions >= 3:
                    break
            
            # Combine all context
            combined_context = "\n".join(context_parts)
            
            logger.info(f"Context retrieval complete: {successful_extractions} files processed, {len(combined_context)} total characters")
            
            return combined_context, source_files
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {str(e)}")
            return "", []
    
    def _calculate_filename_similarity(self, filename1: str, filename2: str) -> float:
        """Calculate similarity between two filenames."""
        # Simple similarity based on common words
        words1 = set(re.findall(r'\w+', filename1.lower()))
        words2 = set(re.findall(r'\w+', filename2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
