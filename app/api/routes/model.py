"""Model configuration CRUD API routes"""
from fastapi import APIRouter, HTTPException, Path, Query

from app.api.schemas import (
    ModelCreateRequest,
    ModelUpdateRequest,
    ModelResponse,
    ModelListResponse,
)
from app.storage.model_repository import ModelRepository
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["model"])


@router.post("/models", response_model=ModelResponse, status_code=201)
async def create_model(request: ModelCreateRequest) -> ModelResponse:
    """Create a new model configuration"""
    try:
        repository = ModelRepository()
        model_id = repository.insert_model(
            name=request.name,
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
            api_key=request.api_key,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            api_type=request.api_type,
            model_id=request.model_id,
        )
        
        # Fetch the created model (without API key for security)
        model = repository.get_by_model_id(model_id, include_api_key=False)
        if not model:
            raise HTTPException(status_code=500, detail="Failed to retrieve created model")
        
        return ModelResponse(
            id=model["id"],
            model_id=model["model_id"],
            name=model["name"],
            provider=model["provider"],
            model=model["model"],
            base_url=model["base_url"],
            api_key=None,  # Don't return API key in create response
            has_api_key=model.get("has_api_key", False),
            max_tokens=model["max_tokens"],
            temperature=model["temperature"],
            api_type=model["api_type"],
            created_at=model["created_at"],
            updated_at=model["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List all model configurations"""
    try:
        repository = ModelRepository()
        models = repository.list_models()
        
        model_responses = [
            ModelResponse(
                id=model["id"],
                model_id=model["model_id"],
                name=model["name"],
                provider=model["provider"],
                model=model["model"],
                base_url=model["base_url"],
                api_key=None,  # Never return API key in list
                has_api_key=model.get("has_api_key", False),
                max_tokens=model["max_tokens"],
                temperature=model["temperature"],
                api_type=model["api_type"],
                created_at=model["created_at"],
                updated_at=model["updated_at"],
            )
            for model in models
        ]
        
        return ModelListResponse(models=model_responses)
    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str = Path(..., description="Model ID"),
    include_api_key: bool = Query(False, description="Include decrypted API key (use with caution)")
) -> ModelResponse:
    """Get a model configuration by model_id"""
    try:
        repository = ModelRepository()
        model = repository.get_by_model_id(model_id, include_api_key=include_api_key)
        
        if not model:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        
        return ModelResponse(
            id=model["id"],
            model_id=model["model_id"],
            name=model["name"],
            provider=model["provider"],
            model=model["model"],
            base_url=model["base_url"],
            api_key=model.get("api_key") if include_api_key else None,
            has_api_key=model.get("has_api_key", False) if not include_api_key else None,
            max_tokens=model["max_tokens"],
            temperature=model["temperature"],
            api_type=model["api_type"],
            created_at=model["created_at"],
            updated_at=model["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    request: ModelUpdateRequest,
    model_id: str = Path(..., description="Model ID")
) -> ModelResponse:
    """Update a model configuration by model_id"""
    try:
        repository = ModelRepository()
        
        # Check if model exists
        existing = repository.get_by_model_id(model_id, include_api_key=False)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        
        # Update model
        success = repository.update_model(
            model_id=model_id,
            name=request.name,
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
            api_key=request.api_key,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            api_type=request.api_type,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update model")
        
        # Fetch updated model (without API key for security)
        model = repository.get_by_model_id(model_id, include_api_key=False)
        if not model:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated model")
        
        return ModelResponse(
            id=model["id"],
            model_id=model["model_id"],
            name=model["name"],
            provider=model["provider"],
            model=model["model"],
            base_url=model["base_url"],
            api_key=None,  # Don't return API key in update response
            has_api_key=model.get("has_api_key", False),
            max_tokens=model["max_tokens"],
            temperature=model["temperature"],
            api_type=model["api_type"],
            created_at=model["created_at"],
            updated_at=model["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: str = Path(..., description="Model ID")
) -> None:
    """Delete a model configuration by model_id"""
    try:
        repository = ModelRepository()
        
        # Check if model exists
        existing = repository.get_by_model_id(model_id, include_api_key=False)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        
        # Delete model
        success = repository.delete_model(model_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete model")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

