# Blog Post Creator

🔐 **AI-Powered security Blog Generation System**

An intelligent Azure Function that automatically generates professional security blog posts by crawling RSS feeds, extracting full article content, and using AI to create comprehensive, technically accurate analysis articles.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Azure Functions](https://img.shields.io/badge/Azure-Functions-blue.svg)](https://azure.microsoft.com/en-us/services/functions/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI GPT-4](https://img.shields.io/badge/AI-GPT--4-green.svg)](https://openai.com/)

## 🏗️ Architecture Overview

```mermaid
graph TB
    subgraph "RSS Sources"
        A[Krebs on Security]
        B[Bleeping Computer] 
        C[The Hacker News]
        D[Other RSS Feeds]
    end
    
    subgraph "Azure Function App"
        E[Timer Trigger]
        F[RSS Feed Parser]
        G[Web Content Crawler]
        H[AI Content Generator]
        I[HTML Template Engine]
    end
    
    subgraph "External Services"
        J[OpenAI GPT-4 API]
        K[Azure Blob Storage]
    end
    
    subgraph "Output"
        L[Professional Blog Posts]
        M[Styled HTML Articles]
        N[Threat Intelligence]
    end
    
    A --> F
    B --> F
    C --> F
    D --> F
    
    E --> F
    F --> G
    G --> H
    H --> J
    J --> H
    H --> I
    I --> K
    K --> L
    L --> M
    M --> N
    
    style E fill:#ff5a5a,stroke:#fff,color:#fff
    style J fill:#00a86b,stroke:#fff,color:#fff
    style K fill:#0078d4,stroke:#fff,color:#fff
    style L fill:#ff6b6b,stroke:#fff,color:#fff
```

## 🔄 Data Flow Architecture

```mermaid
sequenceDiagram
    participant T as Timer Trigger
    participant R as RSS Parser
    participant W as Web Crawler
    participant AI as OpenAI GPT-4
    participant H as HTML Engine
    participant S as Blob Storage
    
    T->>R: Execute every 6 hours
    R->>R: Parse RSS feeds
    R->>W: Extract article URLs
    W->>W: Scrape full article content
    W->>AI: Send content for analysis
    AI->>AI: Generate comprehensive blog post
    AI->>H: Return formatted content
    H->>H: Apply professional styling
    H->>S: Upload HTML articles
    S->>S: Store for web delivery
    
    Note over T,S: Automated Content Pipeline
    Note over W,AI: Full Context Analysis
    Note over H,S: Professional Output
```

## ⚡ Key Features

- 🤖 **AI-Powered Analysis**: Uses GPT-4 to generate comprehensive security analysis
- 🌐 **Smart Web Crawling**: Extracts full article content from RSS feed links
- 🎨 **Professional Styling**: Dark theme with red accents, mobile responsive
- 📊 **Threat Assessment**: Automatically categorizes threat levels (Critical/High/Medium/Low)
- 🏷️ **Keyword Extraction**: Identifies relevant security terms and topics
- ☁️ **Azure Integration**: Seamless deployment with Azure Functions and Blob Storage
- 🔧 **Configurable Sources**: Easy to add/remove RSS feeds and customize behavior
- 📱 **Mobile Optimized**: Responsive design that works on all devices

## 🚀 Quick Start

### Prerequisites

- Azure Account with Function App
- OpenAI API Key
- Python 3.8+
- Azure CLI (for deployment)

### 1. Clone Repository

```bash
git clone https://github.com/your-username/blog-creator.git
cd blog-creator
```

### 2. Configure Environment

Create a `local.settings.json` file:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "your_azure_storage_connection_string",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "OPENAI_API_KEY": "your_openai_api_key_here",
    "RSS_FEEDS": "https://krebsonsecurity.com/feed/,https://www.bleepingcomputer.com/feed/,https://feeds.feedburner.com/TheHackersNews",
    "CONTENT_MAX_LENGTH": "12000",
    "ARTICLES_PER_FEED": "3",
    "LOG_LEVEL": "INFO",
    "STORAGE_CONTAINER_NAME": "articles"
  }
}
```

### 3. Deploy to Azure

Using Azure CLI:

```bash
# Login to Azure
az login

# Create resource group
az group create --name -rg --location "West Europe"

# Create storage account
az storage account create \
  --name storage \
  --resource-group -rg \
  --location "West Europe" \
  --sku Standard_LRS

# Create function app
az functionapp create \
  --resource-group -rg \
  --consumption-plan-location "West Europe" \
  --runtime python \
  --runtime-version 3.8 \
  --functions-version 4 \
  --name -functions \
  --storage-account storage

# Deploy function
func azure functionapp publish -functions
```

### 4. Configure Application Settings

```bash
az functionapp config appsettings set \
  --name -functions \
  --resource-group -rg \
  --settings \
  "OPENAI_API_KEY=your_api_key" \
  "RSS_FEEDS=https://krebsonsecurity.com/feed/,https://www.bleepingcomputer.com/feed/"
```

## ⚙️ Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 | - | ✅ |
| `AzureWebJobsStorage` | Azure Storage connection | - | ✅ |
| `RSS_FEEDS` | Comma-separated RSS feed URLs | See default config | ✅ |
| `CONTENT_MAX_LENGTH` | Max characters per article | 12000 | ❌ |
| `ARTICLES_PER_FEED` | Articles to process per feed | 3 | ❌ |
| `LOG_LEVEL` | Logging level | INFO | ❌ |
| `STORAGE_CONTAINER_NAME` | Blog storage container | articles | ❌ |

### Default RSS Feed Sources

- **Krebs on Security**: `https://krebsonsecurity.com/feed/`
- **Bleeping Computer**: `https://www.bleepingcomputer.com/feed/`
- **The Hacker News**: `https://feeds.feedburner.com/TheHackersNews`

Add custom feeds by updating the `RSS_FEEDS` environment variable.

## 🎨 System Functions

### GenerateArticles (Timer Function)
- **Trigger**: Timer (configurable schedule)
- **Default**: Every 6 hours
- **Process**: 
  1. Parse RSS feeds
  2. Extract full article content
  3. Generate AI-powered blog posts
  4. Store as styled HTML in blob storage

### GetArticles (HTTP Function)
- **Endpoint**: `/api/GetArticles`
- **Method**: GET
- **Response**: JSON list of all generated articles
- **Format**:
```json
{
  "total": 15,
  "articles": [
    {
      "name": "krebsonsecurity-com-20250910-1430.html",
      "url": "https://storage.blob.core.windows.net/articles/...",
      "created": "2025-09-10 14:30 UTC",
      "size": 4096
    }
  ]
}
```

### ClearArticles (HTTP Function)
- **Endpoint**: `/api/ClearArticles`
- **Method**: POST
- **Authorization**: Requires `Code` header
- **Function**: Removes all articles from storage
- **Response**: Count of deleted articles

## 🛠️ System Components

```mermaid
graph LR
    subgraph "Content Sources"
        A[RSS Feeds] --> B[Article URLs]
    end
    
    subgraph "Processing Pipeline"
        B --> C[Content Extraction]
        C --> D[AI Analysis]
        D --> E[Content Generation]
        E --> F[HTML Rendering]
    end
    
    subgraph "Output & Storage"
        F --> G[Styled Articles]
        G --> H[Blob Storage]
        H --> I[Web Delivery]
    end
    
    style A fill:#e1f5fe
    style D fill:#f3e5f5  
    style G fill:#fff3e0
    style I fill:#e8f5e8
```

## 🎨 Customization

### Adding New RSS Sources

Update the `RSS_FEEDS` environment variable:

```bash
RSS_FEEDS="https://krebsonsecurity.com/feed/,https://www.bleepingcomputer.com/feed/,https://your-custom-feed.com/rss"
```

### Styling Theme

Modify CSS variables in the HTML template:

```css
:root {
    --primary-color: #FF5A5A;      /* Main accent color */
    --secondary-color: #FF6B6B;    /* Secondary accent */
    --background-color: #000000;   /* Dark background */
    --text-primary: #FFFFFF;       /* Primary text */
    --text-secondary: #CCCCCC;     /* Secondary text */
}
```

### Content Generation

Blog posts follow this structure:
1. **Opening Hook** - Attention-grabbing statistics/facts
2. **Clear Introduction** - Context and importance
3. **Technical Analysis** - Detailed breakdown with subheadings
4. **Business Implications** - Impact assessment
5. **Security Recommendations** - Actionable advice
6. **Strong Conclusion** - Key takeaways and next steps

## 📊 Monitoring & Logging

The system provides comprehensive logging:

```
🚀  Article Generator started
📡 Processing RSS feed: https://krebsonsecurity.com/feed/
✅ Extracted 8,432 characters using selector: .entry-content
🤖 Generating AI blog post for: Critical Vulnerability Discovered...
✅ Generated 2,847 character blog post
✅ Created blog post: krebsonsecurity-com-20250910-1430.html
```

Monitor these key metrics:
- Articles processed per run
- Content extraction success rate
- AI generation completion rate
- Storage upload success rate

## 🔒 Security Features

- **Defensive Focus**: Only generates defensive security content
- **API Key Security**: Secure environment variable storage
- **Content Validation**: Automatic threat level assessment
- **Source Attribution**: All articles link back to original sources

## 🤝 Contributing

We welcome contributions! To get started:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
