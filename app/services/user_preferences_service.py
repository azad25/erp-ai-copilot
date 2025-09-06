"""
User Preferences and Caching Service

Manages user preferences, settings, and caching for personalized AI Copilot experience.
"""

from typing import Dict, List, Any, Optional, Union
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings
from app.database.connection import get_mongodb, get_redis

logger = logging.getLogger(__name__)


class PreferenceCategory(Enum):
    """Preference categories"""
    GENERAL = "general"
    AI_BEHAVIOR = "ai_behavior"
    UI_SETTINGS = "ui_settings"
    NOTIFICATIONS = "notifications"
    PRIVACY = "privacy"
    INTEGRATIONS = "integrations"


@dataclass
class UserPreference:
    """User preference structure"""
    preference_id: str
    user_id: str
    organization_id: str
    category: PreferenceCategory
    key: str
    value: Any
    data_type: str
    description: str = ""
    is_encrypted: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class UserPreferencesService:
    """
    User Preferences and Caching Service
    
    Features:
    - User preference management with categories
    - Redis caching for fast access
    - MongoDB persistence for durability
    - Preference validation and type checking
    - Bulk preference operations
    - Preference history and versioning
    - Organization-level default preferences
    """
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.default_preferences = self._initialize_default_preferences()
        
    def _initialize_default_preferences(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default preferences for new users"""
        return {
            PreferenceCategory.GENERAL.value: {
                "language": {"value": "en", "type": "string", "description": "User interface language"},
                "timezone": {"value": "UTC", "type": "string", "description": "User timezone"},
                "date_format": {"value": "YYYY-MM-DD", "type": "string", "description": "Preferred date format"},
                "time_format": {"value": "24h", "type": "string", "description": "Preferred time format"}
            },
            PreferenceCategory.AI_BEHAVIOR.value: {
                "response_style": {"value": "professional", "type": "string", "description": "AI response style"},
                "detail_level": {"value": "medium", "type": "string", "description": "Level of detail in responses"},
                "proactive_suggestions": {"value": True, "type": "boolean", "description": "Enable proactive AI suggestions"},
                "reasoning_display": {"value": True, "type": "boolean", "description": "Show AI reasoning steps"},
                "auto_context": {"value": True, "type": "boolean", "description": "Automatically include context in conversations"},
                "memory_retention": {"value": "30d", "type": "string", "description": "How long to retain conversation memory"}
            },
            PreferenceCategory.UI_SETTINGS.value: {
                "theme": {"value": "light", "type": "string", "description": "UI theme preference"},
                "sidebar_collapsed": {"value": False, "type": "boolean", "description": "Sidebar collapsed by default"},
                "chat_bubble_style": {"value": "modern", "type": "string", "description": "Chat bubble appearance"},
                "font_size": {"value": "medium", "type": "string", "description": "UI font size"},
                "animations_enabled": {"value": True, "type": "boolean", "description": "Enable UI animations"}
            },
            PreferenceCategory.NOTIFICATIONS.value: {
                "email_notifications": {"value": True, "type": "boolean", "description": "Enable email notifications"},
                "push_notifications": {"value": True, "type": "boolean", "description": "Enable push notifications"},
                "ai_insights_alerts": {"value": True, "type": "boolean", "description": "AI insights notifications"},
                "system_alerts": {"value": True, "type": "boolean", "description": "System status alerts"},
                "notification_frequency": {"value": "immediate", "type": "string", "description": "Notification frequency"}
            },
            PreferenceCategory.PRIVACY.value: {
                "data_retention": {"value": "1y", "type": "string", "description": "Personal data retention period"},
                "analytics_tracking": {"value": True, "type": "boolean", "description": "Allow analytics tracking"},
                "conversation_logging": {"value": True, "type": "boolean", "description": "Log conversations for improvement"},
                "share_usage_data": {"value": False, "type": "boolean", "description": "Share anonymous usage data"}
            },
            PreferenceCategory.INTEGRATIONS.value: {
                "third_party_apis": {"value": [], "type": "list", "description": "Enabled third-party API integrations"},
                "webhook_endpoints": {"value": [], "type": "list", "description": "User webhook endpoints"},
                "external_tools": {"value": [], "type": "list", "description": "Enabled external tools"},
                "api_rate_limits": {"value": {"default": 1000}, "type": "dict", "description": "API rate limits per service"}
            }
        }
    
    async def get_user_preference(
        self,
        user_id: str,
        organization_id: str,
        category: Union[str, PreferenceCategory],
        key: str
    ) -> Optional[Any]:
        """Get a specific user preference"""
        category_str = category.value if isinstance(category, PreferenceCategory) else category
        
        # Try cache first
        cache_key = f"user_pref:{user_id}:{organization_id}:{category_str}:{key}"
        redis = await get_redis()
        
        cached_value = await redis.get(cache_key)
        if cached_value:
            try:
                return json.loads(cached_value)
            except json.JSONDecodeError:
                return cached_value
        
        # Get from database
        mongodb = await get_mongodb()
        
        pref_doc = await mongodb.user_preferences.find_one({
            "user_id": user_id,
            "organization_id": organization_id,
            "category": category_str,
            "key": key
        })
        
        if pref_doc:
            value = pref_doc["value"]
            # Cache the result
            await redis.set(cache_key, json.dumps(value), ex=self.cache_ttl)
            return value
        
        # Return default if not found
        default_value = self._get_default_preference(category_str, key)
        if default_value is not None:
            # Store default preference
            await self.set_user_preference(user_id, organization_id, category, key, default_value)
            return default_value
        
        return None
    
    async def set_user_preference(
        self,
        user_id: str,
        organization_id: str,
        category: Union[str, PreferenceCategory],
        key: str,
        value: Any,
        description: str = ""
    ) -> bool:
        """Set a user preference"""
        category_str = category.value if isinstance(category, PreferenceCategory) else category
        
        try:
            # Validate preference
            if not self._validate_preference(category_str, key, value):
                logger.warning(f"Invalid preference value: {category_str}.{key} = {value}")
                return False
            
            mongodb = await get_mongodb()
            redis = await get_redis()
            
            now = datetime.utcnow()
            
            # Update or insert preference
            pref_doc = {
                "user_id": user_id,
                "organization_id": organization_id,
                "category": category_str,
                "key": key,
                "value": value,
                "data_type": type(value).__name__,
                "description": description,
                "updated_at": now
            }
            
            result = await mongodb.user_preferences.update_one(
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "category": category_str,
                    "key": key
                },
                {"$set": pref_doc, "$setOnInsert": {"created_at": now}},
                upsert=True
            )
            
            # Update cache
            cache_key = f"user_pref:{user_id}:{organization_id}:{category_str}:{key}"
            await redis.set(cache_key, json.dumps(value), ex=self.cache_ttl)
            
            # Invalidate user preferences cache
            user_cache_key = f"user_prefs:{user_id}:{organization_id}"
            await redis.delete(user_cache_key)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set preference: {e}")
            return False
    
    async def get_user_preferences(
        self,
        user_id: str,
        organization_id: str,
        category: Optional[Union[str, PreferenceCategory]] = None
    ) -> Dict[str, Any]:
        """Get all user preferences or preferences for a specific category"""
        category_str = category.value if isinstance(category, PreferenceCategory) else category
        
        # Try cache first
        cache_key = f"user_prefs:{user_id}:{organization_id}"
        if category_str:
            cache_key += f":{category_str}"
        
        redis = await get_redis()
        cached_prefs = await redis.get(cache_key)
        
        if cached_prefs:
            return json.loads(cached_prefs)
        
        # Get from database
        mongodb = await get_mongodb()
        
        query = {
            "user_id": user_id,
            "organization_id": organization_id
        }
        if category_str:
            query["category"] = category_str
        
        cursor = mongodb.user_preferences.find(query)
        
        preferences = {}
        async for pref_doc in cursor:
            cat = pref_doc["category"]
            key = pref_doc["key"]
            value = pref_doc["value"]
            
            if cat not in preferences:
                preferences[cat] = {}
            preferences[cat][key] = value
        
        # Add missing defaults
        if not category_str:
            for cat, defaults in self.default_preferences.items():
                if cat not in preferences:
                    preferences[cat] = {}
                for key, default_config in defaults.items():
                    if key not in preferences[cat]:
                        preferences[cat][key] = default_config["value"]
        
        # Cache result
        await redis.set(cache_key, json.dumps(preferences), ex=self.cache_ttl)
        
        return preferences
    
    async def delete_user_preference(
        self,
        user_id: str,
        organization_id: str,
        category: Union[str, PreferenceCategory],
        key: str
    ) -> bool:
        """Delete a user preference"""
        category_str = category.value if isinstance(category, PreferenceCategory) else category
        
        try:
            mongodb = await get_mongodb()
            redis = await get_redis()
            
            # Delete from database
            result = await mongodb.user_preferences.delete_one({
                "user_id": user_id,
                "organization_id": organization_id,
                "category": category_str,
                "key": key
            })
            
            # Remove from cache
            cache_key = f"user_pref:{user_id}:{organization_id}:{category_str}:{key}"
            await redis.delete(cache_key)
            
            # Invalidate user preferences cache
            user_cache_key = f"user_prefs:{user_id}:{organization_id}"
            await redis.delete(user_cache_key)
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete preference: {e}")
            return False
    
    async def bulk_set_preferences(
        self,
        user_id: str,
        organization_id: str,
        preferences: Dict[str, Dict[str, Any]]
    ) -> bool:
        """Set multiple preferences in bulk"""
        try:
            mongodb = await get_mongodb()
            redis = await get_redis()
            
            operations = []
            now = datetime.utcnow()
            
            for category, prefs in preferences.items():
                for key, value in prefs.items():
                    if self._validate_preference(category, key, value):
                        pref_doc = {
                            "user_id": user_id,
                            "organization_id": organization_id,
                            "category": category,
                            "key": key,
                            "value": value,
                            "data_type": type(value).__name__,
                            "updated_at": now
                        }
                        
                        operations.append({
                            "updateOne": {
                                "filter": {
                                    "user_id": user_id,
                                    "organization_id": organization_id,
                                    "category": category,
                                    "key": key
                                },
                                "update": {
                                    "$set": pref_doc,
                                    "$setOnInsert": {"created_at": now}
                                },
                                "upsert": True
                            }
                        })
            
            if operations:
                await mongodb.user_preferences.bulk_write(operations)
            
            # Clear cache
            cache_patterns = [
                f"user_pref:{user_id}:{organization_id}:*",
                f"user_prefs:{user_id}:{organization_id}*"
            ]
            
            for pattern in cache_patterns:
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to bulk set preferences: {e}")
            return False
    
    def _validate_preference(self, category: str, key: str, value: Any) -> bool:
        """Validate preference value"""
        # Get expected type from defaults
        default_config = self.default_preferences.get(category, {}).get(key)
        if not default_config:
            return True  # Allow custom preferences
        
        expected_type = default_config["type"]
        
        # Type validation
        if expected_type == "string" and not isinstance(value, str):
            return False
        elif expected_type == "boolean" and not isinstance(value, bool):
            return False
        elif expected_type == "number" and not isinstance(value, (int, float)):
            return False
        elif expected_type == "list" and not isinstance(value, list):
            return False
        elif expected_type == "dict" and not isinstance(value, dict):
            return False
        
        # Value-specific validation
        if key == "language" and value not in ["en", "es", "fr", "de", "zh", "ja"]:
            return False
        elif key == "theme" and value not in ["light", "dark", "auto"]:
            return False
        elif key == "response_style" and value not in ["professional", "casual", "technical", "friendly"]:
            return False
        elif key == "detail_level" and value not in ["low", "medium", "high"]:
            return False
        
        return True
    
    def _get_default_preference(self, category: str, key: str) -> Optional[Any]:
        """Get default preference value"""
        default_config = self.default_preferences.get(category, {}).get(key)
        return default_config["value"] if default_config else None
    
    async def get_ai_behavior_preferences(
        self,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """Get AI behavior preferences for customizing responses"""
        prefs = await self.get_user_preferences(
            user_id,
            organization_id,
            PreferenceCategory.AI_BEHAVIOR
        )
        
        return prefs.get(PreferenceCategory.AI_BEHAVIOR.value, {})
    
    async def get_ui_preferences(
        self,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """Get UI preferences for frontend customization"""
        prefs = await self.get_user_preferences(
            user_id,
            organization_id,
            PreferenceCategory.UI_SETTINGS
        )
        
        return prefs.get(PreferenceCategory.UI_SETTINGS.value, {})
    
    async def update_last_activity(
        self,
        user_id: str,
        organization_id: str,
        activity_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update user's last activity for analytics"""
        try:
            mongodb = await get_mongodb()
            redis = await get_redis()
            
            now = datetime.utcnow()
            
            # Store in MongoDB for persistence
            activity_doc = {
                "user_id": user_id,
                "organization_id": organization_id,
                "activity_type": activity_type,
                "metadata": metadata or {},
                "timestamp": now
            }
            
            await mongodb.user_activities.insert_one(activity_doc)
            
            # Update Redis cache
            activity_key = f"user_activity:{user_id}:{organization_id}"
            await redis.hset(activity_key, mapping={
                "last_activity": now.isoformat(),
                "activity_type": activity_type,
                "metadata": json.dumps(metadata or {})
            })
            await redis.expire(activity_key, 86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Failed to update user activity: {e}")
    
    async def get_user_analytics(
        self,
        user_id: str,
        organization_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user analytics and usage patterns"""
        try:
            mongodb = await get_mongodb()
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Aggregate user activities
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "organization_id": organization_id,
                        "timestamp": {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": "$activity_type",
                        "count": {"$sum": 1},
                        "last_activity": {"$max": "$timestamp"}
                    }
                }
            ]
            
            cursor = mongodb.user_activities.aggregate(pipeline)
            activities = {}
            
            async for doc in cursor:
                activities[doc["_id"]] = {
                    "count": doc["count"],
                    "last_activity": doc["last_activity"].isoformat()
                }
            
            # Get conversation statistics
            conv_stats = await mongodb.conversations.aggregate([
                {
                    "$match": {
                        "user_id": user_id,
                        "organization_id": organization_id,
                        "created_at": {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_conversations": {"$sum": 1},
                        "avg_message_count": {"$avg": "$message_count"}
                    }
                }
            ]).to_list(1)
            
            conversation_stats = conv_stats[0] if conv_stats else {
                "total_conversations": 0,
                "avg_message_count": 0
            }
            
            return {
                "activities": activities,
                "conversations": conversation_stats,
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get user analytics: {e}")
            return {}
    
    async def export_user_preferences(
        self,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """Export all user preferences for backup/migration"""
        preferences = await self.get_user_preferences(user_id, organization_id)
        
        return {
            "user_id": user_id,
            "organization_id": organization_id,
            "preferences": preferences,
            "exported_at": datetime.utcnow().isoformat(),
            "version": "1.0"
        }
    
    async def import_user_preferences(
        self,
        user_id: str,
        organization_id: str,
        preferences_data: Dict[str, Any]
    ) -> bool:
        """Import user preferences from backup"""
        try:
            preferences = preferences_data.get("preferences", {})
            return await self.bulk_set_preferences(user_id, organization_id, preferences)
            
        except Exception as e:
            logger.error(f"Failed to import preferences: {e}")
            return False
    
    async def clear_user_cache(self, user_id: str, organization_id: str):
        """Clear all cached data for a user"""
        try:
            redis = await get_redis()
            
            cache_patterns = [
                f"user_pref:{user_id}:{organization_id}:*",
                f"user_prefs:{user_id}:{organization_id}*",
                f"user_activity:{user_id}:{organization_id}",
                f"user_context:{user_id}:{organization_id}:*"
            ]
            
            for pattern in cache_patterns:
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
            
            logger.info(f"Cleared cache for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear user cache: {e}")


# Global user preferences service instance
user_preferences_service = UserPreferencesService()
