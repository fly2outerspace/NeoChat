"""
Simplified LLM client with cleaner configuration management.

Usage:
    # Use default config from config.toml
    llm = LLM()
    
    # Use specific config by name
    llm = LLM("gpt4")
    
    # Use custom settings directly
    llm = LLM(settings=LLMSettings(...))
"""
from typing import Awaitable, Callable, Dict, List, Literal, Optional, Union, Any

from openai import (
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.config import LLMSettings, config
from app.logger import logger
from app.schema import Message, Function, ToolCall
from app.utils import log_execution_time


class _StreamingChatMessage:
    """Lightweight message object matching OpenAI ChatCompletionMessage attrs."""

    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
    ):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls


class LLM:
    """Simplified LLM client with cleaner configuration."""
    
    # Cache for singleton instances per config
    _instances: Dict[str, "LLM"] = {}
    
    def __init__(
        self,
        config_name: str = "openai",
        settings: Optional[LLMSettings] = None,
    ):
        """
        Initialize LLM client.
        
        Args:
            config_name: Name of the config to use from config.toml
            settings: Optional LLMSettings object to use directly
        """
        # Use provided settings or get from config
        if settings is None:
            settings = self._get_settings_from_config(config_name)
        
        # Store settings
        self.settings = settings
        self.model = settings.model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature
        self.api_key = settings.api_key
        self.base_url = settings.base_url
        
        # Build default headers for OpenRouter support
        default_headers = {}
        if settings.http_referer:
            default_headers["HTTP-Referer"] = settings.http_referer
        if settings.x_title:
            default_headers["X-Title"] = settings.x_title
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=default_headers if default_headers else None
        )
    
    @staticmethod
    def _get_settings_from_config(config_name: str) -> LLMSettings:
        """Get LLMSettings from global config by name."""
        all_configs = config.llm
        
        if config_name not in all_configs:
            # Try "default" for backward compatibility, then "openai"
            if "default" in all_configs:
                logger.warning(
                    f"Config '{config_name}' not found, using 'default'"
                )
                config_name = "default"
            elif "openai" in all_configs:
                logger.warning(
                    f"Config '{config_name}' not found, using 'openai'"
                )
                config_name = "openai"
            else:
                # Use first available config
                fallback_name = next(iter(all_configs.keys()))
                logger.warning(
                    f"Config '{config_name}' not found, using '{fallback_name}'"
                )
                config_name = fallback_name
        
        return all_configs[config_name]
    
    @classmethod
    def get_instance(
        cls,
        config_name: str = "openai",
        settings: Optional[LLMSettings] = None,
    ) -> "LLM":
        """
        Get or create singleton instance.
        
        Args:
            config_name: Name of the config to use
            settings: Optional LLMSettings object
            
        Returns:
            LLM instance (singleton per config_name)
        """
        # Create cache key
        cache_key = config_name if settings is None else f"custom_{id(settings)}"
        
        # Return existing instance if available
        if cache_key in cls._instances:
            return cls._instances[cache_key]
        
        # Create new instance
        instance = cls(config_name=config_name, settings=settings)
        cls._instances[cache_key] = instance
        return instance
    
    @staticmethod
    def format_messages(
        messages: List[Union[dict, Message]]
    ) -> List[dict]:
        """
        Format messages for LLM by converting them to OpenAI message format.

        Args:
            messages: List of messages that can be either dict or Message objects

        Returns:
            List[dict]: List of formatted messages in OpenAI format

        Raises:
            ValueError: If messages are invalid or missing required fields
            TypeError: If unsupported message types are provided
        """
        formatted_messages = []

        for message in messages:
            if isinstance(message, dict):
                if "role" not in message:
                    raise ValueError("Message dict must contain 'role' field")
                formatted_messages.append(message)
            elif isinstance(message, Message):
                formatted_messages.append(message.to_dict())
            else:
                raise TypeError(f"Unsupported message type: {type(message)}")

        # Validate all messages have required fields
        for msg in formatted_messages:
            if msg["role"] not in ["system", "user", "assistant", "tool"]:
                raise ValueError(f"Invalid role: {msg['role']}")
            if "content" not in msg and "tool_calls" not in msg:
                raise ValueError(
                    "Message must contain either 'content' or 'tool_calls'"
                )

        return formatted_messages

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    async def ask(
        self,
        messages: List[Union[dict, Message]],
        stream: bool = True,
        temperature: Optional[float] = None,
        on_delta: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        Send a prompt to the LLM and get the response.

        Args:
            messages: List of conversation messages
            stream: Whether to stream the response
            temperature: Sampling temperature for the response
            on_delta: Optional callback for streaming token deltas

        Returns:
            str: The generated response

        Raises:
            ValueError: If messages are invalid or response is empty
            OpenAIError: If API call fails after retries
        """
        try:

            # from pprint import pprint
            # for msg in messages:
            #     pprint(msg.to_dict(), width=210)
            messages = self.format_messages(messages)
            if not stream:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=temperature or self.temperature,
                    stream=False,
                )
                if not response.choices or not response.choices[0].message.content:
                    raise ValueError("Empty or invalid response from LLM")
                return response.choices[0].message.content

            # Streaming request
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
            )

            collected_messages = []
            async for chunk in response:
                choice = chunk.choices[0]

                # Token delta
                chunk_message = choice.delta.content or ""
                if chunk_message:
                    collected_messages.append(chunk_message)
                    if on_delta:
                        await on_delta(chunk_message)

                # Tool call delta (if present)
                if choice.delta.tool_calls:
                    for tool_delta in choice.delta.tool_calls:
                        if on_delta:
                            payload = {
                                "type": "tool_delta",
                                "tool_call_id": tool_delta.id,
                                "name": tool_delta.function and tool_delta.function.name,
                                "arguments_delta": tool_delta.function and tool_delta.function.arguments,
                            }
                            await on_delta(payload)

                # 如果模型标记了结束，再跳出循环（但不丢弃当前 chunk 的内容）
                if choice.finish_reason is not None:
                    break

            full_response = "".join(collected_messages).strip()
            if on_delta:
                await on_delta({"type": "stream_end"})
            if not full_response:
                raise ValueError("Empty response from streaming LLM")
            return full_response

        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            raise
        except OpenAIError as oe:
            logger.error(f"OpenAI API error: {oe}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask: {e}")
            raise

    @staticmethod
    def _validate_and_fix_messages(messages: List[dict]) -> List[dict]:
        """
        Validate and fix message sequence to ensure tool messages are properly paired.
        
        OpenAI API requires that tool messages must follow an assistant message with tool_calls.
        This function handles two scenarios:
        1. Tool messages without corresponding assistant messages (orphaned tool messages)
        2. Assistant messages with tool_calls but no corresponding tool messages (orphaned tool_calls)
        
        Args:
            messages: List of formatted messages
            
        Returns:
            List of validated and fixed messages
        """
        if not messages:
            return messages
        
        # First pass: collect all valid tool call pairs
        # Map: assistant message index -> set of tool_call_ids that have corresponding tool messages
        assistant_tool_calls_map = {}  # {assistant_index: {tool_call_id: tool_message_index}}
        tool_call_to_assistant = {}  # {tool_call_id: assistant_index}
        pending_assistant_index = None
        pending_tool_call_ids = set()
        
        for i, msg in enumerate(messages):
            role = msg.get("role")
            
            if role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    # Extract tool call IDs
                    tool_call_ids = set()
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            tool_id = tc.get("id")
                        elif hasattr(tc, "id"):
                            tool_id = tc.id
                        else:
                            tool_id = None
                        if tool_id:
                            tool_call_ids.add(tool_id)
                    
                    if tool_call_ids:
                        pending_assistant_index = i
                        pending_tool_call_ids = tool_call_ids.copy()
                        assistant_tool_calls_map[i] = {}
                        # Map each tool_call_id to this assistant
                        for tool_id in tool_call_ids:
                            tool_call_to_assistant[tool_id] = i
                else:
                    # Assistant without tool_calls - clear pending state
                    pending_assistant_index = None
                    pending_tool_call_ids.clear()
                    
            elif role == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id and tool_call_id in tool_call_to_assistant:
                    # Valid tool message - record the pairing
                    assistant_idx = tool_call_to_assistant[tool_call_id]
                    if assistant_idx in assistant_tool_calls_map:
                        assistant_tool_calls_map[assistant_idx][tool_call_id] = i
                # Note: orphaned tool messages (without corresponding assistant) will be skipped
                
            elif role in ["user", "system"]:
                # New user/system message - clear pending state
                pending_assistant_index = None
                pending_tool_call_ids.clear()
        
        # Second pass: build validated messages
        validated_messages = []
        orphaned_tool_count = 0
        fixed_assistant_count = 0
        
        # Find the last assistant message index (might be in progress)
        last_assistant_index = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                last_assistant_index = i
                break
        
        for i, msg in enumerate(messages):
            role = msg.get("role")
            
            if role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    if i in assistant_tool_calls_map:
                        # Check if all tool_calls have corresponding tool messages
                        valid_tool_call_ids = assistant_tool_calls_map[i]
                        
                        # Filter tool_calls to only include those with corresponding tool messages
                        valid_tool_calls = []
                        for tc in tool_calls:
                            tool_id = None
                            if isinstance(tc, dict):
                                tool_id = tc.get("id")
                            elif hasattr(tc, "id"):
                                tool_id = tc.id
                            
                            if tool_id and tool_id in valid_tool_call_ids:
                                valid_tool_calls.append(tc)
                        
                        if valid_tool_calls:
                            # Some tool_calls are valid - keep message with only valid tool_calls
                            msg_copy = msg.copy()
                            msg_copy["tool_calls"] = valid_tool_calls
                            validated_messages.append(msg_copy)
                            
                            # Check if we removed any tool_calls
                            if len(valid_tool_calls) < len(tool_calls):
                                fixed_assistant_count += 1
                                logger.warning(
                                    f"Fixed assistant message at index {i}: "
                                    f"removed {len(tool_calls) - len(valid_tool_calls)} orphaned tool_call(s). "
                                    f"Original tool_calls: {len(tool_calls)}, "
                                    f"Valid tool_calls: {len(valid_tool_calls)}"
                                )
                        else:
                            # All tool_calls currently orphaned (no tool outputs recorded yet)
                            if i == last_assistant_index:
                                # Keep the message as-is (tool outputs may arrive in this step)
                                validated_messages.append(msg)
                                logger.debug(
                                    f"Keeping last assistant message at index {i} with pending tool_calls "
                                    f"(awaiting tool execution outputs)"
                                )
                            else:
                                # Delete the entire assistant message
                                fixed_assistant_count += 1
                                logger.warning(
                                    f"Removed assistant message at index {i}: "
                                    f"all tool_calls are orphaned (no corresponding tool messages found). "
                                    f"Message deleted."
                                )
                    else:
                        # Assistant message with tool_calls but not in map (no valid tool_call_ids or no tool messages)
                        # If this is the last assistant message, it might be in progress - keep it
                        if i == last_assistant_index:
                            # Keep the message as-is (tool messages might be added later)
                            validated_messages.append(msg)
                            logger.debug(
                                f"Keeping last assistant message at index {i} with tool_calls "
                                f"(might be in progress, tool messages will be added later)"
                            )
                        else:
                            # Delete the entire assistant message
                            fixed_assistant_count += 1
                            logger.warning(
                                f"Removed assistant message at index {i}: "
                                f"has tool_calls but no corresponding tool messages found. "
                                f"Message deleted."
                            )
                else:
                    # Assistant without tool_calls - keep as is
                    validated_messages.append(msg)
                    
            elif role == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id and tool_call_id in tool_call_to_assistant:
                    # Valid tool message - it has a corresponding assistant message
                    assistant_idx = tool_call_to_assistant[tool_call_id]
                    if assistant_idx in assistant_tool_calls_map:
                        if tool_call_id in assistant_tool_calls_map[assistant_idx]:
                            # This tool message is paired with an assistant message
                            validated_messages.append(msg)
                        else:
                            # Should not happen, but skip just in case
                            orphaned_tool_count += 1
                            logger.warning(
                                f"Found orphaned tool message at index {i}: "
                                f"tool_call_id={tool_call_id} has assistant but not in valid pairs. "
                                f"Message will be skipped."
                            )
                    else:
                        orphaned_tool_count += 1
                        logger.warning(
                            f"Found orphaned tool message at index {i}: "
                            f"tool_call_id={tool_call_id} has no valid assistant mapping. "
                            f"Message will be skipped."
                        )
                else:
                    # Orphaned tool message - no corresponding assistant message
                    orphaned_tool_count += 1
                    logger.warning(
                        f"Found orphaned tool message at index {i}: "
                        f"tool_call_id={tool_call_id} has no corresponding assistant message. "
                        f"Message will be skipped."
                    )
                    
            else:
                # system, user, or other roles - always valid
                validated_messages.append(msg)
        
        # Log summary if we fixed any issues
        if orphaned_tool_count > 0 or fixed_assistant_count > 0:
            logger.warning(
                f"Fixed message sequence: "
                f"removed {orphaned_tool_count} orphaned tool message(s), "
                f"fixed {fixed_assistant_count} assistant message(s) with orphaned tool_calls. "
                f"Original message count: {len(messages)}, "
                f"Validated message count: {len(validated_messages)}"
            )
        
        return validated_messages

    @log_execution_time(log_level="INFO")
    @retry(
        wait=wait_random_exponential(min=1, max=20),
        stop=stop_after_attempt(3),
    )
    async def ask_tool(
        self,
        messages: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        timeout: int = 30,
        tools: Optional[List[dict]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        temperature: Optional[float] = None,
        stream: bool = False,
        on_delta: Optional[Callable[[Any], Awaitable[None]]] = None,
        **kwargs,
    ):
        """
        Ask LLM using functions/tools and return the response.

        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            timeout: Request timeout in seconds
            tools: List of tools to use
            tool_choice: Tool choice strategy
            temperature: Sampling temperature for the response
            **kwargs: Additional completion arguments

        Returns:
            ChatCompletionMessage: The model's response

        Raises:
            ValueError: If tools, tool_choice, or messages are invalid
            OpenAIError: If API call fails after retries
        """
        try:
            if tool_choice not in ["none", "auto", "required"]:
                raise ValueError(f"Invalid tool_choice: {tool_choice}")

            # Format messages
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                messages = system_msgs + self.format_messages(messages)
            else:
                messages = self.format_messages(messages)
                
            # Validate and fix message sequence before sending to API
            messages = self._validate_and_fix_messages(messages)

            # Log message sequence for debugging (only if there are tool messages)
            has_tool_messages = any(msg.get("role") == "tool" for msg in messages)
            if has_tool_messages:
                logger.debug(
                    f"Message sequence before API call (total: {len(messages)}): "
                    f"{[{'role': m.get('role'), 'has_tool_calls': bool(m.get('tool_calls')), 'tool_call_id': m.get('tool_call_id')} for m in messages]}"
                )

            # Validate tools if provided
            if tools:
                for tool in tools:
                    if not isinstance(tool, dict) or "type" not in tool:
                        raise ValueError("Each tool must be a dict with 'type' field")

            stream_mode = stream or on_delta is not None
            if not stream_mode:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature or self.temperature,
                    max_tokens=self.max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                    timeout=timeout,
                    **kwargs,
                )

                if not response.choices or not response.choices[0].message:
                    logger.error(f"Invalid or empty response from LLM: {response}")
                    raise ValueError("Invalid or empty response from LLM")

                return response.choices[0].message

            # Streaming branch
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                timeout=timeout,
                stream=True,
                **kwargs,
            )

            content_parts: List[str] = []
            tool_call_builders: Dict[int, Dict[str, Any]] = {}

            async for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                # 先处理文本增量
                if delta.content:
                    content_parts.append(delta.content)
                    if on_delta:
                        await on_delta(delta.content)

                # 再处理工具调用增量
                if delta.tool_calls:
                    for tool_delta in delta.tool_calls:
                        index = getattr(tool_delta, "index", 0) or 0
                        builder = tool_call_builders.setdefault(
                            index,
                            {
                                "id": None,
                                "type": "function",
                                "function": {"name": None, "arguments": ""},
                            },
                        )

                        if tool_delta.id:
                            builder["id"] = tool_delta.id

                        if tool_delta.function:
                            if tool_delta.function.name:
                                builder["function"]["name"] = tool_delta.function.name
                            if tool_delta.function.arguments:
                                builder["function"]["arguments"] += (
                                    tool_delta.function.arguments
                                )

                        if on_delta:
                            await on_delta(
                                {
                                    "type": "tool_call_delta",
                                    "index": index,
                                    "tool_call_id": builder["id"],
                                    "function": builder["function"],
                                    "raw_delta": tool_delta.function
                                    and tool_delta.function.arguments,
                                }
                            )

                # 最后再根据 finish_reason 判断是否结束
                if choice.finish_reason is not None:
                    break

            content = "".join(content_parts).strip() or None
            tool_calls: List[ToolCall] = []

            for index in sorted(tool_call_builders.keys()):
                builder = tool_call_builders[index]
                func = builder["function"]
                if not func["name"]:
                    continue
                tool_calls.append(
                    ToolCall(
                        id=builder["id"] or f"call_{index}",
                        function=Function(
                            name=func["name"],
                            arguments=func["arguments"] or "{}",
                        ),
                    )
                )

            if on_delta:
                await on_delta({"type": "stream_end"})

            return _StreamingChatMessage(content=content, tool_calls=tool_calls or None)

        except ValueError as ve:
            logger.error(f"Validation error in ask_tool: {ve}")
            raise
        except OpenAIError as oe:
            if isinstance(oe, AuthenticationError):
                logger.error("Authentication failed. Check API key.")
            elif isinstance(oe, RateLimitError):
                logger.error("Rate limit exceeded. Consider increasing retry attempts.")
            elif isinstance(oe, APIError):
                error_message = str(oe)
                logger.error(f"API error: {oe}")
                
                # If it's the tool message error, log detailed message info
                if "tool" in error_message.lower() and "tool_calls" in error_message.lower():
                    logger.error(
                        f"Tool message validation error detected. "
                        f"Message count: {len(messages)}, "
                        f"Message roles: {[m.get('role') for m in messages]}, "
                        f"Tool messages: {[i for i, m in enumerate(messages) if m.get('role') == 'tool']}, "
                        f"Assistant messages with tool_calls: {[i for i, m in enumerate(messages) if m.get('role') == 'assistant' and m.get('tool_calls')]}"
                    )
                    # Log full message details for debugging
                    for i, msg in enumerate(messages):
                        if msg.get("role") in ["assistant", "tool"]:
                            logger.debug(
                                f"Message {i}: role={msg.get('role')}, "
                                f"tool_calls={bool(msg.get('tool_calls'))}, "
                                f"tool_call_id={msg.get('tool_call_id')}, "
                                f"content_preview={str(msg.get('content', ''))[:50]}"
                            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask_tool: {e}", exc_info=True)
            raise


# Convenience function for backward compatibility
def get_llm(
    config_name: str = "openai",
    settings: Optional[LLMSettings] = None,
) -> LLM:
    """
    Get LLM instance (singleton per config).
    
    Args:
        config_name: Name of the config to use
        settings: Optional LLMSettings object
        
    Returns:
        LLM instance
    """
    return LLM.get_instance(config_name=config_name, settings=settings)


