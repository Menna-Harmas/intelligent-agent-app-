import re
import logging
from typing import List, Optional, Dict, Any
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileProcessor:
    """
    Utility class for processing file content including text cleaning,
    keyword extraction, and content optimization for AI context.
    """
    
    def __init__(self):
        """Initialize the file processor."""
        # Comprehensive stop words
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'they', 'this', 'these', 'their',
            'there', 'than', 'them', 'his', 'her', 'she', 'or', 'but', 'if',
            'we', 'you', 'your', 'i', 'my', 'me', 'our', 'us', 'up', 'out',
            'down', 'can', 'could', 'would', 'should', 'have', 'had', 'do',
            'does', 'did', 'will', 'would', 'shall', 'should', 'may', 'might',
            'must', 'can', 'could', 'been', 'being', 'am', 'were', 'was',
            'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
            'also', 'just', 'now', 'very', 'too', 'then', 'here', 'how', 'where',
            'please', 'content', 'file', 'document', 'summarize', 'summary'
        }
        
        logger.info("File processor initialized")
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text content with enhanced cleaning.
        """
        if not text:
            return ""
        
        # Remove excessive whitespace and normalize line breaks
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Remove control characters but keep essential punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\"\'\/@\%\$\#\&\*\+\=\|\\\n]', '', text)
        
        # Clean up excessive punctuation
        text = re.sub(r'[\.]{3,}', '...', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        # Remove extra spaces
        text = re.sub(r' +', ' ', text)
        
        # Clean up line breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract key terms from text using enhanced frequency analysis.
        FIXED: Better keyword extraction for file searches.
        """
        if not text:
            return []
        
        # Convert to lowercase and extract words
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        
        # Filter out stop words and very short words
        filtered_words = [
            word for word in words 
            if word not in self.stop_words and len(word) > 2
        ]
        
        # Count word frequencies
        word_freq = Counter(filtered_words)
        
        # Get most common words
        top_words = [word for word, _ in word_freq.most_common(max_keywords * 2)]
        
        # FIXED: Add context-aware filtering for professional documents
        priority_words = []
        regular_words = []
        
        # Keywords that often appear in professional documents
        professional_keywords = {
            'experience', 'skill', 'education', 'project', 'work', 
            'university', 'degree', 'certificate', 'training', 'language',
            'software', 'programming', 'management', 'analysis', 'research',
            'development', 'design', 'engineering', 'marketing', 'sales',
            'cv', 'resume', 'harmas', 'menna', 'pdf', 'qualification',
            'internship', 'job', 'career', 'professional', 'technical'
        }
        
        # Name-like words (capitalized or common names)
        name_patterns = re.findall(r'\b([A-Z][a-z]+)\b', text)
        potential_names = [name.lower() for name in name_patterns if len(name) > 2]
        
        for word in top_words:
            if (word in professional_keywords or 
                word in potential_names or 
                len(word) > 6 or
                word.endswith('cv') or word.startswith('cv')):
                priority_words.append(word)
            else:
                regular_words.append(word)
        
        # Return priority words first, then regular words
        result = (priority_words + regular_words)[:max_keywords]
        logger.info(f"Extracted keywords: {result}")
        return result
    
    def truncate_content(self, text: str, max_length: int = 1000) -> str:
        """
        Intelligently truncate content while preserving meaning and structure.
        """
        if not text or len(text) <= max_length:
            return text
        
        # Try to preserve document structure by splitting on double line breaks first
        sections = text.split('\n\n')
        
        truncated = ""
        for section in sections:
            if len(truncated + section) <= max_length - 100:  # Leave room for ellipsis
                truncated += section + "\n\n"
            else:
                # If section is too long, try to split by sentences
                sentences = re.split(r'[.!?]+', section)
                for sentence in sentences:
                    if len(truncated + sentence) <= max_length - 50:
                        truncated += sentence + ". "
                    else:
                        break
                break
        
        # If still no content, do word-level truncation
        if not truncated.strip():
            words = text[:max_length].split()
            if len(words) > 1:
                truncated = " ".join(words[:-1])
            else:
                truncated = text[:max_length]
        
        return truncated.strip() + "..."
