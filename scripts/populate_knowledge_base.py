#!/usr/bin/env python3
"""
Populate Knowledge Base from Documentation

This script ingests all documentation from the docs/ folder into the RAG system.
"""

import asyncio
import sys
import os
from pathlib import Path
import logging

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database.connection import get_db_manager
from app.rag.service import RAGService
from app.rag.models import Document, DocumentType, AccessLevel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def ingest_documentation_files(rag_service: RAGService, docs_dir: Path):
    """Ingest all markdown files from docs directory"""
    
    ingested_count = 0
    failed_count = 0
    
    # Find all markdown files
    md_files = list(docs_dir.glob("**/*.md"))
    
    logger.info(f"Found {len(md_files)} documentation files to ingest")
    
    for md_file in md_files:
        try:
            # Read file content
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                logger.warning(f"Skipping empty file: {md_file.name}")
                continue
            
            # Determine document type from filename
            filename = md_file.stem.lower()
            if 'api' in filename or 'endpoint' in filename:
                doc_type = DocumentType.DOCUMENT
            elif 'guide' in filename or 'tutorial' in filename:
                doc_type = DocumentType.MANUAL
            elif 'architecture' in filename or 'technical' in filename:
                doc_type = DocumentType.DOCUMENT
            elif 'readme' in filename:
                doc_type = DocumentType.DOCUMENT
            elif 'faq' in filename:
                doc_type = DocumentType.FAQ
            elif 'policy' in filename:
                doc_type = DocumentType.POLICY
            else:
                doc_type = DocumentType.KNOWLEDGE_BASE
            
            # Create document
            document = Document(
                title=md_file.stem.replace('_', ' ').replace('-', ' ').title(),
                content=content,
                document_type=doc_type,
                metadata={
                    "source": "documentation",
                    "filename": md_file.name,
                    "path": str(md_file.relative_to(docs_dir.parent)),
                    "category": "erp_documentation"
                },
                access_level=AccessLevel.INTERNAL,
                version="1.0"
            )
            
            # Ingest document
            success, doc_id, vector_ids = await rag_service.ingest_document(document)
            
            if success:
                ingested_count += 1
                logger.info(
                    f"✓ Ingested: {md_file.name} "
                    f"(ID: {doc_id}, Vectors: {len(vector_ids) if vector_ids else 0})"
                )
            else:
                failed_count += 1
                logger.error(f"✗ Failed to ingest: {md_file.name}")
                
        except Exception as e:
            failed_count += 1
            logger.error(f"✗ Error ingesting {md_file.name}: {e}")
    
    return ingested_count, failed_count


async def main():
    """Main function to populate knowledge base"""
    try:
        logger.info("="*60)
        logger.info("KNOWLEDGE BASE POPULATION SCRIPT")
        logger.info("="*60)
        
        # Initialize database manager
        logger.info("Initializing database connections...")
        db_manager = await get_db_manager()
        
        # Initialize RAG service
        logger.info("Initializing RAG service...")
        rag_service = RAGService(db_manager)
        await rag_service.initialize()
        
        # Get docs directory
        docs_dir = Path(__file__).parent.parent / "docs"
        
        if not docs_dir.exists():
            logger.error(f"Documentation directory not found: {docs_dir}")
            sys.exit(1)
        
        logger.info(f"Documentation directory: {docs_dir}")
        
        # Ingest documentation
        logger.info("\nIngesting documentation files...")
        ingested, failed = await ingest_documentation_files(rag_service, docs_dir)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("INGESTION SUMMARY")
        logger.info("="*60)
        logger.info(f"Successfully ingested: {ingested} documents")
        logger.info(f"Failed: {failed} documents")
        logger.info(f"Total processed: {ingested + failed} documents")
        logger.info("="*60)
        
        # Test search
        logger.info("\nTesting knowledge base search...")
        from app.rag.models import SearchQuery
        
        test_queries = [
            "What is the ERP architecture?",
            "How does authentication work?",
            "What are the microservices?",
            "API documentation"
        ]
        
        for query in test_queries:
            search_query = SearchQuery(
                query=query,
                max_results=3,
                similarity_threshold=0.5
            )
            results = await rag_service.search(search_query)
            
            if isinstance(results, list):
                result_count = len(results)
            elif hasattr(results, 'results'):
                result_count = len(results.results)
            else:
                result_count = 0
            
            logger.info(f"  Query: '{query}' -> {result_count} results")
        
        logger.info("\n✓ Knowledge base population completed successfully!")
        
    except Exception as e:
        logger.error(f"✗ Knowledge base population failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
