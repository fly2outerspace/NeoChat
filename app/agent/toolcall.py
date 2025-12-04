import asyncio
import json
from typing import Any, AsyncIterator, Iterable, List, Literal

from pydantic import Field

from app.agent.react import ReActAgent
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import ExecutionEvent, ExecutionState, Message, ToolCall
from app.tool import CreateChatCompletion, Terminate, ToolCollection, ToolResult
from app.utils.enums import ToolName
from app.utils import get_current_time
from typing import Dict

TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            CreateChatCompletion(), Terminate()
        )
    )
    tool_choices: Literal["none", "auto", "required"] = "auto"
    special_tool_names: List[str] = Field(default_factory=lambda: [ToolName.TERMINATE])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    
    # Store tool results for access by flow adapters
    tool_results: Dict[str, ToolResult] = Field(default_factory=dict, description="Map of tool_call_id -> ToolResult")

    max_steps: int = 30

    def _chunk_content(self, text: str, chunk_size: int = 120) -> Iterable[str]:
        """Split long text into smaller chunks for streaming."""
        if not text:
            return []
        return (text[i : i + chunk_size] for i in range(0, len(text), chunk_size))

    def prepare_system_messages(self) -> list[Message]:
        """Prepare system messages for the agent"""
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        return [Message.system_message(self.system_prompt, created_at=current_time, visible_for_characters=self.visible_for_characters)]

    def prepare_messages(self) -> list[Message]:
        messages = []
        # Use underlying memory messages instead of the Memory object itself
        # to avoid yielding (field_name, value) tuples from the Pydantic model.
        messages.extend(self.messages)
        if self.next_step_prompt:
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            next_step_msg = Message.system_message(self.next_step_prompt, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters)
            messages += [next_step_msg]
        return messages

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        
        system_msgs = self.prepare_system_messages()
        messages = self.prepare_messages()
        # Get response with tool options
        response = await self.llm.ask_tool(
            messages=messages,
            system_msgs=system_msgs if system_msgs else None,
            tools=self.available_tools.to_params(),
            tool_choice=self.tool_choices,
        )
        self.tool_calls = response.tool_calls

        # # 阻止第一轮使用 terminate 工具
        # if self.current_step == 1 and self.tool_calls:
        #     original_count = len(self.tool_calls)
        #     self.tool_calls = [
        #         call for call in self.tool_calls 
        #         if call.function.name.lower() != "terminate"
        #     ]
        #     if len(self.tool_calls) != original_count:
        #         logger.info(f" Filtered out terminate tool in first step (step {self.current_step})")

        # Log response info
        logger.info(f" {self.name}'s ask_tool response: {response.content}")
        logger.info(
            f" {self.name} selected {len(self.tool_calls) if self.tool_calls else 0} tools to use"
        )
        if self.tool_calls:
            logger.info(
                f" Tools being prepared: {[call.function.name for call in self.tool_calls]}"
            )

        try:
            # Handle different tool_choices modes
            if self.tool_choices == "none":
                if response.tool_calls:
                    logger.warning(
                        f"{self.name} asked to use tools when they weren't available!"
                    )
                if response.content:
                    current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
                    self.memory.add_message(Message.assistant_message(response.content, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters))
                    return True
                return False

            # Create and add assistant message
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls, speaker=self.name, created_at=current_time,
                    visible_for_characters=self.visible_for_characters
                )
                if self.tool_calls
                else Message.assistant_message(response.content, speaker=self.name, created_at=current_time,
                    visible_for_characters=self.visible_for_characters)
            )
            self.memory.add_message(assistant_msg)

            if self.tool_choices == "required" and not self.tool_calls:
                #TODO: 如果工具调用失败，则?
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == "auto" and not self.tool_calls:
                return bool(response.content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"Error: The {self.name}'s thinking process hit a snag: {e}")
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}", speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters
                )
            )
            return False
    
    async def think_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Think with streaming events"""
        system_msgs = self.prepare_system_messages()
        messages = self.prepare_messages()
        
        # Stream response tokens via queue
        delta_queue: asyncio.Queue[Any] = asyncio.Queue()

        async def handle_delta(delta: Any):
            await delta_queue.put(delta)

        async def call_llm():
            try:
                return await self.llm.ask_tool(
                    messages=messages,
                    system_msgs=system_msgs if system_msgs else None,
                    tools=self.available_tools.to_params(),
                    tool_choice=self.tool_choices,
                    stream=True,
                    on_delta=handle_delta,
                )
            finally:
                await delta_queue.put({"type": "stream_end"})

        llm_task = asyncio.create_task(call_llm())

        content_chunks: List[str] = []
        while True:
            delta = await delta_queue.get()
            if isinstance(delta, dict) and delta.get("type") == "stream_end":
                break
            if isinstance(delta, str):
                content_chunks.append(delta)
                yield ExecutionEvent(
                    type="token",
                    content=delta,
                    step=self.current_step,
                    total_steps=self.max_steps,
                )
            elif isinstance(delta, dict) and delta.get("type") == "tool_call_delta":
                message_type = delta.get("function", {}).get("name")
                if message_type:
                    yield ExecutionEvent(
                        type="tool_status",
                        content=f"🛠️ 正在准备工具: {message_type}",
                        step=self.current_step,
                        total_steps=self.max_steps,
                    )

        response = await llm_task
        self.tool_calls = response.tool_calls

        # # 阻止第一轮使用 terminate 工具
        # if self.current_step == 1 and self.tool_calls:
        #     original_count = len(self.tool_calls)
        #     self.tool_calls = [
        #         call for call in self.tool_calls 
        #         if call.function.name.lower() != "terminate"
        #     ]
        #     if len(self.tool_calls) != original_count:
        #         logger.info(f" Filtered out terminate tool in first step (step {self.current_step})")

        # Log response info
        logger.info(f" {self.name}'s ask_tool response: {response.content}")
        logger.info(
            f" {self.name} selected {len(self.tool_calls) if self.tool_calls else 0} tools to use"
        )
        
        # Ensure we have textual content if no tool calls (even if streaming callback provided)
        if not response.content and content_chunks and not self.tool_calls:
            response.content = "".join(content_chunks).strip()
        
        # Normalize None to empty string for easier checking
        if response.content is None:
            response.content = ""
        
        # Emit tool selection status
        if self.tool_calls:
            tool_names = [call.function.name for call in self.tool_calls]
            yield ExecutionEvent(
                type="tool_status",
                content=f"🔧 准备调用工具: {', '.join(tool_names)}",
                step=self.current_step,
                total_steps=self.max_steps,
                metadata={"tool_names": tool_names},
            )
            logger.info(f" Tools being prepared: {tool_names}")

        try:
            # Handle different tool_choices modes
            if self.tool_choices == "none":
                if response.tool_calls:
                    logger.warning(
                        f"{self.name} asked to use tools when they weren't available!"
                    )
                if response.content:
                    current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
                    self.memory.add_message(Message.assistant_message(response.content, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters))
                    yield ExecutionEvent(
                        type="tool_status",
                        content="✅ 思考完成",
                        step=self.current_step,
                        total_steps=self.max_steps,
                        metadata={"should_act": True},
                    )
                    return
                yield ExecutionEvent(
                    type="tool_status",
                    content="✅ 思考完成",
                    step=self.current_step,
                    total_steps=self.max_steps,
                    metadata={"should_act": False},
                )
                return

            # Check if we have no content and no tool calls - skip message creation and terminate
            if not response.content and not self.tool_calls:
                logger.info(f" {self.name} has no content and no tool calls - skipping message and terminating")
                yield ExecutionEvent(
                    type="tool_status",
                    content="✅ 思考完成（无输出）",
                    step=self.current_step,
                    total_steps=self.max_steps,
                    metadata={"should_act": False},
                )
                # Set state to FINISHED to terminate the agent
                self.state = ExecutionState.FINISHED
                return

            # Create and add assistant message
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls, speaker=self.name, created_at=current_time,
                    visible_for_characters=self.visible_for_characters
                )
                if self.tool_calls
                else Message.assistant_message(response.content, speaker=self.name, created_at=current_time,
                    visible_for_characters=self.visible_for_characters)
            )
            self.memory.add_message(assistant_msg)

            if self.tool_choices == "required" and not self.tool_calls:
                yield ExecutionEvent(
                    type="tool_status",
                    content="⚠️ 需要工具调用但未提供",
                    step=self.current_step,
                    total_steps=self.max_steps,
                    metadata={"should_act": True},
                )
                return

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == "auto" and not self.tool_calls:
                yield ExecutionEvent(
                    type="tool_status",
                    content="✅ 思考完成",
                    step=self.current_step,
                    total_steps=self.max_steps,
                    metadata={"should_act": bool(response.content)},
                )
                return

            yield ExecutionEvent(
                type="tool_status",
                content="✅ 思考完成",
                step=self.current_step,
                total_steps=self.max_steps,
                metadata={"should_act": bool(self.tool_calls)},
            )
        except Exception as e:
            logger.error(f"Error: The {self.name}'s thinking process hit a snag: {e}")
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}", speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters
                )
            )
            yield ExecutionEvent(
                type="error",
                content=f"思考过程出错: {str(e)}",
                step=self.current_step,
                total_steps=self.max_steps,
            )
            yield ExecutionEvent(
                type="tool_status",
                content="❌ 思考失败",
                step=self.current_step,
                total_steps=self.max_steps,
                metadata={"should_act": False},
            )

    async def handle_tool_result_stream(
        self, command: ToolCall, result: ToolResult
    ) -> AsyncIterator[ExecutionEvent]:
        """Handle tool result with streaming events"""
        # Store ToolResult for flow adapters to access
        self.tool_results[command.id] = result
        
        # Get text content for display
        normalized_result = str(result) or ""
        
        # Default implementation: accumulate result and add to memory
        logger.info(
            f" Tool '{command.function.name}' completed its mission!"
        )

        # Emit structured data if args exist
        if result.args:
            yield ExecutionEvent(
                type="tool_output",
                content=None,
                message_type=command.function.name,
                message_id=command.id,
                step=self.current_step,
                total_steps=self.max_steps,
                metadata={
                    "structured_data": result.args,
                    "result_type": "tool_result"
                }
            )

        # Add tool response to memory
        current_time = get_current_time()
        self.memory.add_message(
            Message.tool_message(
                content=normalized_result, tool_name=command.function.name, tool_call_id=command.id, created_at=current_time, visible_for_characters=self.visible_for_characters
            )
        )
        
        # Stream the tool output so frontend can display progress
        for chunk in self._chunk_content(normalized_result):
            yield ExecutionEvent(
                type="token",
                content=chunk,
                step=self.current_step,
                total_steps=self.max_steps,
                message_type=command.function.name,
                message_id=command.id,
            )

    async def act(self) -> str:
        """Execute tool calls and handle their results
        
        Note: This method is not used in practice as all subclasses override act_stream().
        It is kept as an abstract method implementation for interface compatibility.
        """
        if not self.tool_calls:
            if self.tool_choices == "required":
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return self.messages[-1].content or "No content or commands to execute"

        # Note: This method is not actually called as subclasses override act_stream()
        # Tool execution is handled in act_stream() via handle_tool_result_stream()
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            # Store result for compatibility (actual handling done in act_stream)
            self.tool_results[command.id] = result
            result_str = str(result)
            self.result += result_str
    
    async def act_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Execute tool calls with streaming events"""
        if not self.tool_calls:
            if self.tool_choices == "required":
                yield ExecutionEvent(
                    type="error",
                    content="错误: 需要工具调用但未提供",
                    step=self.current_step,
                    total_steps=self.max_steps,
                )
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return

        total_tools = len(self.tool_calls)
        for idx, command in enumerate(self.tool_calls):
            message_type = command.function.name
            
            # Emit tool start event
            yield ExecutionEvent(
                type="tool_status",
                content=f"🔧 正在执行工具: {message_type} ({idx + 1}/{total_tools})",
                step=self.current_step,
                total_steps=self.max_steps,
                message_type=message_type,
                message_id=command.id,
            )
            
            try:
                result = await self.execute_tool(command)
                
                # Emit tool completion event
                yield ExecutionEvent(
                    type="tool_status",
                    content=f"✅ 工具 {message_type} 执行完成",
                    step=self.current_step,
                    total_steps=self.max_steps,
                    message_type=message_type,
                    message_id=command.id,
                )
                
                # Handle tool result (may emit additional events)
                async for event in self.handle_tool_result_stream(command, result):
                    yield event
                    
            except Exception as e:
                # Emit tool error event
                yield ExecutionEvent(
                    type="error",
                    content=f"❌ 工具 {message_type} 执行失败: {str(e)}",
                    step=self.current_step,
                    total_steps=self.max_steps,
                    message_type=message_type,
                    message_id=command.id,
                )
                # Still call handle_tool_result to add error to memory
                error_result = ToolResult(error=f"Error: {str(e)}")
                async for event in self.handle_tool_result_stream(command, error_result):
                    yield event

    async def execute_tool(self, command: ToolCall) -> ToolResult:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return ToolResult(error="Error: Invalid command format")

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return ToolResult(error=f"Error: Unknown tool '{name}'")

        try:
            # Parse arguments
            args = json.loads(command.function.arguments or "{}")

            # Execute the tool
            logger.info(f" Activating tool: '{name}'...")
            result = await self.available_tools.execute(name=name, tool_input=args)

            # Ensure result is ToolResult (handle backward compatibility)
            if not isinstance(result, ToolResult):
                result = ToolResult.from_output(result)

            # Format result for display
            logger.info(
                f"{self.id}: observed output of cmd `{name}` executed:\n {str(result)}"
                if result
                else f"{self.id}: cmd `{name}` completed with no output"
            )

            # Handle special tools like `finish`
            await self._handle_special_tool(name=name, result=result)

            return result

        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f" Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return ToolResult(error=error_msg)
        except Exception as e:
            error_msg = f" Tool '{name}' encountered a problem: {str(e)}"
            logger.error(error_msg)
            return ToolResult(error=error_msg)

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Set agent state to finished
            logger.info(f" Special tool '{name}' has completed the task!")
            self.state = ExecutionState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]
