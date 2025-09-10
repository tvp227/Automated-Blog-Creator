#!/bin/bash

# ArugaCyber Blog Creator - Azure Deployment Script
# This script automates the deployment of the ArugaCyber Blog Creator to Azure

set -e  # Exit on any error

# Configuration variables (modify these for your deployment)
RESOURCE_GROUP=${RESOURCE_GROUP:-"arugacyber-rg"}
LOCATION=${LOCATION:-"West Europe"}
STORAGE_ACCOUNT=${STORAGE_ACCOUNT:-"arugacyberstorage$(date +%s)"}
FUNCTION_APP=${FUNCTION_APP:-"arugacyber-functions$(date +%s)"}
SUBSCRIPTION_ID=${SUBSCRIPTION_ID:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Azure Functions Core Tools is installed
    if ! command -v func &> /dev/null; then
        log_error "Azure Functions Core Tools is not installed. Please install it first."
        log_info "Install with: npm install -g azure-functions-core-tools@4 --unsafe-perm true"
        exit 1
    fi
    
    # Check if user is logged in to Azure
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi
    
    log_success "Prerequisites check passed!"
}

# Get user inputs
get_user_inputs() {
    log_info "Getting deployment configuration..."
    
    # Get OpenAI API Key
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -n "Enter your OpenAI API Key: "
        read -r OPENAI_API_KEY
        if [ -z "$OPENAI_API_KEY" ]; then
            log_error "OpenAI API Key is required!"
            exit 1
        fi
    fi
    
    # Get custom RSS feeds (optional)
    if [ -z "$RSS_FEEDS" ]; then
        echo -n "Enter RSS feeds (comma-separated) or press Enter for defaults: "
        read -r RSS_FEEDS
        if [ -z "$RSS_FEEDS" ]; then
            RSS_FEEDS="https://krebsonsecurity.com/feed/,https://www.bleepingcomputer.com/feed/,https://feeds.feedburner.com/TheHackersNews"
        fi
    fi
    
    log_info "Using Resource Group: $RESOURCE_GROUP"
    log_info "Using Location: $LOCATION"
    log_info "Using Storage Account: $STORAGE_ACCOUNT"
    log_info "Using Function App: $FUNCTION_APP"
}

# Create Azure resources
create_resources() {
    log_info "Creating Azure resources..."
    
    # Create resource group
    log_info "Creating resource group: $RESOURCE_GROUP"
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output table
    
    # Create storage account
    log_info "Creating storage account: $STORAGE_ACCOUNT"
    az storage account create \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2 \
        --output table
    
    # Create function app
    log_info "Creating function app: $FUNCTION_APP"
    az functionapp create \
        --resource-group "$RESOURCE_GROUP" \
        --consumption-plan-location "$LOCATION" \
        --runtime python \
        --runtime-version 3.8 \
        --functions-version 4 \
        --name "$FUNCTION_APP" \
        --storage-account "$STORAGE_ACCOUNT" \
        --output table
    
    log_success "Azure resources created successfully!"
}

# Configure application settings
configure_app_settings() {
    log_info "Configuring application settings..."
    
    az functionapp config appsettings set \
        --name "$FUNCTION_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --settings \
        "OPENAI_API_KEY=$OPENAI_API_KEY" \
        "RSS_FEEDS=$RSS_FEEDS" \
        "CONTENT_MAX_LENGTH=12000" \
        "ARTICLES_PER_FEED=3" \
        "LOG_LEVEL=INFO" \
        "STORAGE_CONTAINER_NAME=articles" \
        "THREAT_KEYWORDS_CRITICAL=zero-day,critical,emergency,widespread,global,critical vulnerability" \
        "THREAT_KEYWORDS_HIGH=breach,ransomware,apt,exploit,vulnerability,attack,compromise" \
        "THREAT_KEYWORDS_MEDIUM=phishing,malware,threat,security,incident" \
        --output table
    
    log_success "Application settings configured!"
}

# Deploy function code
deploy_function() {
    log_info "Deploying function code..."
    
    # Build and deploy
    func azure functionapp publish "$FUNCTION_APP" --python
    
    log_success "Function deployed successfully!"
}

# Get function URLs
get_function_urls() {
    log_info "Getting function URLs..."
    
    # Get the function app URL
    FUNCTION_URL=$(az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "defaultHostName" --output tsv)
    
    echo ""
    log_success "Deployment completed successfully!"
    echo ""
    echo "=== ArugaCyber Blog Creator URLs ===" 
    echo "Function App: https://$FUNCTION_URL"
    echo "Get Articles: https://$FUNCTION_URL/api/GetArticles"
    echo "Clear Articles: https://$FUNCTION_URL/api/ClearArticles"
    echo ""
    echo "=== Next Steps ==="
    echo "1. The system will automatically start generating articles based on the timer schedule"
    echo "2. Visit the Get Articles URL to see generated articles"
    echo "3. Monitor the function execution in Azure Portal"
    echo ""
}

# Main deployment flow
main() {
    echo "🔐 ArugaCyber Blog Creator - Azure Deployment"
    echo "============================================="
    echo ""
    
    check_prerequisites
    get_user_inputs
    create_resources
    configure_app_settings
    deploy_function
    get_function_urls
    
    log_success "🎉 ArugaCyber Blog Creator deployed successfully!"
}

# Handle script interruption
trap 'log_error "Deployment interrupted. Please check your Azure resources."; exit 1' INT

# Run main function
main "$@"