import logging
import azure.functions as func
import feedparser
import requests
import os
from datetime import datetime
from openai import OpenAI
from bs4 import BeautifulSoup
from azure.storage.blob import BlobServiceClient
import time
import re
import hashlib

def extract_keywords_for_image_search(title, description, openai_client):
    """Use enhanced AI to extract highly relevant visual keywords for image search"""
    try:
        if not openai_client:
            return fallback_keyword_extraction(title, description)
        
        prompt = f"""
        You are an expert at finding the MOST VISUALLY RELEVANT search terms for cybersecurity article thumbnails. 
        
        Article Title: "{title}"
        Article Content: "{description}"
        
        PRIORITY ORDER for image search terms:
        1. SPECIFIC BRANDS/COMPANIES: If mentioned, use exact brand name (e.g., "Jaguar", "Land Rover", "Apple iPhone", "Microsoft Windows")
        2. SPECIFIC PRODUCTS: Exact product names (e.g., "Tesla Model 3", "Chrome browser", "Android phone")
        3. VISUAL INDUSTRY SYMBOLS: For sectors (e.g., "automotive industry", "banking sector", "healthcare technology")
        4. RECOGNIZABLE LOGOS: Well-known company or product logos
        5. LAST RESORT: Generic security imagery
        
        EXAMPLES of good transformations:
        - "Jaguar Land Rover hack" → "Jaguar Land Rover logo"
        - "Tesla vulnerability" → "Tesla logo"
        - "iPhone malware" → "Apple iPhone"
        - "Banking trojan" → "banking security"
        - "Hospital ransomware" → "healthcare technology"
        - "Boeing systems breach" → "Boeing logo"
        
        AVOID generic terms like: "cybersecurity", "hacker", "security shield" unless no specific entity is mentioned.
        
        CRITICAL: Look for ANY brand, company, product, or industry mentioned. Even if it's just context (like "automotive sector"), use that for the image.
        
        Return ONLY the most visually relevant search term (2-5 words max):
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4",  # Use GPT-4 for better analysis
            messages=[{"role": "user", "content": prompt}],
            max_tokens=25,
            temperature=0.2  # Lower temperature for more focused results
        )
        
        search_term = response.choices[0].message.content.strip().lower()
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
        
        if response.status_code == 200 and 'image' in content_type:
            blocked_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com', 
                             'tiktok.com', 'pinterest.com', 'reddit.com']
            if not any(domain in url.lower() for domain in blocked_domains):
                return True
    except:
        pass
    return False

def search_for_thumbnail_image(search_query):
    """Enhanced multi-layered image search with quality scoring"""
    logging.info(f'🔍 Searching for image with query: "{search_query}"')
    
    # Try multiple refined searches in priority order
    search_variants = generate_search_variants(search_query)
    
    for i, variant in enumerate(search_variants):
        logging.info(f'🔍 Trying search variant {i+1}: "{variant}"')
        
        # Try Google Images first (highest quality potential)
        image_url = search_google_images_enhanced(variant)
        if image_url:
            logging.info(f'✅ Found Google image: {image_url}')
            return image_url
        
        # Try Unsplash with the variant
        image_url = search_unsplash_images(variant)
        if image_url:
            logging.info(f'✅ Found Unsplash image: {image_url}')
            return image_url
    
    # Fallback to default with original query
    logging.info(f'⚠️ Using default image for: {search_query}')
    return get_default_security_image(search_query)

def generate_search_variants(original_query):
    """Generate multiple search variants for better image matching"""
    variants = [original_query]  # Always try original first
    
    # Add logo variant for brands
    if any(term in original_query for term in ['apple', 'microsoft', 'google', 'tesla', 'jaguar', 'ford', 'bmw', 'mercedes']):
        if 'logo' not in original_query:
            variants.append(f"{original_query} logo")
        variants.append(f"{original_query} brand")
    
    # Add specific variants for automotive
    if any(term in original_query for term in ['jaguar', 'land rover', 'tesla', 'ford', 'bmw', 'mercedes', 'toyota', 'honda']):
        variants.extend([
            f"{original_query} car",
            f"{original_query} automotive",
            f"{original_query.replace('land rover', 'landrover')} logo"
        ])
    
    # Add tech variants
    if any(term in original_query for term in ['iphone', 'android', 'windows', 'chrome', 'firefox']):
        variants.extend([
            f"{original_query} device",
            f"{original_query} technology"
        ])
    
    # Remove duplicates and empty variants
    variants = list(dict.fromkeys([v.strip() for v in variants if v.strip()]))
    
    return variants[:4]  # Limit to prevent too many API calls

def search_google_images_enhanced(search_query):
    """Enhanced Google Custom Search with quality scoring and relevance filtering"""
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
            'num': 10,
            'rights': 'cc_publicdomain,cc_attribute,cc_sharealike',
            'fileType': 'jpg,png',
            'imgColorType': 'color'
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if 'items' in data:
            # Score and rank images by relevance
            scored_images = []
            
            for item in data['items']:
                image_url = item.get('link', '')
                title = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                
                # Calculate relevance score
                score = calculate_image_relevance_score(
                    search_query, image_url, title, snippet
                )
                
                if score > 0 and validate_image_url(image_url):
                    scored_images.append((image_url, score))
            
            # Return highest scoring image
            if scored_images:
                scored_images.sort(key=lambda x: x[1], reverse=True)
                return scored_images[0][0]
                    
    except Exception as e:
        logging.error(f"Enhanced Google image search failed for '{search_query}': {e}")
    
    return None

def calculate_image_relevance_score(search_query, image_url, title, snippet):
    """Calculate relevance score for image based on multiple factors"""
    score = 0
    query_terms = search_query.lower().split()
    
    # High-quality domain bonus
    preferred_domains = [
        'wikimedia.org', 'wikipedia.org', 'unsplash.com', 'pexels.com',
        'flickr.com', 'commons.wikimedia.org', 'upload.wikimedia.org'
    ]
    
    if any(domain in image_url.lower() for domain in preferred_domains):
        score += 30
    
    # Penalize low-quality domains
    bad_domains = [
        'pinterest.com', 'facebook.com', 'instagram.com', 'twitter.com',
        'tiktok.com', 'snapchat.com', 'reddit.com', 'tumblr.com'
    ]
    
    if any(domain in image_url.lower() for domain in bad_domains):
        score -= 20
    
    # Brand/company name exact match bonus
    brand_terms = ['logo', 'brand', 'official', 'jaguar', 'land rover', 'tesla', 'apple', 'microsoft']
    
    for term in query_terms:
        if term in brand_terms:
            if term in title or term in snippet:
                score += 25
            if term in image_url.lower():
                score += 15
    
    # General term matching
    for term in query_terms:
        if len(term) > 2:  # Skip short words
            if term in title:
                score += 10
            if term in snippet:
                score += 8
            if term in image_url.lower():
                score += 5
    
    # Logo/official image indicators
    logo_indicators = ['logo', 'official', 'brand', 'symbol', 'emblem']
    if any(indicator in title or indicator in snippet for indicator in logo_indicators):
        score += 15
    
    # File type bonus (prefer PNG for logos, JPG for photos)
    if 'logo' in search_query and image_url.lower().endswith('.png'):
        score += 10
    elif 'logo' not in search_query and image_url.lower().endswith('.jpg'):
        score += 5
    
    return max(0, score)  # Ensure non-negative score

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
            'num': 10,
            'rights': 'cc_publicdomain,cc_attribute,cc_sharealike'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'items' in data:
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
            return data['results'][0]['urls']['regular']
            
    except Exception as e:
        logging.error(f"Unsplash image search failed for '{search_query}': {e}")
    
    return None

def get_default_security_image(search_query):
    """Return a curated default image with rotation to prevent repetition"""
    # Comprehensive image dictionary with multiple options per category
    default_images = {
        # Automotive brands - multiple variants
        'jaguar': [
            'https://upload.wikimedia.org/wikipedia/en/thumb/e/e9/Jaguar_Cars_logo.svg/1200px-Jaguar_Cars_logo.svg.png',
            'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=800', # Jaguar car
            'https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800'  # Luxury car
        ],
        'land rover': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Land_Rover_logo.svg/1200px-Land_Rover_logo.svg.png',
            'https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=800', # SUV
            'https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800'  # Off-road vehicle
        ],
        'tesla': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bd/Tesla_Motors.svg/1200px-Tesla_Motors.svg.png',
            'https://images.unsplash.com/photo-1560958089-b8a1929cea89?w=800', # Tesla Model S
            'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800', # Electric car charging
            'https://images.unsplash.com/photo-1593941707882-a5bac6861d75?w=800'  # Tesla interior
        ],
        'ford': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Ford_logo_flat.svg/1200px-Ford_logo_flat.svg.png',
            'https://images.unsplash.com/photo-1583121274602-3e2820c69888?w=800', # Ford Mustang
            'https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800'   # Ford F-150
        ],
        'bmw': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/BMW.svg/1200px-BMW.svg.png',
            'https://images.unsplash.com/photo-1555215695-3004980ad54e?w=800', # BMW sedan
            'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800'  # BMW sports car
        ],
        'mercedes': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Mercedes-Logo.svg/1200px-Mercedes-Logo.svg.png',
            'https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=800', # Mercedes luxury
            'https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?w=800'  # Mercedes AMG
        ],
        'toyota': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Toyota-Logo.svg/1200px-Toyota-Logo.svg.png',
            'https://images.unsplash.com/photo-1621135802920-133df287f89c?w=800', # Toyota Prius
            'https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=800'   # Toyota sedan
        ],
        'volkswagen': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Volkswagen_logo_2019.svg/1200px-Volkswagen_logo_2019.svg.png',
            'https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?w=800'
        ],
        'audi': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/9/92/Audi-Logo_2016.svg/1200px-Audi-Logo_2016.svg.png',
            'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=800'
        ],
        'porsche': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Porsche_logo.svg/1200px-Porsche_logo.svg.png',
            'https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800'
        ],
        'honda': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Honda_Logo.svg/1200px-Honda_Logo.svg.png',
            'https://images.unsplash.com/photo-1619976215249-95e661cbd259?w=800'
        ],
        
        # Tech companies - multiple variants
        'apple': [
            'https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg',
            'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=800', # Apple devices
            'https://images.unsplash.com/photo-1512054502232-10a0a035d672?w=800', # iPhone
            'https://images.unsplash.com/photo-1484704849700-f032a568e944?w=800'  # MacBook
        ],
        'microsoft': [
            'https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg',
            'https://images.unsplash.com/photo-1633265486064-086b219458ec?w=800', # Windows
            'https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=800', # Surface device
            'https://images.unsplash.com/photo-1606868306217-dbf5046868d2?w=800'  # Office 365
        ],
        'google': [
            'https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg',
            'https://images.unsplash.com/photo-1573804633927-bfcbcd909acd?w=800', # Google search
            'https://images.unsplash.com/photo-1611224923853-80b023f02d71?w=800', # Android
            'https://images.unsplash.com/photo-1607936854279-55e8f4bc0b9a?w=800'  # Google Pixel
        ],
        'amazon': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Amazon_logo.svg/1200px-Amazon_logo.svg.png',
            'https://images.unsplash.com/photo-1523474253046-8cd2748b5fd2?w=800', # Amazon packages
            'https://images.unsplash.com/photo-1586880244406-556ebe35f282?w=800', # AWS cloud
            'https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=800'   # Amazon Echo
        ],
        'meta': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/1200px-Meta_Platforms_Inc._logo.svg.png',
            'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800', # VR headset
            'https://images.unsplash.com/photo-1611605698335-8b1569810432?w=800'  # Social media
        ],
        'facebook': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/1200px-Meta_Platforms_Inc._logo.svg.png',
            'https://images.unsplash.com/photo-1611605698335-8b1569810432?w=800'
        ],
        'netflix': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Netflix_2015_logo.svg/1200px-Netflix_2015_logo.svg.png',
            'https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=800'
        ],
        'spotify': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Spotify_logo_without_text.svg/1200px-Spotify_logo_without_text.svg.png',
            'https://images.unsplash.com/photo-1614680376593-902f74cf0d41?w=800'
        ],
        'nvidia': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/NVIDIA_logo.svg/1200px-NVIDIA_logo.svg.png',
            'https://images.unsplash.com/photo-1591488320449-011701bb6704?w=800'
        ],
        'intel': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Intel-logo.svg/1200px-Intel-logo.svg.png',
            'https://images.unsplash.com/photo-1555617981-dac3880eac6e?w=800'
        ],
        'cisco': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/6/64/Cisco_logo.svg/1200px-Cisco_logo.svg.png',
            'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800'
        ],
        'oracle': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Oracle_logo.svg/1200px-Oracle_logo.svg.png',
            'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800'
        ],
        'salesforce': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Salesforce.com_logo.svg/1200px-Salesforce.com_logo.svg.png',
            'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800'
        ],
        
        # Financial institutions
        'visa': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Visa_Inc._logo.svg/1200px-Visa_Inc._logo.svg.png',
            'https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=800'
        ],
        'mastercard': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/MasterCard_Logo.svg/1200px-MasterCard_Logo.svg.png',
            'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=800'
        ],
        'paypal': [
            'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/PayPal.svg/1200px-PayPal.svg.png',
            'https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=800'
        ],
        
        # Industry sectors - multiple options each
        'automotive': [
            'https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800',
            'https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=800',
            'https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800',
            'https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=800'
        ],
        'banking': [
            'https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800',
            'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?w=800',
            'https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=800',
            'https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=800'
        ],
        'healthcare': [
            'https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=800',
            'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800',
            'https://images.unsplash.com/photo-1538108149393-fbbd81895907?w=800',
            'https://images.unsplash.com/photo-1559757175-0eb30cd8c063?w=800'
        ],
        'aviation': [
            'https://images.unsplash.com/photo-1540962351504-03099e0a754b?w=800',
            'https://images.unsplash.com/photo-1556388158-158ea5ccacbd?w=800',
            'https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=800'
        ],
        'manufacturing': [
            'https://images.unsplash.com/photo-1565514020179-026b92b84bb6?w=800',
            'https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=800',
            'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800'
        ],
        
        # Products - multiple variants
        'iphone': [
            'https://images.unsplash.com/photo-1512054502232-10a0a035d672?w=800',
            'https://images.unsplash.com/photo-1517077304055-6e89abbf09b0?w=800',
            'https://images.unsplash.com/photo-1484704849700-f032a568e944?w=800'
        ],
        'android': [
            'https://images.unsplash.com/photo-1607936854279-55e8f4bc0b9a?w=800',
            'https://images.unsplash.com/photo-1611224923853-80b023f02d71?w=800',
            'https://images.unsplash.com/photo-1573804633927-bfcbcd909acd?w=800'
        ],
        'windows': [
            'https://images.unsplash.com/photo-1633265486064-086b219458ec?w=800',
            'https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=800',
            'https://images.unsplash.com/photo-1606868306217-dbf5046868d2?w=800'
        ],
        
        # Generic security - many variants to prevent repetition
        'security': [
            'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=800',
            'https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800',
            'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800',
            'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800',
            'https://images.unsplash.com/photo-1516321497487-e288fb19713f?w=800'
        ],
        'cybersecurity': [
            'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=800',
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800',
            'https://images.unsplash.com/photo-1573164713714-d95e436ab8d6?w=800',
            'https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800',
            'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800'
        ],
        'network': [
            'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800',
            'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=800',
            'https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=800',
            'https://images.unsplash.com/photo-1573804633927-bfcbcd909acd?w=800'
        ],
        'data': [
            'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800',
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800',
            'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
            'https://images.unsplash.com/photo-1573164713714-d95e436ab8d6?w=800'
        ],
        'technology': [
            'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800',
            'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800',
            'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800',
            'https://images.unsplash.com/photo-1555617981-dac3880eac6e?w=800'
        ]
    }
    
    query_lower = search_query.lower()
    
    # Try exact matches first (highest priority)
    for term, images in default_images.items():
        if term == query_lower:
            selected_image = rotate_image_selection(images, f"exact_{term}")
            logging.info(f'🎯 Exact match default image for: {term} -> {selected_image}')
            return selected_image
    
    # Try partial matches
    for term, images in default_images.items():
        if term in query_lower:
            selected_image = rotate_image_selection(images, f"partial_{term}")
            logging.info(f'🎯 Partial match default image for: {term} -> {selected_image}')
            return selected_image
    
    # Ultimate fallback with rotation
    fallback_images = [
        'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=800',
        'https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800',
        'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800',
        'https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=800'
    ]
    selected_image = rotate_image_selection(fallback_images, "fallback")
    logging.info(f'🎯 Using ultimate fallback security image -> {selected_image}')
    return selected_image

def rotate_image_selection(images, category_key):
    """Rotate through images to prevent repetition using simple hash-based selection"""
    if isinstance(images, str):
        return images
    
    if not images or len(images) == 0:
        return 'https://images.unsplash.com/photo-1555421689-491a97ff2040?w=800'
    
    # Use current timestamp and category to create pseudo-random but deterministic selection
    # This ensures different images are selected over time but same selection for same timestamp
    import time
    current_hour = int(time.time() // 3600)  # Change selection every hour
    
    # Create a simple hash from category and time
    selection_hash = hash(f"{category_key}_{current_hour}") % len(images)
    
    return images[selection_hash]

def main(mytimer: func.TimerRequest) -> None:
    """Simple RSS + Web Crawler for Cybersecurity Blog Posts"""
    logging.info('🚀 ArugaCyber Article Generator started')
    
    # Get OpenAI client
    openai_client = None
    if os.environ.get('OPENAI_API_KEY'):
        openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        logging.info('✅ OpenAI client initialized')
    else:
        logging.error('❌ No OpenAI API key found')
        return
    
    # Get configurable storage settings
    storage_connection = os.environ.get('AzureWebJobsStorage')
    container_name = os.environ.get('STORAGE_CONTAINER_NAME', 'articles')
    
    # Get blob storage client
    try:
        blob_service = BlobServiceClient.from_connection_string(storage_connection)
        container_client = blob_service.get_container_client(container_name)
        
        try:
            container_client.create_container()
        except:
            pass
            
        logging.info('✅ Azure Storage initialized')
    except Exception as e:
        logging.error(f'❌ Azure Storage failed: {e}')
        return
    
    # Get configurable RSS feeds from environment
    rss_feeds_env = os.environ.get('RSS_FEEDS', 
        'https://krebsonsecurity.com/feed/,https://www.bleepingcomputer.com/feed/,https://feeds.feedburner.com/TheHackersNews,https://www.darkreading.com/rss.xml,https://www.securityweek.com/feed/,https://feeds.feedburner.com/eset/blog')
    rss_feeds = [feed.strip() for feed in rss_feeds_env.split(',')]
    
    logging.info(f'📡 Configured RSS feeds: {len(rss_feeds)} sources')
    
    # Get existing articles
    existing_articles = set()
    try:
        for blob in container_client.list_blobs():
            existing_articles.add(blob.name)
        logging.info(f'📁 Found {len(existing_articles)} existing articles')
    except:
        pass
    
    articles_created = 0
    
    # Process each RSS feed
    for feed_url in rss_feeds:
        try:
            logging.info(f'📡 Processing RSS feed: {feed_url}')
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                logging.warning(f'⚠️  No entries in feed: {feed_url}')
                continue
            
            # Get configurable number of articles per feed
            articles_per_feed = int(os.environ.get('ARTICLES_PER_FEED', '3'))
            
            # Process latest articles from each feed
            for entry in feed.entries[:articles_per_feed]:
                try:
                    article_url = entry.link
                    article_title = entry.title
                    
                    logging.info(f'🔍 Crawling article: {article_title[:60]}...')
                    
                    # Create filename
                    filename = create_filename(article_url)
                    if filename in existing_articles:
                        logging.info(f'⏭️  Skipping existing: {filename}')
                        continue
                    
                    # Extract full article content
                    full_content = extract_full_article_content(article_url)
                    
                    if not full_content or len(full_content) < 500:
                        logging.warning(f'⚠️  Insufficient content extracted from {article_url}')
                        continue
                    
                    logging.info(f'✅ Extracted {len(full_content)} characters')
                    
                    # Generate comprehensive blog post using AI
                    blog_post = generate_blog_post_with_ai(
                        title=article_title,
                        full_content=full_content,
                        source_url=article_url,
                        openai_client=openai_client
                    )
                    
                    if blog_post:
                        # Create complete HTML with AI-generated thumbnail
                        html_content = create_blog_html(blog_post, openai_client)
                        
                        # Upload to storage
                        blob_client = container_client.get_blob_client(filename)
                        blob_client.upload_blob(html_content, overwrite=True, content_type='text/html')
                        
                        articles_created += 1
                        logging.info(f'✅ Created blog post: {filename}')
                        
                        # Rate limiting
                        time.sleep(2)
                    else:
                        logging.error(f'❌ Failed to generate blog post for: {article_title}')
                        
                except Exception as e:
                    logging.error(f'❌ Error processing article: {e}')
                    continue
                    
        except Exception as e:
            logging.error(f'❌ Error processing feed {feed_url}: {e}')
            continue
    
    logging.info(f'🎉 Article generation complete! Created {articles_created} blog posts')

def create_filename(url: str) -> str:
    """Create filename from URL"""
    domain = url.split('/')[2].replace('www.', '').replace('.', '-')
    timestamp = datetime.now().strftime('%Y%m%d-%H%M')
    return f"{domain}-{timestamp}.html"

def extract_full_article_content(url: str) -> str:
    """Extract full article content from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        logging.info(f'🌐 Fetching content from: {url}')
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 
                           '.advertisement', '.ads', '.social-share', '.comments',
                           '.navigation', '.sidebar', '.related-articles']):
            if element:
                element.decompose()
        
        # Site-specific content selectors
        domain = url.lower()
        content = ""
        
        # Try site-specific selectors first
        if 'krebsonsecurity.com' in domain:
            selectors = ['.entry-content', '.post-content', 'article .content']
        elif 'bleepingcomputer.com' in domain:
            selectors = ['.articleBody', '.news_content', '.article_section']
        elif 'thehackernews.com' in domain:
            selectors = ['.post-body', '.story-content', '.article-content']
        elif 'darkreading.com' in domain:
            selectors = ['.article-content', '.content-body', '.post-content']
        elif 'securityweek.com' in domain:
            selectors = ['.field-name-body', '.article-body', '.content']
        elif 'welivesecurity.com' in domain:  # ESET blog
            selectors = ['.post-content', '.entry-content', '.article-body']
        else:
            selectors = []
        
        # Add generic selectors
        selectors.extend([
            'article', '.article-content', '.post-content', '.entry-content',
            '.content', '.main-content', '[role="main"]', '.story-body',
            'main article', '.post-body'
        ])
        
        # Try each selector until we find substantial content
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(separator=' ', strip=True)
                    cleaned_text = ' '.join(text.split())
                    
                    if len(cleaned_text) > 500:
                        content = cleaned_text
                        logging.info(f'✅ Content extracted using selector: {selector}')
                        break
            except:
                continue
        
        # Fallback to body content
        if not content or len(content) < 300:
            logging.info('🔄 Using body fallback for content extraction')
            body_text = soup.get_text(separator=' ', strip=True)
            content = ' '.join(body_text.split())
        
        # Get configurable content length limit
        max_content_length = int(os.environ.get('CONTENT_MAX_LENGTH', '12000'))
        
        # Limit content size for AI processing
        if len(content) > max_content_length:
            content = content[:max_content_length]
            logging.info(f'📏 Content truncated to {len(content)} characters')
        
        return content
        
    except Exception as e:
        logging.error(f'❌ Failed to extract content from {url}: {e}')
        return ""

def generate_blog_post_with_ai(title: str, full_content: str, source_url: str, openai_client) -> dict:
    """Generate comprehensive blog post using AI with full article content"""
    
    if not openai_client:
        return None
        
    try:
        logging.info(f'🤖 Generating AI blog post for: {title[:50]}...')
        
        # Extract key cybersecurity keywords
        keywords = extract_cybersecurity_keywords(full_content)
        
        # Determine threat level
        threat_level = assess_threat_level(title, full_content)
        
        # Create comprehensive prompt with full context
        prompt = f"""
You are a senior cybersecurity journalist. Create a comprehensive, informative blog post based on this FULL ARTICLE CONTENT.

ORIGINAL ARTICLE TITLE: {title}
FULL ARTICLE CONTENT: {full_content}
SOURCE URL: {source_url}

BLOG POST REQUIREMENTS:
1. OPENING HOOK: Start with a compelling statistic, fact, or statement from the article
2. CLEAR INTRODUCTION: Summarize what happened and why it matters (2-3 paragraphs)
3. DETAILED ANALYSIS: Break down the technical details, attack methods, impact (multiple sections with subheadings)
4. BUSINESS IMPLICATIONS: Explain the broader impact on organizations and industries
5. SECURITY RECOMMENDATIONS: Provide specific, actionable advice for security teams
6. CONCLUSION: Summarize key takeaways and next steps

CONTENT GUIDELINES:
- Use ALL specific details from the full article (company names, technical specs, dates, numbers)
- Write in UK English for cybersecurity professionals
- Include technical analysis suitable for security experts
- Minimum 1000 words of substantial content
- Use clear subheadings with ## for main sections and ### for subsections
- Format lists with bullet points or numbers for readability
- Extract and use actual quotes, statistics, and facts from the source article
- Focus on actionable intelligence and insights

FORMATTING REQUIREMENTS:
- Use ## for main section headers (e.g., ## Technical Analysis)
- Use ### for subsection headers (e.g., ### Attack Methodology)
- Use bullet points (-) for lists and key points
- Keep paragraphs to 2-4 sentences for readability
- Use **bold** for important terms and concepts

Create a comprehensive, fact-based blog post with consistent formatting that provides real value to cybersecurity professionals.
"""

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a cybersecurity expert and professional journalist. Create comprehensive, factual blog posts using the provided source material. Extract specific details, technical information, and actionable insights from the source content."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=3000,
            temperature=0.1  # Low temperature for factual accuracy
        )
        
        blog_content = response.choices[0].message.content.strip()
        
        # Generate AI-powered unique title
        ai_title = generate_unique_title(title, blog_content[:500], openai_client)
        
        # Create blog post object
        blog_post = {
            'title': ai_title,
            'original_title': title,  # Keep original for reference
            'content': blog_content,
            'source_url': source_url,
            'keywords': keywords,
            'threat_level': threat_level,
            'generated_at': datetime.now().isoformat(),
            'content_length': len(blog_content)
        }
        
        logging.info(f'✅ Generated {len(blog_content)} character blog post')
        return blog_post
        
    except Exception as e:
        logging.error(f'❌ AI blog generation failed: {e}')
        return None

def extract_cybersecurity_keywords(content: str) -> list:
    """Extract cybersecurity keywords from content"""
    cyber_keywords = [
        'malware', 'ransomware', 'phishing', 'vulnerability', 'exploit', 'breach', 
        'hack', 'trojan', 'virus', 'botnet', 'ddos', 'apt', 'zero-day', 'cve',
        'patch', 'firewall', 'encryption', 'authentication', 'cybersecurity',
        'threat', 'attack', 'security', 'compromise', 'incident', 'data breach',
        'spyware', 'rootkit', 'backdoor', 'social engineering'
    ]
    
    found_keywords = []
    content_lower = content.lower()
    
    for keyword in cyber_keywords:
        if keyword in content_lower:
            found_keywords.append(keyword)
            
    return found_keywords[:8]  # Limit to top 8

def assess_threat_level(title: str, content: str) -> str:
    """Assess threat level based on configurable content indicators"""
    text = (title + ' ' + content).lower()
    
    # Get configurable threat indicators from environment
    critical_indicators = os.environ.get('THREAT_KEYWORDS_CRITICAL', 
        'zero-day,critical,emergency,widespread,global,critical vulnerability').split(',')
    high_indicators = os.environ.get('THREAT_KEYWORDS_HIGH',
        'breach,ransomware,apt,exploit,vulnerability,attack,compromise').split(',')
    medium_indicators = os.environ.get('THREAT_KEYWORDS_MEDIUM',
        'phishing,malware,threat,security,incident').split(',')
    
    # Clean keywords
    critical_indicators = [k.strip().lower() for k in critical_indicators]
    high_indicators = [k.strip().lower() for k in high_indicators]
    medium_indicators = [k.strip().lower() for k in medium_indicators]
    
    if any(indicator in text for indicator in critical_indicators):
        return 'CRITICAL'
    elif any(indicator in text for indicator in high_indicators):
        return 'HIGH'  
    elif any(indicator in text for indicator in medium_indicators):
        return 'MEDIUM'
    else:
        return 'LOW'

def generate_unique_title(original_title: str, content_preview: str, openai_client) -> str:
    """Generate a unique, compelling title using AI"""
    try:
        if not openai_client:
            return create_compelling_title(original_title)
        
        prompt = f"""
        Create a unique, compelling cybersecurity blog post title based on this information:
        
        Original Title: "{original_title}"
        Content Preview: "{content_preview}"
        
        Requirements:
        1. Make it different from the original title but cover the same topic
        2. Keep it professional and suitable for cybersecurity professionals
        3. Make it engaging and click-worthy
        4. Maximum 80 characters
        5. Focus on the key security implications or business impact
        6. Use active voice when possible
        7. Avoid generic terms like "New Study" or "Report Shows"
        
        Examples of good transformations:
        - "Company X Suffers Data Breach" → "How Company X Lost 50,000 Customer Records to Hackers"
        - "New Malware Discovered" → "Critical Banking Trojan Threatens Financial Institutions Worldwide"
        - "Vulnerability Found in Software" → "Zero-Day Flaw Exposes Millions of Users to Remote Attacks"
        
        Return only the new title, nothing else.
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.4  # Slight creativity while maintaining professionalism
        )
        
        ai_title = response.choices[0].message.content.strip()
        
        # Clean up the response
        ai_title = ai_title.strip('"').strip("'")  # Remove quotes if present
        
        # Ensure it's not too long
        if len(ai_title) > 80:
            ai_title = ai_title[:77] + "..."
        
        # Fallback to original if AI returns empty
        return ai_title if ai_title else create_compelling_title(original_title)
        
    except Exception as e:
        logging.error(f"Error generating AI title: {e}")
        return create_compelling_title(original_title)

def create_compelling_title(original_title: str) -> str:
    """Fallback title creation when AI is not available"""
    # Clean and enhance the original title
    if len(original_title) > 80:
        return original_title[:77] + "..."
    return original_title

def create_blog_html(blog_post: dict, openai_client) -> str:
    """Create comprehensive HTML blog post with AI-generated thumbnail"""
    
    # Generate AI-powered thumbnail image
    thumbnail_search_keywords = extract_keywords_for_image_search(
        blog_post['title'], 
        blog_post['content'][:500],  # Use first 500 chars as description
        openai_client
    )
    
    hero_image = search_for_thumbnail_image(thumbnail_search_keywords)
    logging.info(f'🖼️ Generated thumbnail with keywords: {thumbnail_search_keywords}')
    
    # Format content for HTML
    formatted_content = format_blog_content_for_html(blog_post['content'])
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{blog_post['title']}</title>
    <meta name="description" content="Professional cybersecurity analysis and threat intelligence">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary-color: #FF5A5A;
            --secondary-color: #FF6B6B;
            --accent-color: #FF4757;
            --background-color: #0a0a0a;
            --surface-color: #1a1a1a;
            --card-color: #242424;
            --text-primary: #FFFFFF;
            --text-secondary: #E5E5E5;
            --text-muted: #A0A0A0;
            --text-disabled: #666666;
            --border-color: #333333;
            --success-color: #10B981;
            --warning-color: #F59E0B;
            --error-color: #EF4444;
            --font-primary: 'Inter', system-ui, -apple-system, sans-serif;
            --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.1);
            --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.15);
            --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.2);
            --shadow-xl: 0 16px 40px rgba(0, 0, 0, 0.25);
            --border-radius-sm: 6px;
            --border-radius-md: 12px;
            --border-radius-lg: 20px;
            --border-radius-xl: 24px;
            --spacing-xs: 0.5rem;
            --spacing-sm: 0.75rem;
            --spacing-md: 1rem;
            --spacing-lg: 1.5rem;
            --spacing-xl: 2rem;
            --spacing-2xl: 3rem;
            --spacing-3xl: 4rem;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{ 
            font-family: var(--font-primary); 
            background: var(--background-color); 
            color: var(--text-primary); 
            line-height: 1.6; 
            font-size: 16px;
            font-weight: 400;
            overflow-x: hidden;
        }}
        
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 0 var(--spacing-lg); 
        }}
        
        /* Header Styling */
        .header {{ 
            background: linear-gradient(135deg, var(--surface-color) 0%, var(--card-color) 100%); 
            padding: var(--spacing-xl) 0; 
            border-bottom: 1px solid var(--border-color);
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color), var(--accent-color));
        }}
        
        .logo {{ 
            font-size: clamp(2.5rem, 5vw, 4rem);
            font-weight: 700; 
            color: var(--primary-color); 
            text-align: center; 
            margin-bottom: var(--spacing-sm);
            letter-spacing: -0.02em;
            text-shadow: 0 2px 4px rgba(255, 90, 90, 0.3);
        }}
        
        .tagline {{ 
            text-align: center; 
            font-size: clamp(1rem, 2.5vw, 1.25rem);
            color: var(--text-muted); 
            font-weight: 300;
            letter-spacing: 0.5px; 
        }}
        
        /* Main Article Styling */
        .article {{ 
            background: var(--card-color); 
            margin: var(--spacing-2xl) 0; 
            border-radius: var(--border-radius-xl); 
            overflow: hidden; 
            box-shadow: var(--shadow-xl);
            border: 1px solid var(--border-color);
        }}
        
        /* Hero Section */
        .hero-section {{ 
            position: relative; 
            height: clamp(300px, 50vh, 500px);
            overflow: hidden;
        }}
        
        .hero-image {{ 
            width: 100%; 
            height: 100%; 
            object-fit: cover;
            transition: transform 0.3s ease;
        }}
        
        .hero-image:hover {{
            transform: scale(1.02);
        }}
        
        .hero-overlay {{ 
            position: absolute; 
            bottom: 0; 
            left: 0; 
            right: 0; 
            background: linear-gradient(transparent 0%, rgba(0,0,0,0.3) 30%, rgba(0,0,0,0.9) 100%); 
            padding: var(--spacing-2xl);
        }}
        
        .article-title {{ 
            font-size: clamp(1.75rem, 4vw, 3rem);
            font-weight: 700; 
            color: var(--text-primary); 
            margin-bottom: var(--spacing-lg); 
            line-height: 1.1;
            letter-spacing: -0.02em;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
        }}
        
        .article-meta {{ 
            color: var(--text-secondary); 
            font-size: clamp(0.9rem, 2vw, 1.1rem);
            font-weight: 400;
            display: flex;
            align-items: center;
            gap: var(--spacing-md);
            flex-wrap: wrap;
        }}
        
        /* Threat Badge */
        .threat-badge {{
            display: inline-flex;
            align-items: center;
            padding: var(--spacing-xs) var(--spacing-md);
            border-radius: var(--border-radius-sm);
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: var(--shadow-sm);
        }}
        
        .threat-critical {{ background: linear-gradient(135deg, #DC2626, #B91C1C); color: white; }}
        .threat-high {{ background: linear-gradient(135deg, #EA580C, #DC2626); color: white; }}
        .threat-medium {{ background: linear-gradient(135deg, #D97706, #EA580C); color: white; }}
        .threat-low {{ background: linear-gradient(135deg, #059669, #047857); color: white; }}
        
        /* Content Layout */
        .content {{ 
            display: grid;
            grid-template-columns: 1fr 280px;
            gap: var(--spacing-2xl);
            padding: var(--spacing-2xl);
            align-items: start;
        }}
        
        .main-content {{
            min-width: 0; /* Prevent grid overflow */
        }}
        
        /* Typography */
        .content h2 {{ 
            color: var(--primary-color); 
            font-size: clamp(1.5rem, 3vw, 2.25rem);
            font-weight: 600; 
            margin: var(--spacing-2xl) 0 var(--spacing-lg) 0; 
            line-height: 1.2;
            position: relative;
            padding-bottom: var(--spacing-md);
        }}
        
        .content h2::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 60px;
            height: 3px;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            border-radius: 2px;
        }}
        
        .content h3 {{ 
            color: var(--secondary-color); 
            font-size: clamp(1.25rem, 2.5vw, 1.5rem);
            font-weight: 600; 
            margin: var(--spacing-xl) 0 var(--spacing-md) 0; 
            line-height: 1.3;
        }}
        
        .content h2:first-child {{
            margin-top: 0;
        }}
        
        .content strong {{
            color: var(--text-primary);
            font-weight: 600;
        }}
        
        .content p {{ 
            margin: var(--spacing-lg) 0; 
            color: var(--text-secondary); 
            font-size: 1.1rem;
            line-height: 1.7;
        }}
        
        .content ul, .content ol {{ 
            margin: var(--spacing-lg) 0; 
            padding-left: var(--spacing-xl);
        }}
        
        .content li {{ 
            margin-bottom: var(--spacing-md); 
            color: var(--text-secondary); 
            line-height: 1.6;
            font-size: 1.05rem;
        }}
        
        .content ul li::marker {{
            color: var(--primary-color);
        }}
        
        .content ol li::marker {{
            color: var(--primary-color);
        }}
        
        /* Sidebar Stats Section */
        .stats-sidebar {{
            background: linear-gradient(135deg, rgba(255, 90, 90, 0.08), rgba(255, 107, 107, 0.05));
            border: 1px solid rgba(255, 90, 90, 0.2);
            border-radius: var(--border-radius-lg);
            padding: var(--spacing-lg);
            backdrop-filter: blur(10px);
            position: sticky;
            top: var(--spacing-xl);
            height: fit-content;
        }}
        
        .stats-sidebar h3 {{
            color: var(--primary-color);
            font-size: 1rem;
            margin-bottom: var(--spacing-md);
            text-align: center;
        }}
        
        .stats-grid {{
            display: flex;
            flex-direction: column;
            gap: var(--spacing-sm);
        }}
        
        .stat-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            padding: var(--spacing-sm);
            background: rgba(255, 255, 255, 0.03);
            border-radius: var(--border-radius-sm);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .stat-label {{
            font-weight: 500;
            color: var(--text-muted);
            font-size: 0.8rem;
            margin-bottom: var(--spacing-xs);
        }}
        
        .stat-value {{
            font-weight: 600;
            color: var(--text-primary);
            font-size: 0.9rem;
            word-break: break-word;
        }}
        
        /* Links */
        a {{ 
            color: var(--primary-color); 
            text-decoration: none; 
            font-weight: 500;
            transition: all 0.2s ease;
        }}
        
        a:hover {{ 
            color: var(--secondary-color); 
            text-decoration: underline;
        }}
        
        /* Source Section */
        .source-section {{
            margin-top: var(--spacing-2xl);
            padding-top: var(--spacing-xl);
            border-top: 1px solid var(--border-color);
            background: rgba(255, 255, 255, 0.02);
            border-radius: var(--border-radius-lg);
            padding: var(--spacing-xl);
        }}
        
        .source-section h3 {{
            color: var(--text-primary);
            margin-bottom: var(--spacing-md);
        }}
        
        /* Footer */
        .footer {{ 
            background: var(--surface-color);
            padding: var(--spacing-2xl); 
            text-align: center; 
            color: var(--text-muted); 
            border-top: 1px solid var(--border-color);
            margin-top: var(--spacing-3xl);
        }}
        
        .footer p {{
            margin-bottom: var(--spacing-sm);
            font-size: 0.95rem;
        }}
        
        /* Responsive Design */
        @media (max-width: 1024px) {{
            .content {{
                grid-template-columns: 1fr 240px;
                gap: var(--spacing-lg);
            }}
            
            .stats-sidebar {{
                padding: var(--spacing-md);
            }}
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 0 var(--spacing-md);
            }}
            
            .content {{
                grid-template-columns: 1fr;
                gap: var(--spacing-lg);
                padding: var(--spacing-xl) var(--spacing-lg);
            }}
            
            .stats-sidebar {{
                position: relative;
                top: auto;
                order: -1; /* Show stats at top on mobile */
            }}
            
            .hero-overlay {{
                padding: var(--spacing-xl) var(--spacing-lg);
            }}
            
            .article-meta {{
                flex-direction: column;
                align-items: flex-start;
                gap: var(--spacing-sm);
            }}
        }}
        
        @media (max-width: 480px) {{
            .container {{
                padding: 0 var(--spacing-sm);
            }}
            
            .content {{
                padding: var(--spacing-lg) var(--spacing-md);
            }}
            
            .stats-sidebar {{
                padding: var(--spacing-md);
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="logo">ArugaCyber</h1>
            <p class="tagline">Advanced Cybersecurity Intelligence & Threat Analysis</p>
        </div>
    </header>
    
    <main class="container">
        <article class="article">
            <div class="hero-section">
                <img src="{hero_image}" alt="{blog_post['title']}" class="hero-image">
                <div class="hero-overlay">
                    <h1 class="article-title">{blog_post['title']}</h1>
                    <div class="article-meta">
                        <span>🔒 Cybersecurity Analysis</span>
                        <span>📅 {datetime.now().strftime('%d %B %Y')}</span>
                        <span>👥 ArugaCyber Research Team</span>
                        <span class="threat-badge threat-{blog_post['threat_level'].lower()}">🚨 {blog_post['threat_level']} THREAT</span>
                    </div>
                </div>
            </div>
            
            <div class="content">
                <div class="main-content">
                    {formatted_content}
                    
                    <div class="source-section">
                        <h3>🔗 Source Reference</h3>
                        <p>📰 <a href="{blog_post['source_url']}" target="_blank" rel="noopener">View Original Article</a></p>
                        <p style="margin-top: var(--spacing-md); font-size: 0.9rem; color: var(--text-disabled);">
                            This analysis was generated using advanced AI processing of the source material to provide cybersecurity professionals with comprehensive threat intelligence and actionable insights.
                        </p>
                    </div>
                </div>
                
                <aside class="stats-sidebar">
                    <h3>📊 Intelligence</h3>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <span class="stat-label">Content</span>
                            <span class="stat-value">{(blog_post['content_length'] // 1000)}k chars</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Keywords</span>
                            <span class="stat-value">{', '.join(blog_post.get('keywords', ['security'])[:2])}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Threat Level</span>
                            <span class="stat-value">{blog_post['threat_level']}</span>
                        </div>
                    </div>
                </aside>
            </div>
        </article>
    </main>
    
    <footer class="footer">
        <div class="container">
            <p><strong>🤖 Generated:</strong> {datetime.now().strftime('%d %B %Y, %H:%M UTC')} by ArugaCyber AI Intelligence System</p>
            <p><strong>🛡️ Classification:</strong> Professional Cybersecurity Threat Analysis & Intelligence Report</p>
        </div>
    </footer>
</body>
</html>"""


def format_blog_content_for_html(content: str) -> str:
    """Format AI-generated blog content for consistent HTML display"""
    
    # Clean up content first
    content = content.strip()
    
    # Convert various markdown header formats to HTML
    content = re.sub(r'^#{1,2}\s+(.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)  # # or ## headers
    content = re.sub(r'^#{3,4}\s+(.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)  # ### or #### headers
    
    # Handle bold markdown that might be used in headers
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    
    # Clean up any remaining markdown-style headers that weren't caught
    content = re.sub(r'^##\s*(.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
    content = re.sub(r'^###\s*(.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
    
    # Split content into sections by double newlines
    sections = re.split(r'\n\s*\n', content)
    formatted_sections = []
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Check if this section is a header
        if section.startswith('<h2>') or section.startswith('<h3>'):
            formatted_sections.append(section)
        else:
            # Handle regular paragraphs
            lines = section.split('\n')
            
            # If it's a single line, make it a paragraph
            if len(lines) == 1:
                formatted_sections.append(f'<p>{lines[0]}</p>')
            else:
                # Multiple lines - check if it's a list or paragraphs
                if any(line.strip().startswith(('•', '-', '*', '1.', '2.', '3.')) for line in lines):
                    # Format as a list
                    list_items = []
                    for line in lines:
                        line = line.strip()
                        if line.startswith(('•', '-', '*')):
                            list_items.append(f'<li>{line[1:].strip()}</li>')
                        elif re.match(r'^\d+\.', line):
                            list_items.append(f'<li>{re.sub(r"^\d+\.\s*", "", line)}</li>')
                        elif line:  # Non-list line
                            list_items.append(f'<li>{line}</li>')
                    
                    if list_items:
                        formatted_sections.append(f'<ul>{"".join(list_items)}</ul>')
                else:
                    # Format as paragraphs with line breaks
                    paragraph_text = '<br>'.join(line.strip() for line in lines if line.strip())
                    if paragraph_text:
                        formatted_sections.append(f'<p>{paragraph_text}</p>')
    
    # Join all sections
    formatted_content = '\n\n'.join(formatted_sections)
    
    # Final cleanup - ensure headers are properly closed
    formatted_content = re.sub(r'<h2>([^<]+)</h2>\s*<p>', r'<h2>\1</h2>\n<p>', formatted_content)
    formatted_content = re.sub(r'<h3>([^<]+)</h3>\s*<p>', r'<h3>\1</h3>\n<p>', formatted_content)
    
    # Remove any remaining markdown artifacts
    formatted_content = re.sub(r'#{1,6}\s*', '', formatted_content)
    
    return formatted_content
