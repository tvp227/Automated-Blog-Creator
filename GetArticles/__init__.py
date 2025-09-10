import logging
import json
import os
import hashlib
import re
import requests
from datetime import datetime
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from bs4 import BeautifulSoup
import openai

def extract_keywords_for_image_search(title, description):
    """Use AI to extract the best visual keywords for image search"""
    try:
        # Set up OpenAI client
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        
        if not openai.api_key:
            logging.warning("OpenAI API key not found, using fallback keyword extraction")
            return fallback_keyword_extraction(title, description)
        
        prompt = f"""
        Analyze this cybersecurity article title and description to find the best visual search terms for a thumbnail image:
        
        Title: "{title}"
        Description: "{description}"
        
        Rules:
        1. If a company/brand is mentioned (Apple, Microsoft, Google, etc.), return "{company} logo"
        2. If a specific product is mentioned (iPhone, Windows, etc.), return "{product} icon"
        3. If it's about a cyber attack on a specific industry, return a visual symbol of that industry
        4. For generic security topics, use visual metaphors like "security shield", "lock icon", "network protection"
        5. Avoid abstract terms like "vulnerability" or "exploit"
        6. Keep it 2-4 words maximum
        7. Make it visually searchable and professional
        
        Return only the search term, nothing else.
        """
        
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3
        )
        
        search_term = response.choices[0].message.content.strip().lower()
        
        # Clean up the response
        search_term = re.sub(r'[^\w\s]', '', search_term)
        
        return search_term if search_term else fallback_keyword_extraction(title, description)
        
    except Exception as e:
        logging.error(f"Error using AI for keyword extraction: {e}")
        return fallback_keyword_extraction(title, description)

def fallback_keyword_extraction(title, description):
    """Fallback keyword extraction when AI is not available"""
    text = f"{title} {description}".lower()
    
    # Look for company/brand names first
    companies = ['apple', 'microsoft', 'google', 'amazon', 'meta', 'facebook', 'tesla', 'netflix', 
                'adobe', 'zoom', 'slack', 'twitter', 'linkedin', 'instagram', 'tiktok', 'snapchat',
                'uber', 'airbnb', 'spotify', 'paypal', 'visa', 'mastercard', 'samsung', 'sony',
                'nintendo', 'playstation', 'xbox', 'intel', 'nvidia', 'amd', 'cisco', 'vmware',
                'oracle', 'salesforce', 'dropbox', 'github', 'aws', 'azure', 'cloudflare',
                'jaguar', 'bmw', 'mercedes', 'ford', 'toyota', 'honda', 'volkswagen', 'audi']
    
    for company in companies:
        if company in text:
            return f"{company} logo"
    
    # Check for tech products
    tech_terms = ['iphone', 'android', 'windows', 'mac', 'linux', 'chrome', 'firefox', 'safari']
    for term in tech_terms:
        if term in text:
            return f"{term} icon"
    
    # Security term mappings
    security_mappings = {
        'malware': 'virus warning icon',
        'ransomware': 'lock security icon',
        'phishing': 'email security icon',
        'data breach': 'shield protection icon',
        'cyber attack': 'security alert icon',
        'vulnerability': 'security shield icon'
    }
    
    for term, icon in security_mappings.items():
        if term in text:
            return icon
    
    return "cybersecurity shield icon"

def validate_image_url(url):
    """Check if an image URL is accessible and returns a valid image"""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('content-type', '').lower()
        
        # Check if it's an image and accessible
        if response.status_code == 200 and 'image' in content_type:
            # Avoid certain problematic domains
            blocked_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com', 
                             'tiktok.com', 'pinterest.com', 'reddit.com']
            if not any(domain in url.lower() for domain in blocked_domains):
                return True
    except:
        pass
    return False

def search_for_thumbnail_image(search_query):
    """Search for a high-quality thumbnail image using multiple methods"""
    # Try Google Custom Search first
    image_url = search_google_images(search_query)
    if image_url:
        return image_url
    
    # Fallback to Unsplash API for more reliable images
    image_url = search_unsplash_images(search_query)
    if image_url:
        return image_url
        
    # Final fallback to a curated list of default images
    return get_default_security_image(search_query)

def search_google_images(search_query):
    """Search Google Custom Search for images"""
    try:
        api_key = os.environ.get('GOOGLE_API_KEY')
        search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
        
        if not api_key or not search_engine_id:
            return None
            
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': search_query,
            'searchType': 'image',
            'imgSize': 'large',
            'imgType': 'photo',
            'safe': 'active',
            'num': 10,  # Get more results to find working URLs
            'rights': 'cc_publicdomain,cc_attribute,cc_sharealike'  # Try to get freely usable images
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'items' in data:
            # Try each image URL until we find one that works
            for item in data['items']:
                image_url = item.get('link', '')
                if image_url and validate_image_url(image_url):
                    return image_url
                    
    except Exception as e:
        logging.error(f"Google image search failed for '{search_query}': {e}")
    
    return None

def search_unsplash_images(search_query):
    """Search Unsplash for free high-quality images"""
    try:
        unsplash_key = os.environ.get('UNSPLASH_ACCESS_KEY')
        if not unsplash_key:
            return None
            
        # Clean up search query for Unsplash
        clean_query = re.sub(r'\b(icon|logo)\b', '', search_query).strip()
        if not clean_query:
            clean_query = "technology security"
            
        url = "https://api.unsplash.com/search/photos"
        headers = {"Authorization": f"Client-ID {unsplash_key}"}
        params = {
            'query': clean_query,
            'per_page': 5,
            'orientation': 'landscape',
            'content_filter': 'high'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'results' in data and data['results']:
            # Return the first result's regular sized image
            return data['results'][0]['urls']['regular']
            
    except Exception as e:
        logging.error(f"Unsplash image search failed for '{search_query}': {e}")
    
    return None

def get_default_security_image(search_query):
    """Return a curated default image based on search terms"""
    # Curated list of reliable stock image URLs for common security topics
    default_images = {
        'apple': 'https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg',
        'microsoft': 'https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg',
        'google': 'https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg',
        'security': 'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=400',
        'cybersecurity': 'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=400',
        'shield': 'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=400',
        'lock': 'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=400',
        'network': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=400',
        'data': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400',
        'technology': 'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=400'
    }
    
    query_lower = search_query.lower()
    
    # Find the best matching default image
    for term, image_url in default_images.items():
        if term in query_lower:
            return image_url
    
    # Ultimate fallback
    return 'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=400'

def extract_article_metadata(html_content, blob_name, last_modified, blob_service_account_name):
    """Extract structured metadata from HTML article content"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract title
        title_element = soup.find('title') or soup.find('h1')
        title = title_element.get_text().strip() if title_element else blob_name.replace('.html', '').replace('_', ' ').title()
        
        # Extract description from meta description or first paragraph
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc:
            description = meta_desc.get('content', '').strip()
        else:
            first_p = soup.find('p')
            if first_p:
                description = first_p.get_text().strip()[:200] + "..." if len(first_p.get_text().strip()) > 200 else first_p.get_text().strip()
        
        # Extract author
        author = ""
        author_meta = soup.find('meta', attrs={'name': 'author'}) or soup.find('meta', attrs={'property': 'article:author'})
        if author_meta:
            author = author_meta.get('content', '').strip()
        
        # Count words
        text_content = soup.get_text()
        word_count = len(re.findall(r'\b\w+\b', text_content))
        
        # Generate unique ID from content
        article_id = hashlib.md5(html_content.encode()).hexdigest()[:16]
        
        # Extract or infer source
        source = "Security Blog"
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            url = canonical.get('href', '')
            if 'zdnet.com' in url:
                source = "ZDNet Security"
            elif 'krebsonsecurity.com' in url:
                source = "Krebs on Security"
            elif 'bleepingcomputer.com' in url:
                source = "BleepingComputer"
            elif 'thehackernews.com' in url:
                source = "The Hacker News"
            elif 'darkreading.com' in url:
                source = "Dark Reading"
            elif 'securityweek.com' in url:
                source = "SecurityWeek"
            elif 'welivesecurity.com' in url:
                source = "ESET Security Blog"
        
        # Search for thumbnail image
        search_keywords = extract_keywords_for_image_search(title, description)
        thumbnail_url = search_for_thumbnail_image(search_keywords)
        
        return {
            "id": article_id,
            "title": title,
            "description": description,
            "link": f"https://{blob_service_account_name}.blob.core.windows.net/articles/{blob_name}",
            "publishDate": last_modified.strftime('%Y-%m-%dT%H:%M:%S'),
            "source": source,
            "sourceFeed": "",
            "category": "security",
            "region": "global",
            "tags": ["security", "cybersecurity"],
            "author": author,
            "wordCount": word_count,
            "thumbnailUrl": thumbnail_url,
            "imageSearchQuery": search_keywords
        }
    except Exception as e:
        logging.error(f"Error extracting metadata from {blob_name}: {e}")
        return None

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('GetArticles function called')
    
    try:
        # Get blob client
        blob_service = BlobServiceClient.from_connection_string(
            os.environ['AzureWebJobsStorage']
        )
        container_client = blob_service.get_container_client('articles')
        
        # Get articles list with enhanced metadata
        articles = []
        try:
            for blob in container_client.list_blobs():
                if blob.name.endswith('.html'):
                    try:
                        # Download blob content to extract metadata
                        blob_client = container_client.get_blob_client(blob.name)
                        html_content = blob_client.download_blob().readall().decode('utf-8')
                        
                        # Extract structured metadata
                        article_data = extract_article_metadata(html_content, blob.name, blob.last_modified, blob_service.account_name)
                        if article_data:
                            articles.append(article_data)
                    except Exception as e:
                        logging.error(f"Error processing blob {blob.name}: {e}")
                        # Fallback to basic metadata
                        fallback_title = blob.name.replace('.html', '').replace('_', ' ').title()
                        fallback_keywords = extract_keywords_for_image_search(fallback_title, "cybersecurity article")
                        fallback_thumbnail = search_for_thumbnail_image(fallback_keywords)
                        
                        articles.append({
                            "id": hashlib.md5(blob.name.encode()).hexdigest()[:16],
                            "title": fallback_title,
                            "description": "Cybersecurity article",
                            "link": f"https://{blob_service.account_name}.blob.core.windows.net/articles/{blob.name}",
                            "publishDate": blob.last_modified.strftime('%Y-%m-%dT%H:%M:%S'),
                            "source": "Security Blog",
                            "sourceFeed": "",
                            "category": "security",
                            "region": "global",
                            "tags": ["security"],
                            "author": "",
                            "wordCount": 0,
                            "thumbnailUrl": fallback_thumbnail,
                            "imageSearchQuery": fallback_keywords
                        })
        except Exception as e:
            logging.error(f"Error listing blobs: {e}")
            return func.HttpResponse("No articles found", status_code=404)
        
        # Sort by publish date (newest first)
        articles.sort(key=lambda x: x['publishDate'], reverse=True)
        
        # Calculate metrics
        total_articles = len(articles)
        threat_levels = {}
        sources = {}
        total_word_count = 0
        
        for article in articles:
            # Count threat levels
            threat_level = article.get('tags', ['unknown'])[0] if article.get('tags') else 'unknown'
            threat_levels[threat_level] = threat_levels.get(threat_level, 0) + 1
            
            # Count sources
            source = article.get('source', 'Unknown')
            sources[source] = sources.get(source, 0) + 1
            
            # Sum word counts
            total_word_count += article.get('wordCount', 0)
        
        # Get latest article date
        latest_article_date = articles[0]['publishDate'] if articles else None
        
        # Create response with metrics at top
        response_data = {
            "metrics": {
                "totalArticles": total_articles,
                "totalWordCount": total_word_count,
                "averageWordCount": round(total_word_count / total_articles) if total_articles > 0 else 0,
                "latestArticle": latest_article_date,
                "threatLevels": threat_levels,
                "sources": sources,
                "lastUpdated": datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            },
            "articles": articles
        }
        
        # Return JSON response with metrics and articles
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"GetArticles failed: {e}")
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype="application/json"
        )