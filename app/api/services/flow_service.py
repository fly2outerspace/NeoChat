"""Flow service for managing flow instances"""
from typing import Optional, List

from app.config import LLMSettings
from app.flow.base import BaseFlow
from app.flow.chat_parallel_flow import ChatParallelFlow
from app.llm import LLM
from app.logger import logger
from app.prompt.character import ROLEPLAY_PROMPT


class FlowService:
    """Service for creating and managing flow instances"""
    
    @staticmethod
    def create_flow(
        flow_type: str = "chat_parallel",
        session_id: str = "",
        name: Optional[str] = None,
        roleplay_prompt: Optional[str] = None,
        llm_settings: Optional[LLMSettings] = None,
        visible_for_characters: Optional[List[str]] = None,
        character_id: Optional[str] = None,
        **kwargs
    ) -> BaseFlow:
        """Create a new flow instance
        
        Args:
            flow_type: Type of flow to create (only "chat_parallel" is supported)
            session_id: Session ID (required)
            name: Character/flow name
            roleplay_prompt: Roleplay prompt
            llm_settings: Optional LLM settings
            visible_for_characters: Character IDs that can see messages
            character_id: Character ID
            **kwargs: Additional flow configuration
            
        Returns:
            ChatParallelFlow instance
        """
        if not session_id:
            raise ValueError("session_id is required for flow creation")
        
        if flow_type != "chat_parallel":
            raise ValueError(f"Only 'chat_parallel' flow type is supported. Got: {flow_type}")
        
        logger.info(f"Creating chat_parallel flow for session: {session_id}")
        
        # Create LLM instances if settings provided
        chat_llm = None
        infer_llm = None
        if llm_settings:
            chat_llm = LLM(settings=llm_settings)
            infer_llm = LLM(settings=llm_settings)
        else:
            logger.warning("Using default LLM config from config.toml")
        
        # Flow kwargs
        flow_kwargs = {
            "session_id": session_id,
            "name": name or "chat_parallel_flow",
            "roleplay_prompt": roleplay_prompt or ROLEPLAY_PROMPT,
            "chat_llm": chat_llm,
            "infer_llm": infer_llm,
            "visible_for_characters": visible_for_characters,
            "character_id": character_id,
        }
        flow_kwargs.update(kwargs)
        
        return ChatParallelFlow(**flow_kwargs)
