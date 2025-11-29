"""
Organization-Specific Vector Store Service

Manages Qdrant collections with organization-level isolation.
Each organization has its own collection for secure multi-tenancy.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.rag.vector_store import VectorStore
from app.services.rbac_service import rbac_service, Permission, Role
from app.database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class OrgVectorStoreService:
    """
    Organization-specific vector store service
    
    Features:
    - Organization-specific collections (org_{org_id}_docs)
    - Admin can access any organization's collection
    - Users can only access their organization's collection
    - Automatic collection creation per organization
    - Secure multi-tenant isolation
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.vector_store = VectorStore(db_manager)
        self.client: Optional[QdrantClient] = None
        self.collection_prefix = "org"
        self.vector_size = 384  # all-MiniLM-L6-v2
        
    async def initialize(self):
        """Initialize vector store"""
        await self.vector_store.initialize()
        self.client = self.vector_store.client
        logger.info("Organization vector store service initialized")
    
    def _get_collection_name(self, organization_id: str, collection_type: str = "docs") -> str:
        """
        Get organization-specific collection name
        
        Args:
            organization_id: Organization ID
            collection_type: Type of collection (docs, memory, etc.)
            
        Returns:
            Collection name in format: org_{org_id}_{type}
        """
        # Sanitize org_id (remove special characters)
        safe_org_id = organization_id.replace("-", "_").replace(".", "_")
        return f"{self.collection_prefix}_{safe_org_id}_{collection_type}"
    
    def _check_access(self, user_role: str, user_org_id: str, target_org_id: str) -> bool:
        """
        Check if user can access target organization's data
        
        Args:
            user_role: User's role
            user_org_id: User's organization ID
            target_org_id: Target organization ID
            
        Returns:
            True if access is allowed
        """
        # Admin can access any organization
        if rbac_service.has_permission(user_role, Permission.READ_ALL_DATA):
            return True
        
        # Users can only access their own organization
        return user_org_id == target_org_id
    
    async def ensure_collection_exists(
        self, 
        organization_id: str,
        collection_type: str = "docs"
    ) -> str:
        """
        Ensure organization-specific collection exists
        
        Args:
            organization_id: Organization ID
            collection_type: Type of collection
            
        Returns:
            Collection name
        """
        collection_name = self._get_collection_name(organization_id, collection_type)
        
        try:
            # Check if collection exists
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if collection_name not in collection_names:
                # Create collection
                await self.vector_store.create_collection_if_not_exists(
                    collection_name=collection_name,
                    vector_size=self.vector_size,
                    distance="cosine"
                )
                
                # Create organization-specific indexes
                await self._create_org_indexes(collection_name, organization_id)
                
                logger.info(f"Created collection for organization: {collection_name}")
            
            return collection_name
            
        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise
    
    async def _create_org_indexes(self, collection_name: str, organization_id: str):
        """Create indexes for organization collection"""
        try:
            # Index for organization_id (redundant but useful for validation)
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="organization_id",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            # Index for document_id
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            # Index for document_type
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_type",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            # Index for access_level
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="access_level",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            logger.info(f"Created indexes for collection: {collection_name}")
            
        except Exception as e:
            logger.warning(f"Failed to create some indexes: {e}")
    
    async def add_document(
        self,
        organization_id: str,
        user_id: str,
        user_role: str,
        document_id: str,
        vector: List[float],
        content: str,
        metadata: Dict[str, Any],
        collection_type: str = "docs"
    ) -> str:
        """
        Add document to organization's collection
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            user_role: User's role
            document_id: Document ID
            vector: Document embedding
            content: Document content
            metadata: Document metadata
            collection_type: Collection type
            
        Returns:
            Vector ID
        """
        # Check access
        if not self._check_access(user_role, organization_id, organization_id):
            raise PermissionError(f"User does not have access to organization {organization_id}")
        
        # Ensure collection exists
        collection_name = await self.ensure_collection_exists(organization_id, collection_type)
        
        # Prepare payload with organization_id
        payload = {
            "organization_id": organization_id,
            "document_id": document_id,
            "content": content,
            "created_by": user_id,
            "created_at": datetime.utcnow().isoformat(),
            **metadata
        }
        
        # Add vector
        vector_id = await self.vector_store.add_vector(
            collection_name=collection_name,
            vector=vector,
            payload=payload,
            id=document_id
        )
        
        logger.info(f"Added document to {collection_name}: {document_id}")
        return vector_id
    
    async def search_documents(
        self,
        organization_id: str,
        user_id: str,
        user_role: str,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        additional_filters: Optional[List[Dict[str, Any]]] = None,
        collection_type: str = "docs"
    ) -> List[Dict[str, Any]]:
        """
        Search documents in organization's collection
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            user_role: User's role
            query_vector: Query embedding
            limit: Max results
            threshold: Similarity threshold
            additional_filters: Additional filters
            collection_type: Collection type
            
        Returns:
            Search results
        """
        # Check access
        if not self._check_access(user_role, organization_id, organization_id):
            raise PermissionError(f"User does not have access to organization {organization_id}")
        
        # Get collection name
        collection_name = self._get_collection_name(organization_id, collection_type)
        
        # Check if collection exists
        try:
            await self.client.get_collection(collection_name)
        except Exception:
            logger.warning(f"Collection {collection_name} does not exist, returning empty results")
            return []
        
        # Build filters - always filter by organization_id
        filters = [
            {"field": "organization_id", "value": organization_id, "operator": "=="}
        ]
        
        # Add additional filters
        if additional_filters:
            filters.extend(additional_filters)
        
        # Perform search
        results = await self.vector_store.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            threshold=threshold,
            filters=filters
        )
        
        logger.info(f"Search in {collection_name}: {len(results)} results")
        return results
    
    async def delete_document(
        self,
        organization_id: str,
        user_id: str,
        user_role: str,
        document_id: str,
        collection_type: str = "docs"
    ) -> bool:
        """
        Delete document from organization's collection
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            user_role: User's role
            document_id: Document ID
            collection_type: Collection type
            
        Returns:
            True if deleted
        """
        # Check access
        if not self._check_access(user_role, organization_id, organization_id):
            raise PermissionError(f"User does not have access to organization {organization_id}")
        
        # Check delete permission
        if not rbac_service.has_permission(user_role, Permission.DELETE_RECORDS):
            raise PermissionError("User does not have delete permission")
        
        # Get collection name
        collection_name = self._get_collection_name(organization_id, collection_type)
        
        # Delete vector
        await self.vector_store.delete_vectors(
            collection_name=collection_name,
            ids=[document_id]
        )
        
        logger.info(f"Deleted document from {collection_name}: {document_id}")
        return True
    
    async def list_organization_collections(
        self,
        user_role: str,
        user_org_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List collections (admin can see all, users see only their org)
        
        Args:
            user_role: User's role
            user_org_id: User's organization ID
            
        Returns:
            List of collections with info
        """
        # Get all collections
        collections = await self.client.get_collections()
        
        result = []
        for collection in collections.collections:
            # Only include org-prefixed collections
            if not collection.name.startswith(f"{self.collection_prefix}_"):
                continue
            
            # Extract org_id from collection name
            # Format: org_{org_id}_{type}
            parts = collection.name.split("_")
            if len(parts) < 3:
                continue
            
            collection_org_id = parts[1]
            collection_type = "_".join(parts[2:])
            
            # Check access
            if not rbac_service.has_permission(user_role, Permission.READ_ALL_DATA):
                # Non-admin users can only see their org's collections
                if user_org_id != collection_org_id:
                    continue
            
            # Get collection info
            info = await self.vector_store.get_collection_info(collection.name)
            info["organization_id"] = collection_org_id
            info["collection_type"] = collection_type
            
            result.append(info)
        
        return result
    
    async def delete_organization_collection(
        self,
        organization_id: str,
        user_role: str,
        collection_type: str = "docs"
    ) -> bool:
        """
        Delete entire organization collection (admin only)
        
        Args:
            organization_id: Organization ID
            user_role: User's role
            collection_type: Collection type
            
        Returns:
            True if deleted
        """
        # Only admin can delete collections
        if not rbac_service.has_permission(user_role, Permission.SYSTEM_COMMANDS):
            raise PermissionError("Only admins can delete collections")
        
        collection_name = self._get_collection_name(organization_id, collection_type)
        
        await self.vector_store.delete_collection(collection_name)
        
        logger.info(f"Deleted collection: {collection_name}")
        return True
    
    async def get_collection_stats(
        self,
        organization_id: str,
        user_id: str,
        user_role: str,
        collection_type: str = "docs"
    ) -> Dict[str, Any]:
        """
        Get statistics for organization's collection
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            user_role: User's role
            collection_type: Collection type
            
        Returns:
            Collection statistics
        """
        # Check access
        if not self._check_access(user_role, organization_id, organization_id):
            raise PermissionError(f"User does not have access to organization {organization_id}")
        
        collection_name = self._get_collection_name(organization_id, collection_type)
        
        try:
            info = await self.vector_store.get_collection_info(collection_name)
            return {
                "organization_id": organization_id,
                "collection_type": collection_type,
                "collection_name": collection_name,
                **info
            }
        except Exception as e:
            logger.warning(f"Collection {collection_name} does not exist: {e}")
            return {
                "organization_id": organization_id,
                "collection_type": collection_type,
                "collection_name": collection_name,
                "exists": False,
                "vectors_count": 0
            }


# Global instance
_org_vector_store_service: Optional[OrgVectorStoreService] = None


async def get_org_vector_store_service() -> OrgVectorStoreService:
    """Get or create organization vector store service instance"""
    global _org_vector_store_service
    
    if _org_vector_store_service is None:
        from app.database.connection import DatabaseManager
        db_manager = DatabaseManager()
        _org_vector_store_service = OrgVectorStoreService(db_manager)
        await _org_vector_store_service.initialize()
    
    return _org_vector_store_service
