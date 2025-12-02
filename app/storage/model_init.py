"""Initialize default model configurations from config.toml"""
from app.storage.model_repository import ModelRepository
from app.config import config
from app.logger import logger


def init_default_models():
    """Initialize default model configurations from config.toml
    
    This function should be called on application startup to ensure
    default models are available in the database.
    """
    repository = ModelRepository()
    
    try:
        # Get all LLM configurations from config.toml
        llm_configs = config.llm
        
        # Default models to create
        default_models = []
        
        # Process each LLM configuration
        for config_name, llm_settings in llm_configs.items():
            # Determine provider name from config name or base_url
            provider = _determine_provider(config_name, llm_settings.base_url)
            
            # Create model_id from config name
            model_id = f"model-{config_name}"
            
            # Check if model already exists
            if repository.model_exists(model_id):
                logger.debug(f"Model {model_id} already exists, skipping")
                continue
            
            default_models.append({
                "model_id": model_id,
                "name": _format_model_name(config_name),
                "provider": provider,
                "model": llm_settings.model,
                "base_url": llm_settings.base_url,
                "api_key": llm_settings.api_key,
                "max_tokens": llm_settings.max_tokens,
                "temperature": llm_settings.temperature,
                "api_type": llm_settings.api_type,
            })
        
        # Insert default models
        for model_data in default_models:
            try:
                repository.insert_model(
                    model_id=model_data["model_id"],
                    name=model_data["name"],
                    provider=model_data["provider"],
                    model=model_data["model"],
                    base_url=model_data["base_url"],
                    api_key=model_data["api_key"],
                    max_tokens=model_data["max_tokens"],
                    temperature=model_data["temperature"],
                    api_type=model_data["api_type"],
                )
                logger.info(f"Initialized default model: {model_data['name']} ({model_data['model_id']})")
            except Exception as e:
                logger.warning(f"Failed to initialize model {model_data['model_id']}: {e}")
        
        if default_models:
            logger.info(f"Initialized {len(default_models)} default model configurations")
        else:
            logger.info("All default models already exist in database")
            
    except Exception as e:
        logger.error(f"Failed to initialize default models: {e}", exc_info=True)


def _determine_provider(config_name: str, base_url: str) -> str:
    """Determine provider name from config name or base_url"""
    config_name_lower = config_name.lower()
    
    # Check config name first
    if "openai" in config_name_lower or config_name == "default":
        return "OpenAI"
    elif "deepseek" in config_name_lower:
        return "DeepSeek"
    elif "grok" in config_name_lower or "xai" in config_name_lower:
        return "xAI"
    elif "google" in config_name_lower or "gemini" in config_name_lower:
        return "Google"
    elif "openrouter" in config_name_lower:
        return "OpenRouter"
    
    # Check base_url as fallback
    base_url_lower = base_url.lower()
    if "openai.com" in base_url_lower:
        return "OpenAI"
    elif "deepseek.com" in base_url_lower:
        return "DeepSeek"
    elif "x.ai" in base_url_lower:
        return "xAI"
    elif "google" in base_url_lower:
        return "Google"
    elif "openrouter.ai" in base_url_lower:
        return "OpenRouter"
    
    # Default
    return "Unknown"


def _format_model_name(config_name: str) -> str:
    """Format config name into a readable model name"""
    if config_name == "default":
        return "Default (GPT-4o)"
    elif config_name == "openai":
        return "OpenAI (GPT-4o)"
    
    # Convert snake_case or kebab-case to Title Case
    name = config_name.replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() for word in name.split())

