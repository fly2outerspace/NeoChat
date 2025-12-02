"""SQLite repository for model records"""
from typing import Any, Dict, List, Optional
import uuid

from app.storage.settings_sqlite_base import SettingsSQLiteBase
from app.utils import get_current_time, get_real_time
from app.utils.crypto import encrypt_api_key, decrypt_api_key
from app.logger import logger


class ModelRepository(SettingsSQLiteBase):
    """Data access layer for model table"""

    def insert_model(
        self,
        name: str,
        provider: str,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        api_type: str = "openai",
        model_id: Optional[str] = None,
    ) -> str:
        """Insert a model entry
        
        Args:
            name: Model configuration name
            provider: Provider name (e.g., "OpenAI", "DeepSeek", "xAI")
            model: Model name (e.g., "gpt-4o", "deepseek-chat")
            base_url: API base URL
            api_key: API key (will be encrypted)
            max_tokens: Maximum tokens
            temperature: Temperature parameter
            api_type: API type (default: "openai")
            model_id: Optional model_id (if not provided, generates "model-{16位uuid}")
        
        Returns:
            The model_id of the inserted model
        """
        # Generate model_id if not provided: "model-{16位uuid}"
        if not model_id:
            # Generate 16 hex characters (8 bytes)
            hex_uuid = uuid.uuid4().hex[:16]
            model_id = f"model-{hex_uuid}"
        
        # Encrypt API key if provided
        encrypted_api_key = encrypt_api_key(api_key) if api_key else None
        
        timestamp = get_current_time()
        real_timestamp = get_real_time()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO model (model_id, name, provider, model, base_url, api_key, max_tokens, temperature, api_type, created_at, updated_at, real_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (model_id, name, provider, model, base_url, encrypted_api_key, max_tokens, temperature, api_type, timestamp, timestamp, real_timestamp),
            )
            return model_id

    def list_models(self) -> List[Dict[str, Any]]:
        """List all models
        
        Returns:
            List of model dicts ordered by created_at DESC
        """
        rows = self.fetch_all(
            """
            SELECT id, model_id, name, provider, model, base_url, api_key, max_tokens, temperature, api_type, created_at, updated_at
            FROM model
            ORDER BY created_at DESC
            """
        )
        # Decrypt API keys for display (but mark as encrypted in response)
        result = []
        for row in rows:
            row_dict = dict(row)
            # Don't return decrypted API key in list (security)
            # Only return a flag indicating if API key exists
            row_dict['has_api_key'] = bool(row_dict.get('api_key'))
            row_dict['api_key'] = None  # Don't expose encrypted key
            result.append(row_dict)
        return result

    def get_by_model_id(self, model_id: str, include_api_key: bool = False) -> Optional[Dict[str, Any]]:
        """Get a model by model_id
        
        Args:
            model_id: Model ID
            include_api_key: If True, decrypt and include API key (use with caution)
        
        Returns:
            Model dict if found, None otherwise
        """
        row = self.fetch_one(
            """
            SELECT id, model_id, name, provider, model, base_url, api_key, max_tokens, temperature, api_type, created_at, updated_at
            FROM model
            WHERE model_id = ?
            """,
            (model_id,),
        )
        
        if not row:
            return None
        
        row_dict = dict(row)
        
        # Decrypt API key if requested
        if include_api_key and row_dict.get('api_key'):
            try:
                row_dict['api_key'] = decrypt_api_key(row_dict['api_key'])
            except Exception as e:
                logger.error(f"Failed to decrypt API key for model {model_id}: {e}")
                row_dict['api_key'] = None
        else:
            # Don't expose encrypted key
            row_dict['has_api_key'] = bool(row_dict.get('api_key'))
            row_dict['api_key'] = None
        
        return row_dict

    def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        api_type: Optional[str] = None,
    ) -> bool:
        """Update a model by model_id
        
        Args:
            model_id: Model ID
            name: Optional new name
            provider: Optional new provider
            model: Optional new model name
            base_url: Optional new base URL
            api_key: Optional new API key (will be encrypted)
            max_tokens: Optional new max tokens
            temperature: Optional new temperature
            api_type: Optional new API type
        
        Returns:
            True if updated, False if model not found
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if provider is not None:
            updates.append("provider = ?")
            params.append(provider)
        if model is not None:
            updates.append("model = ?")
            params.append(model)
        if base_url is not None:
            updates.append("base_url = ?")
            params.append(base_url)
        if api_key is not None:
            # Encrypt API key before storing
            encrypted_api_key = encrypt_api_key(api_key) if api_key else None
            updates.append("api_key = ?")
            params.append(encrypted_api_key)
        if max_tokens is not None:
            updates.append("max_tokens = ?")
            params.append(max_tokens)
        if temperature is not None:
            updates.append("temperature = ?")
            params.append(temperature)
        if api_type is not None:
            updates.append("api_type = ?")
            params.append(api_type)
        
        if not updates:
            return False
        
        # Add updated_at timestamp
        updates.append("updated_at = ?")
        params.append(get_current_time())
        updates.append("real_updated_at = ?")
        params.append(get_real_time())
        
        params.append(model_id)
        
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE model
                SET {', '.join(updates)}
                WHERE model_id = ?
                """,
                params,
            )
            return cursor.rowcount > 0

    def delete_model(self, model_id: str) -> bool:
        """Delete a model by model_id
        
        Args:
            model_id: Model ID
        
        Returns:
            True if deleted, False if model not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM model
                WHERE model_id = ?
                """,
                (model_id,),
            )
            return cursor.rowcount > 0

    def model_exists(self, model_id: str) -> bool:
        """Check if a model exists
        
        Args:
            model_id: Model ID
        
        Returns:
            True if exists, False otherwise
        """
        row = self.fetch_one(
            """
            SELECT 1 FROM model WHERE model_id = ?
            """,
            (model_id,),
        )
        return row is not None

