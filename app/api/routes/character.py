"""Character card CRUD API routes"""
from fastapi import APIRouter, HTTPException, Path

from app.api.schemas import (
    CharacterCreateRequest,
    CharacterUpdateRequest,
    CharacterResponse,
    CharacterListResponse,
)
from app.storage.character_repository import CharacterRepository
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["character"])


@router.post("/characters", response_model=CharacterResponse, status_code=201)
async def create_character(request: CharacterCreateRequest) -> CharacterResponse:
    """Create a new character card"""
    try:
        repository = CharacterRepository()
        character_id = repository.insert_character(
            name=request.name,
            roleplay_prompt=request.roleplay_prompt,
            avatar=request.avatar,
            character_id=request.character_id,
        )
        
        # Fetch the created character
        character = repository.get_by_character_id(character_id)
        if not character:
            raise HTTPException(status_code=500, detail="Failed to retrieve created character")
        
        return CharacterResponse(
            id=character["id"],
            character_id=character["character_id"],
            name=character["name"],
            roleplay_prompt=character.get("roleplay_prompt"),
            avatar=character.get("avatar"),
            created_at=character["created_at"],
            updated_at=character["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating character: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/characters", response_model=CharacterListResponse)
async def list_characters() -> CharacterListResponse:
    """List all character cards"""
    try:
        repository = CharacterRepository()
        characters = repository.list_characters()
        
        character_responses = [
            CharacterResponse(
                id=char["id"],
                character_id=char["character_id"],
                name=char["name"],
                roleplay_prompt=char.get("roleplay_prompt"),
                avatar=char.get("avatar"),
                created_at=char["created_at"],
                updated_at=char["updated_at"],
            )
            for char in characters
        ]
        
        return CharacterListResponse(characters=character_responses)
    except Exception as e:
        logger.error(f"Error listing characters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/characters/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str = Path(..., description="Character ID")
) -> CharacterResponse:
    """Get a character card by character_id"""
    try:
        repository = CharacterRepository()
        character = repository.get_by_character_id(character_id)
        
        if not character:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        
        return CharacterResponse(
            id=character["id"],
            character_id=character["character_id"],
            name=character["name"],
            roleplay_prompt=character.get("roleplay_prompt"),
            avatar=character.get("avatar"),
            created_at=character["created_at"],
            updated_at=character["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting character: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/characters/{character_id}", response_model=CharacterResponse)
async def update_character(
    request: CharacterUpdateRequest,
    character_id: str = Path(..., description="Character ID")
) -> CharacterResponse:
    """Update a character card by character_id"""
    try:
        repository = CharacterRepository()
        
        # Check if character exists
        existing = repository.get_by_character_id(character_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        
        # Update character
        success = repository.update_character(
            character_id=character_id,
            name=request.name,
            roleplay_prompt=request.roleplay_prompt,
            avatar=request.avatar,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update character")
        
        # Fetch updated character
        character = repository.get_by_character_id(character_id)
        if not character:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated character")
        
        return CharacterResponse(
            id=character["id"],
            character_id=character["character_id"],
            name=character["name"],
            roleplay_prompt=character.get("roleplay_prompt"),
            avatar=character.get("avatar"),
            created_at=character["created_at"],
            updated_at=character["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating character: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/characters/{character_id}", status_code=204)
async def delete_character(
    character_id: str = Path(..., description="Character ID")
) -> None:
    """Delete a character card by character_id"""
    try:
        repository = CharacterRepository()
        
        # Check if character exists
        existing = repository.get_by_character_id(character_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Character not found: {character_id}")
        
        # Delete character
        success = repository.delete_character(character_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete character")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting character: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

