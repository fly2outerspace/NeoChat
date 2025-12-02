"""Agent service for managing agent instances and processing requests"""
from typing import Optional, List
from app.agent.character import Character
from app.llm import LLM
from app.config import LLMSettings
from app.logger import logger
from app.tool import (
    SendTelegramMessage,
    SpeakInPerson,
    GetCurrentTime,
    PlanningTool,
    Terminate,
    ToolCollection,
    DialogueHistory,
    WebSearch,
    ScheduleReader,
    ScheduleWriter,
    ScenarioReader,
    ScenarioWriter,
    RelationTool,
    Reflection,
)

from app.prompt.character import ROLEPLAY_PROMPT
class AgentService:
    """Service for creating and managing agent instances"""
    
    @staticmethod
    def create_agent(
        session_id: str,
        name: str = "Stacy",
        roleplay_prompt: str = ROLEPLAY_PROMPT,
        character_id: Optional[str] = None,
        llm_settings: Optional[LLMSettings] = None,
        visible_for_characters: Optional[List[str]] = None,
    ) -> Character:
        """Create a new agent instance
        
        Args:
            session_id: Session ID for this agent (required)
            name: Agent name
            roleplay_prompt: Roleplay prompt for character
            character_id: Optional character ID
            llm_settings: Optional LLMSettings object. If not provided, uses default config from config.toml ("openai")
        
        Note: Each request should create a new agent instance.
        LLM will be reused through its own singleton mechanism.
        Memory will be automatically loaded from storage based on session_id.
        """
        logger.info(f"Creating agent: {name} (character_id: {character_id}) for session: {session_id}")
        # LLM will be reused through LLM._instances cache
        if llm_settings is not None:
            # Use provided settings directly
            llm = LLM(settings=llm_settings)
            logger.info(f"Using custom LLM settings: {llm_settings.model}")
        else:
            # Use default config from config.toml ("openai")
            llm = LLM(config_name="openai")
            logger.info(f"Using default LLM config from config.toml: openai")
        agent = Character(
            session_id=session_id,
            name=name,
            description="",
            roleplay_prompt=roleplay_prompt,
            character_id=character_id,
            llm=llm,
            available_tools=ToolCollection(
                Reflection(),
                Terminate(),
                WebSearch(),
                SpeakInPerson(session_id=session_id),
                SendTelegramMessage(session_id=session_id),
                DialogueHistory(session_id=session_id, character_id=character_id),
                ScheduleReader(session_id=session_id, character_id=character_id),
                ScheduleWriter(session_id=session_id, character_id=character_id),
                ScenarioReader(session_id=session_id, character_id=character_id),
                ScenarioWriter(session_id=session_id, character_id=character_id),
                RelationTool(session_id=session_id, character_id=character_id),
            ),
            max_steps=10,
            visible_for_characters=visible_for_characters,
        )
        return agent
    
    