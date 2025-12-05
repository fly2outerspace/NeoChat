"""Memory API routes for schedules and scenarios"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.storage.archive_character_repository import ArchiveCharacterRepository
from app.storage.session_repository import SQLiteSessionRepository
from app.memory import Memory
from app.storage.scenario_store import ScenarioStore
from app.schema import Relation
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["memory"])


class ScheduleItem(BaseModel):
    """Schedule item response"""
    entry_id: str
    session_id: str
    start_at: str
    end_at: str
    content: str
    created_at: Optional[str] = None


class ScenarioItem(BaseModel):
    """Scenario item response"""
    scenario_id: str
    session_id: str
    start_at: str
    end_at: str
    title: Optional[str] = None
    content: Optional[str] = None
    created_at: Optional[str] = None


class CharacterMemoryItem(BaseModel):
    """Combined schedule and scenario item for a character"""
    type: str  # "schedule" or "scenario"
    start_at: str
    end_at: str
    content: str
    title: Optional[str] = None
    entry_id: Optional[str] = None
    scenario_id: Optional[str] = None
    session_id: str


class CharacterMemoryResponse(BaseModel):
    """Memory data for a single character"""
    character_id: str
    character_name: str
    items: List[CharacterMemoryItem]


class MemoryResponse(BaseModel):
    """All characters' memory data"""
    characters: List[CharacterMemoryResponse]


@router.get("/memory", response_model=MemoryResponse)
async def get_all_memory() -> MemoryResponse:
    """Get all schedules and scenarios for all characters in the current archive"""
    try:
        # Get all characters from current archive database
        character_repo = ArchiveCharacterRepository()
        characters = character_repo.list_characters()
        
        # Get all sessions
        session_repo = SQLiteSessionRepository()
        sessions = session_repo.list_sessions()
        session_ids = [session["id"] for session in sessions]
        
        character_memories = []
        
        for char in characters:
            character_id = char["character_id"]
            character_name = char["name"]
            
            # Collect all schedule and scenario items for this character across all sessions
            combined_items = []
            
            # Get schedules from all sessions
            for session_id in session_ids:
                schedule_entries = Memory.get_schedule_entries(session_id, character_id=character_id)
                for entry in schedule_entries:
                    combined_items.append({
                        "type": "schedule",
                        "start_at": entry.start_at,
                        "end_at": entry.end_at,
                        "content": entry.content or "",
                        "title": None,
                        "entry_id": entry.entry_id,
                        "scenario_id": None,
                        "session_id": session_id,
                    })
            
            # Get scenarios from all sessions
            scenario_store = ScenarioStore()
            for session_id in session_ids:
                scenario_store.set_session(session_id)
                scenarios = scenario_store.list_scenarios(session_id, character_id=character_id)
                for sc in scenarios:
                    combined_items.append({
                        "type": "scenario",
                        "start_at": sc.start_at,
                        "end_at": sc.end_at,
                        "content": sc.content or "",
                        "title": getattr(sc, "title", None) or None,
                        "entry_id": None,
                        "scenario_id": sc.scenario_id,
                        "session_id": session_id,
                    })
            
            # Sort by start_at (same as prepare_memory_content)
            combined_items.sort(key=lambda x: x["start_at"])
            
            # Convert to response models
            memory_items = [
                CharacterMemoryItem(
                    type=item["type"],
                    start_at=item["start_at"],
                    end_at=item["end_at"],
                    content=item["content"],
                    title=item["title"],
                    entry_id=item["entry_id"],
                    scenario_id=item["scenario_id"],
                    session_id=item["session_id"],
                )
                for item in combined_items
            ]
            
            character_memories.append(
                CharacterMemoryResponse(
                    character_id=character_id,
                    character_name=character_name,
                    items=memory_items,
                )
            )
        
        return MemoryResponse(characters=character_memories)
        
    except Exception as e:
        logger.error(f"Error getting memory data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class CharacterRelationItem(BaseModel):
    """Relation item for a character"""
    relation_id: str
    session_id: str
    name: str
    knowledge: str
    progress: str
    created_at: Optional[str] = None


class CharacterRelationResponse(BaseModel):
    """Relation data for a single character"""
    character_id: str
    character_name: str
    relations: List[CharacterRelationItem]


class RelationResponse(BaseModel):
    """All characters' relation data"""
    characters: List[CharacterRelationResponse]


@router.get("/relations", response_model=RelationResponse)
async def get_all_relations() -> RelationResponse:
    """Get all relations for all characters in the current archive"""
    try:
        # Get all characters from current archive database
        character_repo = ArchiveCharacterRepository()
        characters = character_repo.list_characters()
        
        # Get all sessions
        session_repo = SQLiteSessionRepository()
        sessions = session_repo.list_sessions()
        session_ids = [session["id"] for session in sessions]
        
        character_relations = []
        
        for char in characters:
            character_id = char["character_id"]
            character_name = char["name"]
            
            # Collect all relations for this character across all sessions
            all_relations: List[Relation] = []
            
            # Get relations from all sessions
            for session_id in session_ids:
                relations = Memory.get_relations(session_id, character_id=character_id)
                all_relations.extend(relations)
            
            # Convert to response models
            relation_items = [
                CharacterRelationItem(
                    relation_id=rel.relation_id,
                    session_id=rel.session_id,
                    name=rel.name,
                    knowledge=rel.knowledge or "",
                    progress=rel.progress or "",
                    created_at=rel.created_at,
                )
                for rel in all_relations
            ]
            
            character_relations.append(
                CharacterRelationResponse(
                    character_id=character_id,
                    character_name=character_name,
                    relations=relation_items,
                )
            )
        
        return RelationResponse(characters=character_relations)
        
    except Exception as e:
        logger.error(f"Error getting relation data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

