import logging
import json
import os
from datetime import datetime
import azure.functions as func
from azure.storage.blob import BlobServiceClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('ClearArticles function called')
    
    # Check authorization header
    auth_header = req.headers.get('Code')
    if auth_header != 'xxx':
        logging.warning('Unauthorized access attempt to ClearArticles')
        return func.HttpResponse(
            json.dumps({
                'error': 'Unauthorized',
                'message': 'Valid Code header required'
            }),
            status_code=401,
            mimetype="application/json"
        )
    
    try:
        # Get blob client
        blob_service = BlobServiceClient.from_connection_string(
            os.environ['AzureWebJobsStorage']
        )
        container_client = blob_service.get_container_client('articles')
        
        # Count articles before deletion
        article_count = 0
        deleted_count = 0
        
        try:
            # List all blobs in the articles container
            blobs_to_delete = []
            for blob in container_client.list_blobs():
                if blob.name.endswith('.html'):
                    blobs_to_delete.append(blob.name)
                    article_count += 1
            
            # Delete each article
            for blob_name in blobs_to_delete:
                try:
                    blob_client = container_client.get_blob_client(blob_name)
                    blob_client.delete_blob()
                    deleted_count += 1
                    logging.info(f"Deleted: {blob_name}")
                except Exception as e:
                    logging.error(f"Failed to delete {blob_name}: {e}")
                    
        except Exception as e:
            logging.error(f"Error listing blobs: {e}")
            return func.HttpResponse(
                json.dumps({'error': f'Failed to access articles: {str(e)}'}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Return success response
        return func.HttpResponse(
            json.dumps({
                'message': 'Articles cleared successfully',
                'total_found': article_count,
                'deleted': deleted_count,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"ClearArticles failed: {e}")
        return func.HttpResponse(
            json.dumps({
                'error': f'Failed to clear articles: {str(e)}',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }),
            status_code=500,
            mimetype="application/json"
        )