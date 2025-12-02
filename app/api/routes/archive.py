"""Archive management API routes"""
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ArchiveCreateRequest,
    ArchiveSwitchRequest,
    ArchiveListResponse,
    ArchiveResponse,
    ArchiveInfo,
)
from app.storage.database_manager import DatabaseManager
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["archive"])


@router.post("/archives", response_model=ArchiveResponse, status_code=201)
async def create_archive(request: ArchiveCreateRequest) -> ArchiveResponse:
    """Create a new archive as a copy of current database"""
    try:
        manager = DatabaseManager()
        archive_name = manager.create_archive(request.name)
        
        # Get archive info
        archives = manager.list_archives()
        archive_info = next((a for a in archives if a["name"] == archive_name), None)
        
        if not archive_info:
            raise HTTPException(status_code=500, detail="Failed to retrieve created archive")
        
        return ArchiveResponse(
            success=True,
            message=f"Archive '{archive_name}' created successfully as copy of current database",
            archive=ArchiveInfo(**archive_info)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating archive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/archives/empty", response_model=ArchiveResponse, status_code=201)
async def create_empty_archive(request: ArchiveCreateRequest) -> ArchiveResponse:
    """Create a new empty archive database"""
    try:
        manager = DatabaseManager()
        archive_name = manager.create_empty_archive(request.name)
        
        # Get archive info
        archives = manager.list_archives()
        archive_info = next((a for a in archives if a["name"] == archive_name), None)
        
        if not archive_info:
            raise HTTPException(status_code=500, detail="Failed to retrieve created archive")
        
        return ArchiveResponse(
            success=True,
            message=f"Empty archive '{archive_name}' created successfully",
            archive=ArchiveInfo(**archive_info)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating empty archive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/archives/empty/auto", response_model=ArchiveResponse, status_code=201)
async def create_empty_archive_auto() -> ArchiveResponse:
    """Reset working database to empty state without creating an archive file
    
    This endpoint clears the working database and initializes it as empty.
    No archive file is created, so no default archive will appear in the archive list.
    """
    try:
        manager = DatabaseManager()
        
        # Reset working database to empty state (no archive file created)
        manager.reset_working_database()
        
        return ArchiveResponse(
            success=True,
            message="Working database reset to empty state successfully",
            archive=None  # No archive is created, so return None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error resetting working database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/archives/overwrite", response_model=ArchiveResponse)
async def overwrite_archive(request: ArchiveCreateRequest) -> ArchiveResponse:
    """Overwrite an archive with current database content
    
    This endpoint copies the current active database to the target archive location.
    If the archive exists, it will be replaced. If it doesn't exist, it will be created.
    """
    try:
        manager = DatabaseManager()
        archive_name = manager.overwrite_archive(request.name)
        
        # Get archive info
        archives = manager.list_archives()
        archive_info = next((a for a in archives if a["name"] == archive_name), None)
        
        if not archive_info:
            raise HTTPException(status_code=500, detail="Failed to retrieve overwritten archive")
        
        return ArchiveResponse(
            success=True,
            message=f"Archive '{archive_name}' overwritten successfully with current database content",
            archive=ArchiveInfo(**archive_info)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error overwriting archive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/archives/{archive_name}", response_model=ArchiveResponse)
async def delete_archive(archive_name: str) -> ArchiveResponse:
    """Delete an archive
    
    Returns error if trying to delete currently active archive.
    """
    try:
        manager = DatabaseManager()
        manager.delete_archive(archive_name)
        
        return ArchiveResponse(
            success=True,
            message=f"Archive '{archive_name}' deleted successfully",
            archive=None
        )
    except ValueError as e:
        # This includes the case where trying to delete active archive
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting archive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/archives/load", response_model=ArchiveResponse)
async def load_archive(request: ArchiveSwitchRequest) -> ArchiveResponse:
    """Load an archive into working database and sync characters to settings"""
    try:
        if request.name is None:
            raise HTTPException(status_code=400, detail="Archive name is required")
        
        manager = DatabaseManager()
        manager.load_archive(request.name)
        
        # Get archive info
        archives = manager.list_archives()
        archive_info = next((a for a in archives if a["name"] == request.name), None)
        
        if not archive_info:
            raise HTTPException(status_code=500, detail="Failed to retrieve loaded archive")
        
        # Sync characters from archive to settings
        # Only import characters that don't exist in settings (based on character_id)
        imported_character_ids = []
        try:
            from app.storage.archive_character_repository import ArchiveCharacterRepository
            from app.storage.character_repository import CharacterRepository
            
            archive_char_repo = ArchiveCharacterRepository()
            settings_char_repo = CharacterRepository()
            
            # Get all characters from archive (now in working database)
            archive_characters = archive_char_repo.list_characters()
            
            # For each archive character, check if it exists in settings
            for arch_char in archive_characters:
                char_id = arch_char["character_id"]
                existing = settings_char_repo.get_by_character_id(char_id)
                
                if not existing:
                    # Character doesn't exist in settings, import it
                    settings_char_repo.insert_character(
                        name=arch_char["name"],
                        roleplay_prompt=arch_char.get("roleplay_prompt"),
                        avatar=arch_char.get("avatar"),
                        character_id=char_id,  # Preserve character_id from archive
                    )
                    imported_character_ids.append(char_id)
                    logger.info(f"Imported character {char_id} from archive to settings")
        except Exception as e:
            # Log error but don't fail the load operation
            logger.error(f"Error syncing characters from archive to settings: {e}", exc_info=True)
        
        return ArchiveResponse(
            success=True,
            message=f"Loaded archive '{request.name}' successfully",
            archive=ArchiveInfo(**archive_info),
            imported_characters=imported_character_ids if imported_character_ids else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading archive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/archives", response_model=ArchiveListResponse)
async def list_archives() -> ArchiveListResponse:
    """List all available archives"""
    try:
        manager = DatabaseManager()
        archives = manager.list_archives()
        
        archive_list = [ArchiveInfo(**a) for a in archives]
        
        return ArchiveListResponse(
            archives=archive_list,
            current_archive=None
        )
    except Exception as e:
        logger.error(f"Error listing archives: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



