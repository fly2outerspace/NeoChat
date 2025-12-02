"""Integrated Meilisearch service combining manager and client"""
import os
import subprocess
import time
import signal
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
from meilisearch import Client
from meilisearch.errors import MeilisearchError

from app.logger import logger


class MeilisearchService:
    """
    Integrated Meilisearch service combining process management and client functionality.
    Singleton pattern - only one instance exists.
    """
    
    DEFAULT_INDEX = "messages"
    PERIOD_INDEX = "periods"
    KV_INDEX = "kv"
    _INDEX_SETTINGS: Dict[str, Dict[str, Any]] = {
        DEFAULT_INDEX: {
            "searchableAttributes": [
                "content",
                "role",
                "session_id",
                "tool_name",
                "speaker"
            ],
            "filterableAttributes": [
                "session_id",
                "role",
                "category",
                "created_at",
                "tool_name",
                "speaker",
                "character_ids"
            ],
            "sortableAttributes": [
                "created_at",
                "id"
            ],
            "displayedAttributes": [
                "id",
                "session_id",
                "role",
                "content",
                "tool_name",
                "speaker",
                "tool_call_id",
                "created_at",
                "category",
                "character_ids"
            ],
            "rankingRules": [
                "exactness",
                "words",
                "typo",
                "proximity",
                "attribute",
                "sort"
            ],
            "stopWords": [],
            "synonyms": {},
            "distinctAttribute": None,
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 2,
                    "twoTypos": 4
                },
                "disableOnWords": [],
                "disableOnAttributes": []
            }
        },
        PERIOD_INDEX: {
            "searchableAttributes": ["content", "title"],
            "filterableAttributes": [
                "session_id",
                "period_id",
                "period_type",
                "character_id",
            ],
            "sortableAttributes": ["start_at", "end_at", "created_at"],
            "displayedAttributes": [
                "id",
                "period_id",
                "period_type",
                "session_id",
                "content",
                "title",
                "start_at",
                "end_at",
                "character_id",
                "created_at"
            ],
            "rankingRules": [
                "words",
                "typo",
                "proximity",
                "attribute",
                "exactness",
                "sort"
            ],
            "stopWords": [],
            "synonyms": {},
            "distinctAttribute": None,
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 2,
                    "twoTypos": 4
                },
                "disableOnWords": [],
                "disableOnAttributes": []
            },
        },
        KV_INDEX: {
            "searchableAttributes": ["key", "metadata"],
            "filterableAttributes": [
                "session_id",
                "key",
                "key_type",
                "character_id",
            ],
            "sortableAttributes": ["created_at", "updated_at"],
            "displayedAttributes": [
                "id",
                "session_id",
                "key",
                "key_type",
                "metadata",
                "character_id",
                "created_at",
                "updated_at"
            ],
            "rankingRules": [
                "words",
                "typo",
                "proximity",
                "attribute",
                "exactness",
                "sort"
            ],
            "stopWords": [],
            "synonyms": {},
            "distinctAttribute": None,
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 2,
                    "twoTypos": 4
                },
                "disableOnWords": [],
                "disableOnAttributes": []
            },
        },
    }
    _instance: Optional["MeilisearchService"] = None
    _initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern - only one instance exists"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Meilisearch service (only called once)"""
        if self._initialized:
            return
        
        # Process management attributes
        self.executable_path: Optional[Path] = None
        self.db_path: Optional[Path] = None
        self.http_addr: str = "127.0.0.1:7700"
        self.process: Optional[subprocess.Popen] = None
        self.base_url: str = "http://127.0.0.1:7700"
        
        # Client attributes
        self._client: Optional[Client] = None
        self._index_name: str = self.DEFAULT_INDEX
        self._api_key: Optional[str] = None
        
        self._initialized = True
    
    def initialize(
        self,
        executable_path: Optional[str] = None,
        db_path: Optional[str] = None,
        http_addr: str = "127.0.0.1:7700",
        api_key: Optional[str] = None,
        auto_connect: bool = True
    ) -> bool:
        """
        Initialize Meilisearch service with configuration
        
        Args:
            executable_path: Path to meilisearch.exe (for process management)
            db_path: Database path for data persistence
            http_addr: HTTP address to bind (default: 127.0.0.1:7700)
            api_key: Optional API key for Meilisearch
            auto_connect: Whether to automatically connect to Meilisearch (default: True)
        
        Returns:
            True if initialized successfully, False otherwise
        """
        try:
            # Set process management attributes
            if executable_path:
                self.executable_path = Path(executable_path)
                if not self.executable_path.exists():
                    logger.warning(f"Meilisearch executable not found: {self.executable_path}")
                    self.executable_path = None
                else:
                    # Create db directory if specified
                    if db_path:
                        self.db_path = Path(db_path)
                        self.db_path.mkdir(parents=True, exist_ok=True)
            
            self.http_addr = http_addr
            self.base_url = f"http://{http_addr}"
            self._api_key = api_key or os.getenv("MEILISEARCH_API_KEY", None)
            
            # Connect to Meilisearch if auto_connect
            if auto_connect:
                return self._connect()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Meilisearch service: {e}", exc_info=True)
            return False
    
    def _connect(self) -> bool:
        """Connect to Meilisearch service"""
        try:
            if self._api_key:
                self._client = Client(self.base_url, self._api_key)
            else:
                self._client = Client(self.base_url)
            
            # Test connection
            self._client.health()
            
            # Initialize indexes
            self._init_index(self._index_name)
            self._init_index(self.PERIOD_INDEX)
            self._init_index(self.KV_INDEX)
            return True
            
        except Exception as e:
            logger.warning(f"Failed to connect to Meilisearch: {e}. Search functionality will be disabled.")
            self._client = None
            return False
    
    def start(self, wait_for_ready: bool = True, timeout: int = 30) -> bool:
        """
        Start Meilisearch process
        
        Args:
            wait_for_ready: Wait for Meilisearch to be ready (default: True)
            timeout: Timeout in seconds for waiting (default: 30)
        
        Returns:
            True if started successfully, False otherwise
        """
        if not self.executable_path:
            logger.error("Cannot start Meilisearch: executable_path not configured")
            return False
        
        if self.is_running():
            logger.info("Meilisearch is already running")
            # Try to connect if not already connected
            if not self._client:
                return self._connect()
            return True
        
        try:
            # Build command
            cmd = [str(self.executable_path)]
            
            if self.db_path:
                cmd.extend(["--db-path", str(self.db_path)])
            
            cmd.extend(["--http-addr", self.http_addr])
            
            # Start process
            # NOTE:
            # We DO NOT use subprocess.PIPE for stdout/stderr here.
            # Capturing long-running service logs into PIPE without reading
            # can fill the pipe buffer and block the Meilisearch process,
            # which would make HTTP requests (including /documents writes)
            # hang indefinitely.
            #
            # Instead, we discard output to avoid deadlocks. If you need logs,
            # prefer configuring Meilisearch to log to files directly.
            popen_kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if os.name == 'nt':
                # Windows: hide console window
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            
            self.process = subprocess.Popen(cmd, **popen_kwargs)
            
            if wait_for_ready:
                if self._wait_for_ready(timeout):
                    # Connect to the started service
                    return self._connect()
                else:
                    logger.error("Meilisearch failed to become ready within timeout")
                    self.stop()
                    return False
            else:
                return True
                
        except Exception as e:
            logger.error(f"Failed to start Meilisearch: {e}")
            self.process = None
            return False
    
    def stop(self) -> bool:
        """
        Stop Meilisearch process
        
        Returns:
            True if stopped successfully, False otherwise
        """
        # Clean up terminated process first
        self._cleanup_terminated_process()
        
        # If no process reference, check if service is still running
        if not self.process:
            # Check if service is still responding (might be started externally)
            try:
                response = requests.get(f"{self.base_url}/health", timeout=2)
                if response.status_code == 200:
                    logger.warning("Meilisearch process reference is None but service is still responding. "
                                 "It may have been started externally or process reference was lost.")
                    # Disconnect client but can't stop external process
                    self._client = None
                    return True
            except Exception:
                # Service is not responding, already stopped
                self._client = None
                return True
        
        try:
            logger.info("Stopping Meilisearch...")
            
            # Disconnect client first
            self._client = None
            
            # Check if process is still alive before trying to stop
            if self.process.poll() is not None:
                # Process already terminated
                logger.info("Meilisearch process already terminated")
                self.process = None
                return True
            
            # Try graceful shutdown
            if os.name == 'nt':
                # Windows
                self.process.terminate()
            else:
                # Unix
                self.process.send_signal(signal.SIGTERM)
            
            # Wait for process to terminate
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                logger.warning("Meilisearch didn't terminate gracefully, forcing kill")
                self.process.kill()
                self.process.wait()
            
            self.process = None
            logger.info("Meilisearch stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop Meilisearch: {e}", exc_info=True)
            # Clean up process reference on error
            self.process = None
            return False
    
    def _cleanup_terminated_process(self):
        """Clean up terminated process reference"""
        if self.process and self.process.poll() is not None:
            # Process has terminated
            logger.info("Cleaning up terminated Meilisearch process reference")
            self.process = None
    
    def is_running(self) -> bool:
        """
        Check if Meilisearch process is running
        
        Returns:
            True if running, False otherwise
        """
        # Clean up terminated process first
        self._cleanup_terminated_process()
        
        # Check if we have a process reference
        if self.process:
            # Process is still alive (poll() returns None means still running)
            return True
        
        # Check if service is actually responding (might be started externally)
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def _wait_for_ready(self, timeout: int = 30) -> bool:
        """
        Wait for Meilisearch to become ready
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            True if ready, False if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/health", timeout=1)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            
            # Check if process is still alive
            if self.process:
                if self.process.poll() is not None:
                    logger.error("Meilisearch process terminated unexpectedly")
                    self._cleanup_terminated_process()
                    return False
            
            time.sleep(0.5)
        
        return False
    
    def _request_with_timeout(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        timeout: float = 5.0,
    ) -> Any:
        """Low-level HTTP request helper with timeout"""
        url = f"{self.base_url.rstrip('/')}{path}"
        
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["X-Meili-API-Key"] = self._api_key
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    
    def _init_index(self, index_name: str):
        """Initialize Meilisearch index with proper settings"""
        if not self._client:
            return
        
        settings = self._INDEX_SETTINGS.get(index_name)
        if not settings:
            return
        
        try:
            index = self._client.index(index_name)
            
            # Note: Primary key is set via URL parameter in add_documents() on first write
            # This is the recommended way for Meilisearch
            
            # Configure index settings for Chinese and English search
            try:
                index.update_settings(settings)
            except Exception:
                # Settings might already be configured, ignore
                pass
        except MeilisearchError as e:
            logger.error(f"Failed to initialize Meilisearch index: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing index: {e}", exc_info=True)
            raise
    
    # Client methods
    @property
    def client(self) -> Optional[Client]:
        """Get Meilisearch client instance"""
        return self._client
    
    @property
    def is_available(self) -> bool:
        """
        Check if Meilisearch is available
        """
        return self._client is not None
    
    def get_index(self, index_name: Optional[str] = None):
        """Get Meilisearch index"""
        if not self._client:
            return None
        name = index_name or self._index_name
        return self._client.index(name)
    
    def add_document(
        self,
        document: Dict[str, Any],
        index_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 5.0,
    ) -> bool:
        """Add or update a single document (reuse add_documents)"""
        return self.add_documents(
            [document],
            index_name=index_name,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
        )
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        index_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
    ) -> bool:
        """
        Add or update multiple documents with HTTP timeout and retry.
        
        Args:
            documents: List of documents to add.
            max_retries: Maximum number of retry attempts (default: 3).
            retry_delay: Delay in seconds between retries (default: 1.0).
            timeout: HTTP timeout in seconds for each attempt (default: 5.0).
        
        Returns:
            True if successful, False otherwise.
        """
        if not documents:
            return False
        
        if not self._client:
            logger.warning("Meilisearch client is not available, skipping add_documents")
            return False
        
        target_index = index_name or self._index_name
        # For periods and kv, explicitly set primary key on first write
        # Note: primaryKey parameter only works when index is empty (first write)
        # For existing indexes, primary key should already be set
        primary_key_param = ""
        if target_index == self.PERIOD_INDEX or target_index == self.KV_INDEX:
            # Always try to set primary key via URL parameter
            # Meilisearch will ignore it if index already exists and has primary key set
            primary_key_param = "?primaryKey=id"
        
        path = f"/indexes/{target_index}/documents{primary_key_param}"
        last_exception: Optional[Exception] = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    f"Adding {len(documents)} documents to Meilisearch "
                    f"(attempt {attempt}/{max_retries}, timeout={timeout}s)"
                )
                
                self._request_with_timeout(
                    method="POST",
                    path=path,
                    json_data=documents,
                    timeout=timeout,
                )
                
                if attempt > 1:
                    logger.debug(
                        f"Successfully added documents to Meilisearch after {attempt} attempts"
                    )
                return True
            
            except requests.Timeout as e:
                last_exception = e
                logger.warning(
                    f"add_documents HTTP request timed out after {timeout}s "
                    f"(attempt {attempt}/{max_retries})"
                )
                if attempt < max_retries:
                    logger.warning(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to add documents after {max_retries} attempts due to timeout: {e}"
                    )
            
            except requests.RequestException as e:
                last_exception = e
                status = getattr(e.response, "status_code", None)
                logger.warning(
                    f"HTTP error while adding documents to Meilisearch "
                    f"(attempt {attempt}/{max_retries}, status={status}): {e}"
                )
                
                if attempt < max_retries:
                    logger.warning(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to add documents to Meilisearch after {max_retries} attempts: {e}"
                    )
            
            except Exception as e:
                last_exception = e
                logger.error(
                    f"Unexpected error while adding documents to Meilisearch "
                    f"(attempt {attempt}/{max_retries}): {e}",
                    exc_info=True,
                )
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to add documents to Meilisearch after {max_retries} attempts: {e}"
                    )
        
        return False
    
    def delete_document(self, document_id: Any, index_name: Optional[str] = None) -> bool:
        """Delete a document by ID"""
        if not self._client:
            return False
        
        try:
            index = self.get_index(index_name)
            index.delete_document(document_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from Meilisearch: {e}")
            return False
    
    def delete_documents(self, document_ids: List[Any], index_name: Optional[str] = None) -> bool:
        """Delete multiple documents by IDs"""
        if not self._client or not document_ids:
            return False
        
        try:
            index = self.get_index(index_name)
            index.delete_documents(document_ids)
            return True
        except Exception as e:
            logger.error(f"Failed to delete documents from Meilisearch: {e}")
            return False
    
    def delete_by_session(self, session_id: str, index_name: Optional[str] = None) -> bool:
        """Delete all documents for a session"""
        if not self._client:
            return False
        
        try:
            target_index = index_name or self._index_name
            # Python client may not yet expose delete-by-filter helper; call HTTP API directly
            self._request_with_timeout(
                method="POST",
                path=f"/indexes/{target_index}/documents/delete",
                json_data={"filter": f'session_id = \"{session_id}\"'},
                timeout=10.0,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete documents by session from Meilisearch: {e}")
            return False
    
    def clear_all_documents(self, index_name: Optional[str] = None) -> bool:
        """Clear all documents from an index or all indexes
        
        Args:
            index_name: Index name to clear, or None to clear all indexes (messages, periods, kv)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            logger.warning("Meilisearch client is not available, skipping clear_all_documents")
            return False
        
        try:
            if index_name is None:
                # Clear all indexes
                indexes_to_clear = [self._index_name, self.PERIOD_INDEX, self.KV_INDEX]
                for target_index in indexes_to_clear:
                    try:
                        self._request_with_timeout(
                            method="DELETE",
                            path=f"/indexes/{target_index}/documents",
                            timeout=30.0,
                        )
                        logger.info(f"Cleared all documents from index: {target_index}")
                    except Exception as e:
                        logger.warning(f"Failed to clear index {target_index}: {e}")
                return True
            else:
                # Clear specific index
                target_index = index_name
                self._request_with_timeout(
                    method="DELETE",
                    path=f"/indexes/{target_index}/documents",
                    timeout=30.0,
                )
                logger.info(f"Cleared all documents from index: {target_index}")
                return True
        except Exception as e:
            logger.error(f"Failed to clear all documents from Meilisearch: {e}")
            return False
    
    def refresh_from_database(self, db_path) -> bool:
        """Refresh Meilisearch index from a database file
        
        Reads all data from the specified database file and re-indexes it.
        
        Args:
            db_path: Path to database file
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            logger.warning("Meilisearch client is not available, skipping refresh_from_database")
            return False
        
        try:
            from pathlib import Path
            import sqlite3
            from app.storage.sqlite_repository import SQLiteMessageRepository
            from app.storage.period_repository import PeriodRepository
            from app.storage.kv_repository import KVRepository
            
            db_path = Path(db_path)
            if not db_path.exists():
                logger.error(f"Database file does not exist: {db_path}")
                return False
            
            logger.info(f"Refreshing Meilisearch from database: {db_path}")
            
            # Temporarily connect to the specified database
            # We need to create temporary repository instances that use this database
            # For now, we'll read directly from the database file
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            chunk_size = 100
            
            # Sync messages
            try:
                cursor.execute("SELECT id, session_id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category FROM messages ORDER BY id")
                messages = cursor.fetchall()
                
                # Get character associations for messages
                message_documents = []
                for msg in messages:
                    msg_dict = dict(msg)  # Convert Row to dict
                    msg_id = msg_dict["id"]
                    # Get character IDs for this message
                    cursor.execute("SELECT character_id FROM message_characters WHERE message_id = ?", (msg_id,))
                    character_ids = [row["character_id"] for row in cursor.fetchall()]
                    
                    message_documents.append({
                        "id": msg_id,
                        "session_id": msg_dict["session_id"],
                        "role": msg_dict["role"],
                        "content": msg_dict.get("content") or "",
                        "name": msg_dict.get("tool_name") or "",
                        "tool_call_id": msg_dict.get("tool_call_id") or "",
                        "created_at": msg_dict.get("created_at") or "",
                        "category": msg_dict.get("category", 0),
                        "character_ids": character_ids
                    })
                
                # Add messages to Meilisearch in chunks
                for i in range(0, len(message_documents), chunk_size):
                    chunk = message_documents[i:i + chunk_size]
                    if not self.add_documents(chunk, timeout=30.0):
                        logger.warning(f"Failed to add message chunk {i//chunk_size + 1}")
                
                logger.info(f"Indexed {len(message_documents)} messages")
                
            except Exception as e:
                logger.error(f"Failed to sync messages: {e}", exc_info=True)
            
            # Sync periods
            try:
                cursor.execute("SELECT id, session_id, period_id, period_type, start_at, end_at, content, title, character_id, created_at FROM period ORDER BY id")
                periods = cursor.fetchall()
                
                period_documents = []
                for period in periods:
                    period_dict = dict(period)  # Convert Row to dict
                    period_id = period_dict.get("period_id") or f"period-{period_dict.get('id')}"
                    period_documents.append({
                        "id": period_id,
                        "period_id": period_id,
                        "period_type": period_dict.get("period_type") or "",
                        "session_id": period_dict.get("session_id") or "",
                        "content": period_dict.get("content") or "",
                        "title": period_dict.get("title") or "",
                        "start_at": period_dict.get("start_at") or "",
                        "end_at": period_dict.get("end_at") or "",
                        "character_id": period_dict.get("character_id"),
                        "created_at": period_dict.get("created_at") or "",
                    })
                
                # Add periods to Meilisearch in chunks
                for i in range(0, len(period_documents), chunk_size):
                    chunk = period_documents[i:i + chunk_size]
                    if not self.add_documents(chunk, index_name=self.PERIOD_INDEX, timeout=30.0):
                        logger.warning(f"Failed to add period chunk {i//chunk_size + 1}")
                
                logger.info(f"Indexed {len(period_documents)} periods")
                
            except Exception as e:
                logger.error(f"Failed to sync periods: {e}", exc_info=True)
            
            # Sync kv
            try:
                cursor.execute("SELECT id, session_id, key, key_type, metadata, character_id, created_at, updated_at FROM kv ORDER BY id")
                kv_rows = cursor.fetchall()
                
                kv_documents = []
                for kv in kv_rows:
                    kv_dict = dict(kv)  # Convert Row to dict
                    kv_documents.append({
                        "id": kv_dict["id"],
                        "session_id": kv_dict.get("session_id") or "",
                        "key": kv_dict.get("key") or "",
                        "key_type": kv_dict.get("key_type") or "",
                        "metadata": kv_dict.get("metadata") or "",
                        "character_id": kv_dict.get("character_id"),
                        "created_at": kv_dict.get("created_at") or "",
                        "updated_at": kv_dict.get("updated_at") or "",
                    })
                
                # Add kv to Meilisearch in chunks
                for i in range(0, len(kv_documents), chunk_size):
                    chunk = kv_documents[i:i + chunk_size]
                    if not self.add_documents(chunk, index_name=self.KV_INDEX, timeout=30.0):
                        logger.warning(f"Failed to add kv chunk {i//chunk_size + 1}")
                
                logger.info(f"Indexed {len(kv_documents)} kv entries")
                
            except Exception as e:
                logger.error(f"Failed to sync kv: {e}", exc_info=True)
            
            conn.close()
            logger.info("Meilisearch refresh completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh Meilisearch from database: {e}", exc_info=True)
            return False
    
    def search(
        self,
        query: str,
        session_id: Optional[str] = None,
        role: Optional[str] = None,
        category: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        sort: Optional[List[str]] = None,
        index_name: Optional[str] = None,
        filters: Optional[List[str]] = None,
        character_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search within specified index"""
        if not self._client:
            logger.warning("Meilisearch client is not available, skipping search")
            return {"hits": [], "estimatedTotalHits": 0, "query": query}
        
        try:
            index = self.get_index(index_name)
            # Build filter
            filter_clauses: List[str] = []
            if session_id:
                filter_clauses.append(f'session_id = "{session_id}"')
            if role:
                filter_clauses.append(f'role = "{role}"')
            if category is not None:
                filter_clauses.append(f"category = {category}")
            if character_id is not None:
               filter_clauses.append(f'character_ids = "{character_id}"')
            # If character_id is None, don't add character_ids filter (return all messages)
            if filters:
                filter_clauses.extend(filters)
            
            filter_str = " AND ".join(filter_clauses) if filter_clauses else None
            
            search_options: Dict[str, Any] = {
                "limit": limit,
                "offset": offset,
            }
            
            if filter_str:
                search_options["filter"] = filter_str
            
            if sort:
                search_options["sort"] = sort

            results = index.search(query, search_options)
            return results
        except Exception as e:
            logger.error(f"Failed to search Meilisearch: {e}")
            return {"hits": [], "estimatedTotalHits": 0, "query": query, "error": str(e)}

