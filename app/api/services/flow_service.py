"""Flow service for managing flow instances"""
from typing import Optional, List

from app.config import LLMSettings
from app.flow.base import BaseFlow
from app.flow.character_flow import CharacterFlow
from app.flow.parallel_flow import ParallelFlow
from app.llm import LLM
from app.logger import logger
from app.prompt.character import ROLEPLAY_PROMPT


class FlowService:
    """Service for creating and managing flow instances"""
    
    @staticmethod
    def create_flow(
        flow_type: str = "character",
        session_id: str = "",
        flow_id: Optional[str] = None,
        name: Optional[str] = None,
        roleplay_prompt: Optional[str] = None,
        llm_settings: Optional[LLMSettings] = None,
        visible_for_characters: Optional[List[str]] = None,
        character_id: Optional[str] = None,
        **kwargs
    ) -> BaseFlow:
        """Create a new flow instance
        
        Args:
            flow_type: Type of flow to create
                - "character": Sequential flow (strategy -> speak/telegram)
                - "parallel": Parallel flow with background task support
            session_id: Session ID (required)
            flow_id: Optional flow ID (auto-generated if not provided)
            name: Character/flow name
            roleplay_prompt: Roleplay prompt
            llm_settings: Optional LLM settings
            visible_for_characters: Character IDs that can see messages
            character_id: Character ID
            **kwargs: Additional flow configuration
            
        Returns:
            Flow instance
        """
        if not session_id:
            raise ValueError("session_id is required for flow creation")
        
        logger.info(f"Creating flow: {flow_type} for session: {session_id}")
        
        # Create LLM instances if settings provided
        chat_llm = None
        strategy_llm = None
        if llm_settings:
            chat_llm = LLM(settings=llm_settings)
            strategy_llm = LLM(settings=llm_settings)
            logger.info(f"Using custom LLM settings: {llm_settings.model}")
        else:
            logger.info("Using default LLM config from config.toml")
        
        # Common flow kwargs
        flow_kwargs = {
            "session_id": session_id,
            "name": name or "flow",
            "visible_for_characters": visible_for_characters,
            "character_id": character_id,
        }
        if flow_id:
            flow_kwargs["flow_id"] = flow_id
        flow_kwargs.update(kwargs)
        
        if flow_type in ("character", "chat"):
            flow_kwargs.update({
                "name": name or "character_flow",
                "roleplay_prompt": roleplay_prompt or ROLEPLAY_PROMPT,
                "chat_llm": chat_llm,
                "strategy_llm": strategy_llm,
            })
            return CharacterFlow(**flow_kwargs)
        
        elif flow_type == "parallel":
            # ParallelFlow - subclass should define nodes
            return ParallelFlow(**flow_kwargs)
        
        else:
            raise ValueError(f"Unknown flow type: {flow_type}. Supported: 'character', 'parallel'")
