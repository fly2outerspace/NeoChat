"""

Supports TOML configuration files with inheritance:
    [llm]                    # Base/default configuration
    model = "gpt-4o-mini"
    base_url = "https://api.openai.com/v1"
    ...
    
    [llm.gpt4]               # Named configuration (inherits from base)
    model = "gpt-4"
    temperature = 0.7
"""
import threading
import tomllib
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field, ValidationError


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class LLMSettings(BaseModel):
    """LLM configuration settings."""
    
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: str = Field(..., description="API key")
    max_tokens: int = Field(4096, description="Maximum number of tokens per request")
    temperature: float = Field(1.0, description="Sampling temperature")
    api_type: str = Field("openai", description="API type (e.g., 'openai', 'custom')")
    http_referer: Optional[str] = Field(None, description="HTTP-Referer header (for OpenRouter)")
    x_title: Optional[str] = Field(None, description="X-Title header (for OpenRouter)")


class MeilisearchSettings(BaseModel):
    """Meilisearch configuration settings."""
    
    executable_path: Optional[str] = Field(None, description="Path to meilisearch.exe")
    db_path: Optional[str] = Field(None, description="Database path for data persistence")
    http_addr: str = Field("127.0.0.1:7700", description="HTTP address to bind")
    auto_start: bool = Field(False, description="Auto-start Meilisearch on FastAPI startup")
    # Note: auto_sync has been removed - Meilisearch is automatically refreshed when loading archives


class TimeSettings(BaseModel):
    """Virtual time configuration settings."""
    
    mode: str = Field("real", description="Time mode: 'real', 'offset', 'fixed', or 'scaled'")
    offset_seconds: float = Field(0.0, description="Time offset in seconds (for offset mode)")
    fixed_time: Optional[str] = Field(None, description="Fixed time point (for fixed mode, format: 'YYYY-MM-DD HH:MM:SS')")
    speed: float = Field(1.0, description="Time speed multiplier (for scaled mode, 1.0 = normal)")
    virtual_start: Optional[str] = Field(None, description="Virtual start time (for scaled mode, format: 'YYYY-MM-DD HH:MM:SS')")


class AppConfig(BaseModel):
    """Application configuration."""
    
    llm: Dict[str, LLMSettings]
    meilisearch: Optional[MeilisearchSettings] = None
    time: Optional[TimeSettings] = None


class Config:
    """
    Simplified configuration manager with singleton pattern.
    
    Usage:
        from app.config import config
        settings = config.llm["openai"]
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize configuration (only once)."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._load_config()
                    self._initialized = True
    
    @staticmethod
    def _get_config_path() -> Path:
        """
        Get configuration file path.
        
        Returns:
            Path to config file (config.toml or config.example.toml)
            
        Raises:
            FileNotFoundError: If no config file is found
        """
        root = PROJECT_ROOT
        config_path = root / "config" / "config.toml"
        
        if config_path.exists():
            return config_path
        
        example_path = root / "config" / "config.example.toml"
        if example_path.exists():
            return example_path
        
        raise FileNotFoundError(
            f"No configuration file found in {root / 'config'}"
        )
    
    def _load_config_file(self) -> dict:
        """Load and parse TOML configuration file."""
        config_path = self._get_config_path()
        try:
            with config_path.open("rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML format in {config_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {config_path}: {e}") from e
    
    def _parse_llm_config(self, raw_config: dict) -> Dict[str, LLMSettings]:
        """
        Parse LLM configuration from raw TOML data.
        
        Handles nested [llm.name] sections (e.g., [llm.openai], [llm.deepseek]).
        
        Args:
            raw_config: Raw TOML configuration dictionary
            
        Returns:
            Dictionary mapping config names to LLMSettings objects
        """
        llm_section = raw_config.get("llm", {})
        
        if not llm_section:
            raise ValueError("No [llm] section found in configuration file")
        
        # Extract named configurations (nested tables like [llm.openai])
        named_configs = {
            name: config_dict
            for name, config_dict in llm_section.items()
            if isinstance(config_dict, dict)
        }
        
        if not named_configs:
            raise ValueError(
                "[llm] section must contain at least one named configuration (e.g., [llm.openai])"
            )
        
        # Build final configuration dictionary
        configs = {}
        
        # Add named configurations
        for name, config_dict in named_configs.items():
            try:
                configs[name] = LLMSettings(**config_dict)
            except ValidationError as e:
                raise ValueError(
                    f"Invalid configuration for '{name}': {e}"
                ) from e
        
        # If "openai" exists, also add it as "default" for backward compatibility
        if "openai" in configs and "default" not in configs:
            configs["default"] = configs["openai"]
        
        return configs
    
    def _parse_meilisearch_config(self, raw_config: dict) -> Optional[MeilisearchSettings]:
        """Parse Meilisearch configuration from raw TOML data."""
        meilisearch_section = raw_config.get("meilisearch", {})
        
        if not meilisearch_section:
            return None
        
        try:
            return MeilisearchSettings(**meilisearch_section)
        except ValidationError as e:
            raise ValueError(f"Invalid Meilisearch configuration: {e}") from e
    
    def _parse_time_config(self, raw_config: dict) -> Optional[TimeSettings]:
        """Parse time configuration from raw TOML data."""
        time_section = raw_config.get("time", {})
        
        if not time_section:
            return TimeSettings()  # Return default settings
        
        try:
            return TimeSettings(**time_section)
        except ValidationError as e:
            raise ValueError(f"Invalid time configuration: {e}") from e
    
    def _load_config(self):
        """Load and validate configuration."""
        try:
            raw_config = self._load_config_file()
            llm_configs = self._parse_llm_config(raw_config)
            meilisearch_config = self._parse_meilisearch_config(raw_config)
            time_config = self._parse_time_config(raw_config)
            self._config = AppConfig(llm=llm_configs, meilisearch=meilisearch_config, time=time_config)
        except (ValueError, ValidationError) as e:
            raise ValueError(f"Configuration validation failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to initialize configuration: {e}") from e
    
    @property
    def llm(self) -> Dict[str, LLMSettings]:
        """
        Get LLM configurations.
        
        Returns:
            Dictionary mapping config names to LLMSettings objects
        """
        return self._config.llm
    
    def get_llm_config(self, name: str = "default") -> LLMSettings:
        """
        Get LLM configuration by name.
        
        Args:
            name: Configuration name (default: "openai")
            
        Returns:
            LLMSettings object
            
        Raises:
            KeyError: If configuration name not found
        """
        if name not in self.llm:
            available = ", ".join(self.llm.keys())
            raise KeyError(
                f"LLM configuration '{name}' not found. "
                f"Available: {available}"
            )
        return self.llm[name]
    
    @property
    def meilisearch(self) -> Optional[MeilisearchSettings]:
        """
        Get Meilisearch configuration.
        
        Returns:
            MeilisearchSettings object or None if not configured
        """
        return self._config.meilisearch
    
    @property
    def time(self) -> TimeSettings:
        """
        Get time configuration.
        
        Returns:
            TimeSettings object (default if not configured)
        """
        return self._config.time or TimeSettings()
    
    def reload(self):
        """Reload configuration from file (useful for testing)."""
        with self._lock:
            self._initialized = False
            self._load_config()


# Global singleton instance
config = Config()

