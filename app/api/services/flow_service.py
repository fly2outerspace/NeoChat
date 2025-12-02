"""Flow service for managing flow instances and processing requests"""
from typing import Optional, Union, List
from app.flow.character_flow import CharacterFlow
from app.flow.base import BaseFlow
from app.config import LLMSettings
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
            flow_type: Type of flow to create (default: "character")
                - "character": Sequential flow with three agents (strategy -> speak/telegram)
                - "conditional": Conditional routing flow (decision -> technical/creative/general)
            session_id: Session ID for this flow (required)
            flow_id: Optional flow ID (auto-generated if not provided)
            name: Character name (default: "character_flow")
            roleplay_prompt: Roleplay prompt for the character (default: ROLEPLAY_PROMPT)
            llm_settings: Optional LLM settings (if provided, will be used for both chat_llm and strategy_llm)
            **kwargs: Additional flow configuration
            
        Returns:
            Flow instance
            
        Examples:
            # Create a character flow
            flow = FlowService.create_flow("character", session_id="session-123")
            
            # Create a conditional flow
            flow = FlowService.create_flow("conditional", session_id="session-123")
        """
        if not session_id:
            raise ValueError("session_id is required for flow creation")
        
        logger.info(f"Creating flow: {flow_type} for session: {session_id}")
        
        if flow_type == "character" or flow_type == "chat":  # Support both for backward compatibility
            # Set default values
            character_name = name or "character_flow"
            character_prompt = roleplay_prompt or ROLEPLAY_PROMPT
            
            # Create LLM instances if settings provided
            chat_llm = None
            strategy_llm = None
            if llm_settings:
                chat_llm = LLM(settings=llm_settings)
                strategy_llm = LLM(settings=llm_settings)
                logger.info(f"Using custom LLM settings: {llm_settings.model}")
            else:
                logger.info(f"Using default LLM config from config.toml: openai")
            
            # Only pass flow_id if it's not None (let CharacterFlow auto-generate if None)
            flow_kwargs = {
                "session_id": session_id,
                "name": character_name,
                "roleplay_prompt": character_prompt,
                "chat_llm": chat_llm,
                "strategy_llm": strategy_llm,
                "visible_for_characters": visible_for_characters,
                "character_id": character_id,
            }
            if flow_id is not None:
                flow_kwargs["flow_id"] = flow_id
            flow_kwargs.update(kwargs)
            
            flow = CharacterFlow(**flow_kwargs)
        else:
            raise ValueError(f"Unknown flow type: {flow_type}. Supported types: 'character', 'conditional'")
        
        return flow

