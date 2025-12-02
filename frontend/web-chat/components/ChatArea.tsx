'use client';

import { useState, useEffect, useRef } from 'react';
import { getConfig, getUserAvatar, getStreamingEnabled, getThemeSetting, getChatMode, saveChatMode, getImmersiveMode, getInnerThoughtEnabled, type ThemeId, type ChatMode } from '@/lib/config';
import { getSessionMessages, saveSessionMessages, createSession, setCurrentSessionId, getAllSessions, primeClientMessageCache, type Message, type ToolOutput } from '@/lib/sessions';
import { InputMode, INPUT_MODE_OPTIONS, getDefaultInputMode, InputModeCategory, getInputModesByCategory, getInputModeConfig } from '@/lib/enums';
import { useLocalStorageInput } from '@/lib/useLocalStorageInput';
import { getChatTheme, type ChatTheme } from '@/lib/themes';
import { listCharacters, type Character } from '@/lib/api/character';
import { fetchSessionTime } from '@/lib/api/sessionTime';

const INLINE_TOOL_NAMES = new Set(['send_telegram_message', 'speak_in_person']);
const TOOL_NAME_LABELS: Record<string, string> = {
  schedule_writer: '日程写入',
  schedule_reader: '日程查询',
  scenario_writer: '场景写入',
  scenario_reader: '场景查询',
  inner_thought: '内心想法',
  dialogue_history: '对话查询',
  web_search: '网络搜索',
  get_current_time: '获取时间',
  planning: '计划',
  create_chat_completion: '说话生成',
  terminate: '终止',
  relation: '关系变更',
};

const formatToolName = (name: string) => {
  const key = name?.toLowerCase();
  return TOOL_NAME_LABELS[key] || name || '工具输出';
};

// Format virtual time for display (format: 'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DD HH:MM')
const formatVirtualTime = (virtualTime?: string): string | null => {
  if (!virtualTime) return null;
  try {
    // Parse 'YYYY-MM-DD HH:MM:SS' format
    const date = new Date(virtualTime.replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) return null;
    // Format as 'YYYY-MM-DD HH:MM'
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hour}:${minute}`;
  } catch (e) {
    return null;
  }
};


interface ChatAreaProps {
  sessionId: string | null;
  onSessionCreated?: (sessionId: string) => void;
}

// 头像组件
function Avatar({ src, alt, isUser }: { src: string | null; alt: string; isUser: boolean }) {
  return (
    <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 overflow-hidden">
      {src ? (
        <img src={src} alt={alt} className="w-full h-full object-cover" />
      ) : (
        <div className="text-lg">
          {isUser ? '👤' : '🤖'}
        </div>
      )}
    </div>
  );
}

// 加载动画组件
function LoadingDots() {
  return (
    <div className="flex items-center gap-1">
      <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
      <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
      <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
    </div>
  );
}

// 消息气泡组件
interface MessageBubble {
  role: 'user' | 'assistant';
  content: string;
  isFirstLine: boolean;
  messageIndex: number;
  lineIndex: number;
}

// 将消息按换行符拆分成多个气泡
function splitMessageIntoBubbles(
  message: Message,
  messageIndex: number
): MessageBubble[] {
  // 如果是 speak_in_person，不分割，直接返回整个内容作为一个气泡
  if (message.toolName === 'speak_in_person') {
    if (!message.content.trim()) {
      return [];
    }
    return [{
      role: message.role,
      content: message.content,
      isFirstLine: true,
      messageIndex,
      lineIndex: 0,
    }];
  }
  
  // 对于 send_telegram_message 或其他消息，按换行符分割
  const lines = message.content.split('\n');
  // 过滤掉所有空行（trim 后为空的行），避免出现空气泡
  // 连续多个 \n 会被过滤掉，不会产生多个空气泡
  const nonEmptyLines = lines.filter((line) => line.trim() !== '');
  
  // 如果过滤后没有任何内容，返回一个空数组（不显示任何气泡）
  // 或者如果原消息就是空的，也返回空数组
  if (nonEmptyLines.length === 0) {
    return [];
  }
  
  // 重新映射索引，确保 isFirstLine 正确
  return nonEmptyLines.map((line, filteredIndex) => ({
    role: message.role,
    content: line,
    isFirstLine: filteredIndex === 0,
    messageIndex,
    lineIndex: filteredIndex,
  }));
}

export default function ChatArea({ sessionId, onSessionCreated }: ChatAreaProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  // Persist input to localStorage with session-specific key
  const inputKey = sessionId ? `chat_input_${sessionId}` : 'chat_input_default';
  const [input, setInput] = useLocalStorageInput<string>(inputKey, '');
  const [loading, setLoading] = useState(false);
  const [isWaitingResponse, setIsWaitingResponse] = useState(false);
  const [toolStatus, setToolStatus] = useState<string>('回复中...'); // 工具状态文本
  const [error, setError] = useState<string | null>(null);
  const [isFirstSession, setIsFirstSession] = useState<boolean>(false);
  const [isClient, setIsClient] = useState(false);
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [selectedCharacter, setSelectedCharacter] = useState<{
    character_id: string;
    name: string;
    roleplay_prompt: string | null;
  } | null>(null);
  // Map character_id to avatar URL
  const [characterAvatarMap, setCharacterAvatarMap] = useState<Map<string, string | null>>(new Map());
  // All characters list for dropdowns
  const [allCharacters, setAllCharacters] = useState<Character[]>([]);
  // Target character (single select) - replaces the role card selection in status bar
  const [targetCharacterId, setTargetCharacterId] = useState<string>('');
  // Participants (multi-select)
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  // Dropdown open states
  const [targetDropdownOpen, setTargetDropdownOpen] = useState(false);
  const [participantsDropdownOpen, setParticipantsDropdownOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<{
    model_id: string;
    name: string;
    provider: string;
    model: string;
    base_url: string;
    api_key: string | null;
    max_tokens: number;
    temperature: number;
    api_type: string;
  } | null>(null);
  const [inputMode, setInputMode] = useState<InputMode>(getDefaultInputMode());
  const [themeId, setThemeId] = useState<ThemeId>(() => getThemeSetting());
  const [chatTheme, setChatTheme] = useState<ChatTheme>(() => getChatTheme(getThemeSetting()));
  const [chatMode, setChatMode] = useState<ChatMode>(() => getChatMode());
  const [immersiveMode, setImmersiveMode] = useState<boolean>(() => getImmersiveMode());
  const [innerThoughtEnabled, setInnerThoughtEnabled] = useState<boolean>(() => getInnerThoughtEnabled());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const placeholderIndexRef = useRef<number | null>(null);
  const activeSessionRef = useRef<string | null>(sessionId);
  const [streamingEnabled, setStreamingEnabled] = useState<boolean>(true);
  const lastSaveTimeRef = useRef<number>(0);
  const toolOutputsRef = useRef<Record<number, ToolOutput[]>>({});
  const saveThrottleMs = 2000; // 每2秒最多保存一次，降低写频率

  // Get current input mode configuration
  const currentInputModeConfig = getInputModeConfig(inputMode) ?? INPUT_MODE_OPTIONS[0];
  const currentCategory = currentInputModeConfig.category;
  const isBasicMode = currentCategory === InputModeCategory.BASIC;
  const isExtendedMode = currentCategory === InputModeCategory.EXTENDED;
  const inputPlaceholder =
    currentInputModeConfig.placeholder || '输入你的内容，Enter 发送，Shift+Enter 换行';

  // 客户端检查：避免 hydration 错误
  useEffect(() => {
    setIsClient(true);
    const checkSessions = async () => {
      // 优先从数据库同步会话列表
      try {
        const { syncSessionsFromDatabase } = await import('@/lib/sessions');
        const dbSessions = await syncSessionsFromDatabase();
        setIsFirstSession(dbSessions.length === 0);
      } catch (err) {
        console.error('Failed to sync sessions from database:', err);
        // 失败时从 localStorage 检查
        const sessions = getAllSessions();
        setIsFirstSession(sessions.length === 0);
      }
    };
    checkSessions();
    
    // 监听存档切换事件，重新检查会话状态
    const handleArchiveSwitched = () => {
      setTimeout(checkSessions, 200); // 延迟检查，确保数据库已切换且 localStorage 已更新
    };
    window.addEventListener('archiveSwitched', handleArchiveSwitched);
    
    return () => {
      window.removeEventListener('archiveSwitched', handleArchiveSwitched);
    };
  }, []);

  // 加载所有角色信息，创建 character_id 到头像的映射
  useEffect(() => {
    const loadCharacters = async () => {
      try {
        const characters = await listCharacters();
        setAllCharacters(characters);
        const avatarMap = new Map<string, string | null>();
        characters.forEach((char: Character) => {
          avatarMap.set(char.character_id, char.avatar);
        });
        setCharacterAvatarMap(avatarMap);
      } catch (err) {
        console.error('Failed to load characters:', err);
      }
    };
    loadCharacters();

    // 监听 localStorage 清空事件，重新加载角色列表
    const handleLocalStorageCleared = () => {
      loadCharacters();
      // 清空选中的角色、参与者和模型（因为 localStorage 已被清空）
      setSelectedCharacter(null);
      setTargetCharacterId('');
      setParticipantIds([]);
      setSelectedModel(null);
    };

    // 监听角色列表更新事件（当角色被删除或创建时）
    const handleCharactersReload = () => {
      loadCharacters();
    };

    window.addEventListener('localStorageCleared', handleLocalStorageCleared);
    window.addEventListener('charactersReloaded', handleCharactersReload);
    return () => {
      window.removeEventListener('localStorageCleared', handleLocalStorageCleared);
      window.removeEventListener('charactersReloaded', handleCharactersReload);
    };
  }, []);

  // 当角色列表更新时，过滤掉参与者列表中已删除的角色ID
  useEffect(() => {
    const validCharacterIds = new Set(allCharacters.map(c => c.character_id));
    setParticipantIds(prev => {
      // 保留'user'和仍然存在的角色ID
      const filtered = prev.filter(id => id === 'user' || validCharacterIds.has(id));
      // 如果列表发生变化，更新localStorage
      if (filtered.length !== prev.length || filtered.some((id, idx) => id !== prev[idx])) {
        localStorage.setItem('selected_participants', JSON.stringify(filtered));
        return filtered;
      }
      return prev;
    });
  }, [allCharacters]);

  // 加载头像和角色信息
  useEffect(() => {
    setUserAvatar(getUserAvatar());
    setStreamingEnabled(getStreamingEnabled());
    setImmersiveMode(getImmersiveMode());
    setInnerThoughtEnabled(getInnerThoughtEnabled());
    const currentThemeId = getThemeSetting();
    setThemeId(currentThemeId);
    setChatTheme(getChatTheme(currentThemeId));
    
    // 加载选中的角色信息
    const storedCharacter = localStorage.getItem('selected_character');
    if (storedCharacter) {
      try {
        const characterInfo = JSON.parse(storedCharacter);
        setSelectedCharacter(characterInfo);
        setTargetCharacterId(characterInfo.character_id);
      } catch (e) {
        console.error('Failed to parse stored character:', e);
      }
    }
    
    // 加载参与者列表
    const storedParticipants = localStorage.getItem('selected_participants');
    if (storedParticipants) {
      try {
        const participantIds = JSON.parse(storedParticipants);
        setParticipantIds(participantIds);
      } catch (e) {
        console.error('Failed to parse stored participants:', e);
      }
    }
    
    // 加载选中的模型信息
    const storedModel = localStorage.getItem('selected_model');
    if (storedModel) {
      try {
        const modelInfo = JSON.parse(storedModel);
        setSelectedModel(modelInfo);
      } catch (e) {
        console.error('Failed to parse stored model:', e);
      }
    }
    
    // 监听自定义事件（当用户在设置页面更新头像时）
    const handleAvatarUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ type: 'user' | 'ai'; avatar: string | null }>;
      if (customEvent.detail.type === 'user') {
        setUserAvatar(customEvent.detail.avatar);
      }
      // 不再处理 AI 头像更新，因为现在使用 characterAvatarMap
    };
    
    // 监听角色更新事件
    const handleCharacterUpdate = async (e: Event) => {
      const customEvent = e as CustomEvent<{
        character_id: string;
        name: string;
        roleplay_prompt: string | null;
      } | null>;
      setSelectedCharacter(customEvent.detail);
      if (customEvent.detail) {
        setTargetCharacterId(customEvent.detail.character_id);
      } else {
        setTargetCharacterId('');
      }
      
      // 重新加载角色列表以更新头像映射（角色头像可能已更新）
      try {
        const characters = await listCharacters();
        setAllCharacters(characters);
        const avatarMap = new Map<string, string | null>();
        characters.forEach((char: Character) => {
          avatarMap.set(char.character_id, char.avatar);
        });
        setCharacterAvatarMap(avatarMap);
      } catch (err) {
        console.error('Failed to reload characters after update:', err);
      }
    };
    
    // 监听模型更新事件
    const handleModelUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{
        model_id: string;
        name: string;
        provider: string;
        model: string;
        base_url: string;
        api_key: string | null;
        max_tokens: number;
        temperature: number;
        api_type: string;
      } | null>;
      setSelectedModel(customEvent.detail);
    };
    
    // 监听流式设置更新事件
    const handleStreamingUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ enabled: boolean }>;
      setStreamingEnabled(customEvent.detail.enabled);
    };
    
    // 监听聊天模式更新事件
    const handleChatModeUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ mode: ChatMode }>;
      setChatMode(customEvent.detail.mode);
    };
    
    // 监听沉浸模式更新事件
    const handleImmersiveModeUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ enabled: boolean }>;
      setImmersiveMode(customEvent.detail.enabled);
    };
    
    // 监听内心想法设置更新事件
    const handleInnerThoughtEnabledUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ enabled: boolean }>;
      setInnerThoughtEnabled(customEvent.detail.enabled);
    };
    
    window.addEventListener('avatarUpdated', handleAvatarUpdate);
    window.addEventListener('characterUpdated', handleCharacterUpdate);
    window.addEventListener('modelUpdated', handleModelUpdate);
    window.addEventListener('streamingSettingUpdated', handleStreamingUpdate);
    window.addEventListener('chatModeUpdated', handleChatModeUpdate);
    window.addEventListener('immersiveModeUpdated', handleImmersiveModeUpdate);
    window.addEventListener('innerThoughtEnabledUpdated', handleInnerThoughtEnabledUpdate);
    const handleThemeUpdated = (e: Event) => {
      const customEvent = e as CustomEvent<{ themeId: ThemeId }>;
      setThemeId(customEvent.detail.themeId);
      setChatTheme(getChatTheme(customEvent.detail.themeId));
    };
    window.addEventListener('themeUpdated', handleThemeUpdated);

    return () => {
      window.removeEventListener('avatarUpdated', handleAvatarUpdate);
      window.removeEventListener('characterUpdated', handleCharacterUpdate);
      window.removeEventListener('modelUpdated', handleModelUpdate);
      window.removeEventListener('streamingSettingUpdated', handleStreamingUpdate);
      window.removeEventListener('chatModeUpdated', handleChatModeUpdate);
      window.removeEventListener('immersiveModeUpdated', handleImmersiveModeUpdate);
      window.removeEventListener('innerThoughtEnabledUpdated', handleInnerThoughtEnabledUpdate);
      window.removeEventListener('themeUpdated', handleThemeUpdated);
    };
  }, []);

  // 当切换会话时，从数据库加载所有消息进行展示
  useEffect(() => {
    if (sessionId) {
      // 优先从数据库加载所有消息
      import('@/lib/api/frontendMessages').then(({ getFrontendMessages }) => {
        getFrontendMessages(sessionId)
          .then((dbMessages) => {
            if (dbMessages && dbMessages.length > 0) {
              // Convert database messages (flat list) back to frontend format (grouped)
              // Group tool outputs with their corresponding text messages
              const frontendMessages: Message[] = [];
              const toolOutputsByText: Map<number, ToolOutput[]> = new Map(); // index -> toolOutputs
              
              dbMessages.forEach((dbMsg) => {
                primeClientMessageCache(sessionId, {
                  client_message_id: dbMsg.client_message_id,
                  id: dbMsg.id,
                  content: dbMsg.content || '',
                  tool_name: dbMsg.tool_name || undefined,
                });
                if (dbMsg.message_kind === 'tool_output') {
                  // Tool output message - collect it for the next text message
                  const toolOutput: ToolOutput = {
                    toolName: dbMsg.tool_name || '',
                    content: dbMsg.content,
                    toolCallId: dbMsg.tool_call_id,
                  };
                  
                  // Find the next text message index to attach this tool output
                  const nextTextIndex = frontendMessages.length;
                  if (!toolOutputsByText.has(nextTextIndex)) {
                    toolOutputsByText.set(nextTextIndex, []);
                  }
                  toolOutputsByText.get(nextTextIndex)!.push(toolOutput);
                } else {
                  // Text message - create a frontend message
                  const toolOutputs = toolOutputsByText.get(frontendMessages.length);
                  frontendMessages.push({
                    role: dbMsg.role as 'user' | 'assistant',
                    content: dbMsg.content,
                    toolOutputs: toolOutputs && toolOutputs.length > 0 ? toolOutputs : undefined,
                    toolName: dbMsg.tool_name,
                    inputMode: dbMsg.input_mode,
                    character_id: dbMsg.character_id,
                    clientMessageId: dbMsg.client_message_id, // Preserve client_message_id from database
                    virtualTime: dbMsg.created_at, // Load virtual time from database (created_at is virtual time)
                  });
                }
              });
              
              setMessages(frontendMessages);
              // 同步到 localStorage（用于离线访问）
              window.localStorage.setItem(`neochat_messages_${sessionId}`, JSON.stringify(frontendMessages));
            } else {
              // 如果数据库没有消息，从 localStorage 加载
              const storedMessages = getSessionMessages(sessionId);
              setMessages(storedMessages);
            }
            setError(null);
          })
          .catch((err) => {
            console.error('Failed to load messages from database:', err);
            // 失败时从 localStorage 加载
            const storedMessages = getSessionMessages(sessionId);
            setMessages(storedMessages);
            setError(null);
          });
      }).catch((err) => {
        console.error('Failed to import frontendMessages API:', err);
        // 失败时从 localStorage 加载
        const storedMessages = getSessionMessages(sessionId);
        setMessages(storedMessages);
        setError(null);
      });
    } else {
      setMessages([]);
    }
  }, [sessionId]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 记录当前 session，便于在流式过程中判断是否需要更新
  useEffect(() => {
    activeSessionRef.current = sessionId;
    placeholderIndexRef.current = null;
  }, [sessionId]);

  // 切换会话或卸载时，中断未完成的流
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [sessionId]);

  const updateAssistantPlaceholder = (
    content: string,
    captureSnapshot = false,
    targetSessionId?: string | null,
    saveToStorage = false,
    toolName?: string
  ): Message[] | null => {
    if (!targetSessionId || activeSessionRef.current !== targetSessionId) {
      return null;
    }
    const placeholderIndex = placeholderIndexRef.current;
    if (placeholderIndex === null) {
      return null;
    }

    let snapshot: Message[] | null = null;
    setMessages((prev) => {
      if (placeholderIndex === null || placeholderIndex >= prev.length) {
        return prev;
      }
      const updated = [...prev];
      const target = updated[placeholderIndex];
      // Get latest toolOutputs from ref to ensure we have the most up-to-date values
      const latestToolOutputs = toolOutputsRef.current[placeholderIndex] ?? target.toolOutputs;
      updated[placeholderIndex] = { 
        ...target, 
        content, 
        toolName: toolName || target.toolName,
        toolOutputs: latestToolOutputs,
        // Preserve clientMessageId if it exists
        clientMessageId: target.clientMessageId,
      };
      if (captureSnapshot) {
        snapshot = updated;
      }
      // 如果需要保存到 localStorage（流式更新时实时保存）
      if (saveToStorage && targetSessionId) {
        saveSessionMessages(targetSessionId, updated);
      }
      return updated;
    });
    return snapshot;
  };

  const updateAssistantToolOutputs = (
    toolOutputs: ToolOutput[],
    targetSessionId?: string | null,
    saveToStorage = false
  ): void => {
    if (!targetSessionId || activeSessionRef.current !== targetSessionId) {
      return;
    }
    const placeholderIndex = placeholderIndexRef.current;
    if (placeholderIndex === null) {
      return;
    }

    setMessages((prev) => {
      if (placeholderIndex === null || placeholderIndex >= prev.length) {
        return prev;
      }
      const updated = [...prev];
      const target = updated[placeholderIndex];
      updated[placeholderIndex] = { ...target, toolOutputs };

      if (saveToStorage && targetSessionId) {
        saveSessionMessages(targetSessionId, updated);
      }

      return updated;
    });
  };

  const shouldPersistNow = () => {
    const now = Date.now();
    if (now - lastSaveTimeRef.current > saveThrottleMs) {
      lastSaveTimeRef.current = now;
      return true;
    }
    return false;
  };

  const sendMessage = async (isSkip = false) => {
    // Skip mode: no input validation needed
    // Normal mode: require input
    if (!isSkip && (!input.trim() || !sessionId || loading)) return;
    if (isSkip && (!sessionId || loading)) return;

    const config = getConfig();
    const currentSessionId = sessionId!; // Already checked above
    
    // Prepare user message
    const userInput = isSkip ? 'skip' : input.trim();
    const messageInputMode = isSkip ? InputMode.SKIP : inputMode;
    // Generate stable client_message_id for user message based on session and message index
    // Use messages.length as index to ensure stable ID (won't change on re-save)
    const userMessageId = `user_${currentSessionId}_${messages.length}`;
    
    // Get virtual time for user message
    let userVirtualTime: string | undefined = undefined;
    try {
      const timeInfo = await fetchSessionTime(currentSessionId);
      userVirtualTime = timeInfo.current_virtual_time;
    } catch (err) {
      console.error('Failed to fetch virtual time for user message:', err);
      // Continue without virtual time if fetch fails
    }
    
    const newUserMessage: Message = { 
      role: 'user', 
      content: userInput,
      inputMode: messageInputMode,
      clientMessageId: userMessageId,
      virtualTime: userVirtualTime, // Save virtual time when user sends message
    };

    // 保存发送前的消息状态（用于失败时回滚）
    const previousMessages = [...messages];

    // 先更新本地状态（乐观更新）
    const updatedUserMessages = [...messages, newUserMessage];
    setMessages(updatedUserMessages);
    saveSessionMessages(currentSessionId, updatedUserMessages);

    if (!isSkip) {
      setInput(''); // Clear input after sending (only for normal mode)
    }

    setLoading(true);
    setError(null);
    setIsWaitingResponse(true); // 显示等待动画
    setToolStatus('回复中...'); // 重置工具状态

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      // 根据设置决定是否使用流式输出
      {
        const showLiveUpdates = streamingEnabled;
        let streamedContent = '';
        let finalContentBuffer = '';
        let hasAddedPlaceholder = false; // 标记是否已添加占位消息
        let hasExternalToolOutput = false;
        const stagedToolOutputs: ToolOutput[] = [];
        let currentInlineToolName: string | undefined = undefined; // Track current inline tool name
        let currentTextMessageId: string | undefined = undefined; // Track message_id for text message

        const ensureAssistantPlaceholder = (messageId?: string) => {
          if (!showLiveUpdates || hasAddedPlaceholder) {
            if (messageId) {
              currentTextMessageId = messageId;
            }
            return;
          }
          hasAddedPlaceholder = true;
          setIsWaitingResponse(false); // 隐藏等待动画
          const assistantPlaceholder: Message = { 
            role: 'assistant', 
            content: '', 
            toolOutputs: [],
            character_id: selectedCharacter?.character_id, // Save character_id for this message
            clientMessageId: messageId // Save message_id from backend
          };
          if (messageId) {
            currentTextMessageId = messageId;
          }
          const optimisticMessages = [...updatedUserMessages, assistantPlaceholder];
          setMessages(optimisticMessages);
          placeholderIndexRef.current = optimisticMessages.length - 1;
          if (placeholderIndexRef.current !== null) {
            toolOutputsRef.current[placeholderIndexRef.current] = [];
          }
        };

        const appendToolOutput = (
          toolName: string,
          toolCallId: string | undefined,
          chunk: string
        ) => {
          if (showLiveUpdates) {
            const placeholderIndex = placeholderIndexRef.current;
            if (placeholderIndex === null) return;
            const outputs = toolOutputsRef.current[placeholderIndex] ?? [];
            if (outputs.length > 0) {
              const last = outputs[outputs.length - 1];
              if (last.toolName === toolName && last.toolCallId === toolCallId) {
                last.content += chunk;
              } else {
                outputs.push({ toolName, toolCallId, content: chunk });
              }
            } else {
              outputs.push({ toolName, toolCallId, content: chunk });
            }
            toolOutputsRef.current[placeholderIndex] = [...outputs];
          } else {
            if (stagedToolOutputs.length > 0) {
              const last = stagedToolOutputs[stagedToolOutputs.length - 1];
              if (last.toolName === toolName && last.toolCallId === toolCallId) {
                last.content += chunk;
              } else {
                stagedToolOutputs.push({ toolName, toolCallId, content: chunk });
              }
            } else {
              stagedToolOutputs.push({ toolName, toolCallId, content: chunk });
            }
          }
        };

        // 根据聊天模式选择端点
        const endpoint = chatMode === 'flow' 
          ? `${config.baseUrl}/v1/flow/completions`
          : `${config.baseUrl}/v1/chat/completions`;
        
        const requestBody: any = {
          user_input: userInput,
          input_mode: messageInputMode,
          stream: true,
          session_id: currentSessionId,
          ...(selectedCharacter && {
            character: {
              character_id: selectedCharacter.character_id,
              name: selectedCharacter.name,
              roleplay_prompt: selectedCharacter.roleplay_prompt,
            },
          }),
          // Add participants field (use selected participants, or empty array if none)
          // Convert 'user' to 'user_{session_id}' format
          ...(participantIds.length > 0 && {
            participants: participantIds.map(id => 
              id === 'user' ? `user_${currentSessionId}` : id
            ),
          }),
          ...(selectedModel && {
            model_info: {
              model_id: selectedModel.model_id,
              name: selectedModel.name,
              provider: selectedModel.provider,
              model: selectedModel.model,
              base_url: selectedModel.base_url,
              api_key: selectedModel.api_key,
              max_tokens: selectedModel.max_tokens,
              temperature: selectedModel.temperature,
              api_type: selectedModel.api_type,
            },
          }),
        };
        
        // Flow 模式需要添加 flow_type
        if (chatMode === 'flow') {
          requestBody.flow_type = 'character';
        }
        
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
          },
          body: JSON.stringify(requestBody),
          signal: controller.signal,
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`HTTP ${res.status}: ${text}`);
        }

        if (!res.body) {
          throw new Error('当前浏览器不支持流式输出');
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let finished = false;

        const handleEvent = (rawEvent: string): boolean => {
          const trimmed = rawEvent.trim();
          if (!trimmed.startsWith('data:')) {
            return false;
          }
          const payload = trimmed.replace(/^data:\s*/, '');
          if (!payload) {
            return false;
          }
          if (payload === '[DONE]') {
            return true;
          }

          try {
            const chunk = JSON.parse(payload);
            const choice = chunk?.choices?.[0];
            const delta = choice?.delta;
            const toolEvent = delta?.tool_event;
            const toolName = typeof toolEvent?.message_type === 'string' ? toolEvent.message_type : null;
            
            // Handle tool_status updates
            const toolStatusUpdate = delta?.tool_status;
            if (typeof toolStatusUpdate === 'string') {
              setToolStatus(toolStatusUpdate);
              // Keep waiting animation visible when tool_status is present
              setIsWaitingResponse(true);
            }
            
            // Handle content updates (tokens)
            const deltaContent = delta?.content;
            if (typeof deltaContent === 'string') {
              // Get message_id from tool_event if available (for both tool outputs and text messages)
              const messageId = toolEvent?.message_id;
              ensureAssistantPlaceholder(messageId);
              
              const isExternalToolOutput =
                toolEvent?.type === 'tool_output' &&
                toolName &&
                !INLINE_TOOL_NAMES.has(toolName.toLowerCase());

              if (isExternalToolOutput && toolName) {
                hasExternalToolOutput = true;
                appendToolOutput(toolName, toolEvent?.message_id, deltaContent);
                if (showLiveUpdates && placeholderIndexRef.current !== null) {
                  const shouldSaveOutputs = shouldPersistNow();
                  updateAssistantToolOutputs(
                    toolOutputsRef.current[placeholderIndexRef.current] || [],
                    currentSessionId,
                    shouldSaveOutputs
                  );
                }
              } else {
                // This is inline tool output (send_telegram_message or speak_in_person)
                // Track the tool name for the first chunk
                if (!currentInlineToolName && toolName) {
                  currentInlineToolName = toolName;
                }
                // Update message_id if available
                if (messageId) {
                  currentTextMessageId = messageId;
                }
                finalContentBuffer += deltaContent;
                if (showLiveUpdates) {
                  streamedContent += deltaContent;
                  const shouldSaveContent = shouldPersistNow();
                  // Update placeholder with message_id
                  setMessages((prev) => {
                    if (placeholderIndexRef.current === null || placeholderIndexRef.current >= prev.length) {
                      return prev;
                    }
                    const updated = [...prev];
                    updated[placeholderIndexRef.current] = {
                      ...updated[placeholderIndexRef.current],
                      content: streamedContent,
                      toolName: currentInlineToolName,
                      clientMessageId: currentTextMessageId,
                    };
                    if (shouldSaveContent && currentSessionId) {
                      saveSessionMessages(currentSessionId, updated);
                    }
                    return updated;
                  });
                }
              }
            }
            
            if (choice?.finish_reason) {
              // Hide waiting animation when finished
              setIsWaitingResponse(false);
              return true;
            }
          } catch (parseError) {
            console.error('Failed to parse streaming chunk', parseError);
          }
          return false;
        };

        const processBuffer = (flush = false): boolean => {
          let doneProcessing = false;
          let separatorIndex: number;
          while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
            const rawEvent = buffer.slice(0, separatorIndex);
            buffer = buffer.slice(separatorIndex + 2);
            if (handleEvent(rawEvent)) {
              doneProcessing = true;
              break;
            }
          }
          if (!doneProcessing && flush && buffer.trim()) {
            doneProcessing = handleEvent(buffer);
            buffer = '';
          }
          return doneProcessing;
        };

        while (!finished) {
          try {
          const { value, done } = await reader.read();
          if (done) {
            buffer += decoder.decode();
            finished = processBuffer(true);
            break;
          }
          if (value) {
            buffer += decoder.decode(value, { stream: true });
            finished = processBuffer();
            }
          } catch (readError: any) {
            // 如果读取时被中断（AbortError），这是正常的，直接退出循环
            if (readError?.name === 'AbortError') {
              break;
            }
            // 其他错误重新抛出，由外层 catch 处理
            throw readError;
          }
        }

        const finalContent =
          finalContentBuffer || (hasExternalToolOutput ? '' : '[空响应]');

        // Get virtual time when streaming completes
        let virtualTime: string | undefined = undefined;
        try {
          const timeInfo = await fetchSessionTime(currentSessionId);
          virtualTime = timeInfo.current_virtual_time;
        } catch (err) {
          console.error('Failed to fetch virtual time:', err);
          // Continue without virtual time if fetch fails
        }

        if (showLiveUpdates) {
          const finalPlaceholderIndex = placeholderIndexRef.current;
          if (finalPlaceholderIndex !== null) {
            setMessages((prev) => {
              if (finalPlaceholderIndex === null || finalPlaceholderIndex >= prev.length) {
                return prev;
              }
              const updated = [...prev];
              const target = updated[finalPlaceholderIndex];
              const latestToolOutputs = toolOutputsRef.current[finalPlaceholderIndex] ?? target.toolOutputs;
              updated[finalPlaceholderIndex] = {
                ...target,
                content: finalContent,
                toolName: currentInlineToolName,
                toolOutputs: latestToolOutputs,
                clientMessageId: currentTextMessageId,
                virtualTime: virtualTime, // Update virtual time in React state
              };
              saveSessionMessages(currentSessionId, updated);
              return updated;
            });
          }
        } else {
          const assistantMessage: Message = {
            role: 'assistant',
            content: finalContent,
            toolOutputs: stagedToolOutputs.length ? stagedToolOutputs : undefined,
            toolName: currentInlineToolName,
            character_id: selectedCharacter?.character_id, // Save character_id for this message
            clientMessageId: currentTextMessageId, // Use message_id from backend
            virtualTime: virtualTime, // Save virtual time when streaming completes
          };
          const updatedMessages = [...updatedUserMessages, assistantMessage];
          setMessages(updatedMessages);
          saveSessionMessages(currentSessionId, updatedMessages);
        }
      }
    } catch (e: any) {
      const isAbortError = e?.name === 'AbortError';
      // 如果是 AbortError（用户切换会话或组件卸载导致的正常中断），不记录到控制台
      if (!isAbortError) {
        console.error(e);
        if (activeSessionRef.current === currentSessionId) {
        setError(e?.message || '请求失败');
        // 发送失败时，回滚到发送前的状态
        setMessages(previousMessages);
        saveSessionMessages(currentSessionId, previousMessages);
        }
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
      const placeholderIdx = placeholderIndexRef.current;
      placeholderIndexRef.current = null;
      if (placeholderIdx !== null) {
        delete toolOutputsRef.current[placeholderIdx];
      }
      setLoading(false);
      setIsWaitingResponse(false); // 确保隐藏等待动画
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading) {
        sendMessage();
      }
    }
  };

  // Handle target character selection
  const handleTargetCharacterChange = (characterId: string) => {
    setTargetCharacterId(characterId);
    const character = allCharacters.find(c => c.character_id === characterId);
    if (character) {
      const characterInfo = {
        character_id: character.character_id,
        name: character.name,
        roleplay_prompt: character.roleplay_prompt || null,
      };
      setSelectedCharacter(characterInfo);
      localStorage.setItem('selected_character', JSON.stringify(characterInfo));
      window.dispatchEvent(new CustomEvent('characterUpdated', { 
        detail: characterInfo 
      }));
      
      // 自动将目标添加到参与者列表中（如果还没有）
      setParticipantIds(prev => {
        if (!prev.includes(characterId)) {
          const newIds = [...prev, characterId];
          localStorage.setItem('selected_participants', JSON.stringify(newIds));
          return newIds;
        }
        return prev;
      });
    } else {
      setSelectedCharacter(null);
      localStorage.removeItem('selected_character');
      window.dispatchEvent(new CustomEvent('characterUpdated', { 
        detail: null 
      }));
    }
  };

  // Handle participants selection (multi-select)
  const handleParticipantToggle = (characterId: string) => {
    // 如果尝试取消的是目标角色，则不允许取消
    if (characterId === targetCharacterId && participantIds.includes(characterId)) {
      return; // 目标角色不能从参与者中移除
    }
    
    setParticipantIds(prev => {
      const newIds = prev.includes(characterId)
        ? prev.filter(id => id !== characterId)
        : [...prev, characterId];
      localStorage.setItem('selected_participants', JSON.stringify(newIds));
      return newIds;
    });
  };

  // Handle user participant toggle (special case)
  const handleUserParticipantToggle = () => {
    const userKey = 'user';
    setParticipantIds(prev => {
      const newIds = prev.includes(userKey)
        ? prev.filter(id => id !== userKey)
        : [...prev, userKey];
      localStorage.setItem('selected_participants', JSON.stringify(newIds));
      return newIds;
    });
  };

  // 确保目标角色始终在参与者列表中
  useEffect(() => {
    if (targetCharacterId) {
      setParticipantIds(prev => {
        if (!prev.includes(targetCharacterId)) {
          const newIds = [...prev, targetCharacterId];
          localStorage.setItem('selected_participants', JSON.stringify(newIds));
          return newIds;
        }
        return prev;
      });
    }
  }, [targetCharacterId]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.character-dropdown')) {
        setTargetDropdownOpen(false);
        setParticipantsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCreateFirstSession = () => {
    const newSession = createSession('第一个会话');
    setCurrentSessionId(newSession.id);
    setIsFirstSession(false);
    if (onSessionCreated) {
      onSessionCreated(newSession.id);
    }
  };

  if (!sessionId) {
    // 在客户端渲染之前，显示一个占位符以避免 hydration 错误
    if (!isClient) {
      return (
        <div className="h-full flex items-center justify-center">
          <div className="text-center text-slate-500">
            加载中...
          </div>
        </div>
      );
    }
    
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          {isFirstSession && (
            <button
              onClick={handleCreateFirstSession}
              className="px-6 py-3 rounded-md bg-sky-600 hover:bg-sky-700 text-white font-medium transition-colors shadow-lg"
            >
              创建会话
            </button>
          )}
          <div className="text-slate-500">
            {isFirstSession ? '点击上方按钮创建第一个会话' : '请选择一个会话或创建新会话'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-slate-900">
      {/* 消息区域 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-slate-500">
              <div className="text-lg mb-2">开始对话</div>
              <div className="text-sm">输入消息，按 Enter 发送</div>
            </div>
          </div>
        )}
        {messages.map((m, messageIdx) => {
          // Skip user messages with SKIP input mode (don't show bubble)
          if (m.role === 'user' && m.inputMode === InputMode.SKIP) {
            return null;
          }
          
          const isUser = m.role === 'user';
          
          // 沉浸模式过滤逻辑
          if (immersiveMode) {
            // 如果是assistant消息，且不是speak_in_person或send_telegram_message，则隐藏
            if (!isUser) {
              const isSpeakInPerson = m.toolName === 'speak_in_person';
              const isTelegram = m.toolName === 'send_telegram_message';
              if (!isSpeakInPerson && !isTelegram) {
                return null; // 隐藏assistant消息（除了speak_in_person和telegram）
              }
            }
            // user消息不受影响，继续显示
          }
          
          const bubbles = splitMessageIntoBubbles(m, messageIdx);
          // 工具输出过滤逻辑
          let toolOutputs: ToolOutput[] = [];
          if (!isUser && m.toolOutputs) {
            if (immersiveMode) {
              // 沉浸模式下，如果内心想法开关开启，则只显示内心想法
              if (innerThoughtEnabled) {
                toolOutputs = m.toolOutputs.filter(
                  (tool) => tool.toolName?.toLowerCase() === 'inner_thought'
                );
              }
              // 如果内心想法开关关闭，则不显示任何工具调用（toolOutputs保持为空数组）
            } else {
              // 非沉浸模式下，根据内心想法开关决定是否显示内心想法
              toolOutputs = m.toolOutputs.filter((tool) => {
                const isInnerThought = tool.toolName?.toLowerCase() === 'inner_thought';
                // 如果内心想法开关关闭，则隐藏内心想法
                if (isInnerThought && !innerThoughtEnabled) {
                  return false;
                }
                return true;
              });
            }
          }
          let avatarRendered = false;

          const renderAvatar = (shouldDisplay: boolean) => {
            if (shouldDisplay && !avatarRendered) {
              avatarRendered = true;
              let avatarSrc: string | null = null;
              let avatarAlt: string;
              
              if (isUser) {
                // User messages always use user avatar
                avatarSrc = userAvatar;
                avatarAlt = '用户头像';
              } else {
                // Assistant messages: use character avatar if character_id exists
                if (m.character_id) {
                  avatarSrc = characterAvatarMap.get(m.character_id) || null;
                  avatarAlt = '角色头像';
                } else {
                  // No character_id: use default avatar (null will show 🤖 emoji)
                  avatarSrc = null;
                  avatarAlt = 'AI 头像';
                }
              }
              
              return (
                <Avatar
                  src={avatarSrc}
                  alt={avatarAlt}
                  isUser={isUser}
                />
              );
            }
            return <div className="w-8 flex-shrink-0" />;
          };

          // Show time at the top of the entire message group (before tool outputs and bubbles)
          const displayTime = m.virtualTime ? formatVirtualTime(m.virtualTime) : null;

          return (
            <div key={`msg-${messageIdx}`} className="space-y-1">
              {/* Time display at the top of the message group */}
              {displayTime && (
                <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-1 px-1`}>
                  <span className={`text-xs text-slate-500 ${isUser ? 'mr-11' : 'ml-11'}`}>
                    {displayTime}
                  </span>
                </div>
              )}
              
              {toolOutputs
                .filter((tool) => {
                  // Filter out terminate tool outputs
                  if (tool.toolName?.toLowerCase() === 'terminate') {
                    return false;
                  }
                  return true;
                })
                .map((tool, toolIdx) => {
                // Determine background color based on tool name
                const isInnerThought = tool.toolName?.toLowerCase() === 'inner_thought';
                // Get theme classes
                const toolBgClass = isInnerThought
                  ? chatTheme.toolBubbles.reflectionBg
                  : chatTheme.toolBubbles.defaultBg;
                const toolTextClass = isInnerThought
                  ? chatTheme.toolBubbles.reflectionLabel
                  : chatTheme.toolBubbles.defaultLabel;
                const toolContentClass = isInnerThought
                  ? chatTheme.toolBubbles.reflectionContent
                  : chatTheme.toolBubbles.defaultContent;
                return (
                  <div
                    key={`msg-${messageIdx}-tool-${toolIdx}`}
                    className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                  >
                    {renderAvatar(!avatarRendered)}
                    <div className={`max-w-[75%] rounded-lg px-3 py-2 text-xs ${toolBgClass}`}>
                      <div className={`text-[11px] uppercase tracking-wide ${toolTextClass}`}>
                        {formatToolName(tool.toolName)}
                      </div>
                      <div className={`mt-1 whitespace-pre-wrap ${toolContentClass}`}>
                        {tool.content || '（无输出）'}
                      </div>
                    </div>
                  </div>
                );
              })}

              {bubbles.map((bubble, bubbleIdx) => {
                const showAvatar = bubble.isFirstLine && !avatarRendered;
                const bubbleKey = `msg-${messageIdx}-line-${bubbleIdx}`;
                // Determine background color based on tool name or input mode
                const isSpeakInPerson = m.toolName === 'speak_in_person';
                const isTelegram = m.toolName === 'send_telegram_message';
                let bubbleBgClass: string;
                if (isUser) {
                  // Different colors for different input modes
                  const userInputMode = m.inputMode as InputMode | undefined;
                  // Access theme using the enum value, fallback to default if not found
                  bubbleBgClass = (userInputMode && chatTheme.userBubbles[userInputMode]) || chatTheme.userBubbles.default;
                } else {
                  // Assistant message colors
                  bubbleBgClass = isSpeakInPerson
                    ? chatTheme.assistantBubbles.speakInPerson
                    : isTelegram
                    ? chatTheme.assistantBubbles.telegram
                    : chatTheme.assistantBubbles.default;
                }
                
                return (
                  <div
                    key={bubbleKey}
                    className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                  >
                    {renderAvatar(showAvatar)}
                    <div
                      className={`max-w-[75%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${bubbleBgClass}`}
                    >
                      {bubble.content}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
        
        {/* 等待响应的加载动画 */}
        {isWaitingResponse && (
          <div className="space-y-1">
            <div className="flex items-start gap-3">
              {/* AI 头像 - 使用当前选择的角色头像 */}
              <Avatar
                src={selectedCharacter?.character_id ? (characterAvatarMap.get(selectedCharacter.character_id) || null) : null}
                alt="角色头像"
                isUser={false}
              />
              
              {/* 加载气泡 */}
              <div className="max-w-[75%] rounded-lg px-4 py-2 text-sm bg-slate-800 text-slate-50">
                <LoadingDots />
              </div>
            </div>
            
            {/* 工具状态窗口 - 沉浸模式下隐藏 */}
            {!immersiveMode && (
              <div className="flex items-start gap-3">
                {/* 占位符，保持与加载气泡对齐 */}
                <div className="w-8 flex-shrink-0" />
                
                {/* 状态窗口 */}
                <div className="max-w-[75%] rounded px-3 py-1 text-xs bg-slate-800/60 text-slate-400 border border-slate-700/50 animate-pulse">
                  {toolStatus}
                </div>
              </div>
            )}
          </div>
        )}
        
        {error && (
          <div className="text-xs text-red-400 border border-red-400/50 rounded p-2 bg-red-950/20">
            错误：{error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className={`relative border-t p-4 transition-colors duration-200 ${
        isExtendedMode 
          ? 'bg-rose-300/20 border-rose-400/30' 
          : 'bg-slate-950 border-slate-700'
      }`}>
        {/* 浮动书签 - 位于输入框上方 */}
        <div className="absolute -top-8 left-4 right-4 pointer-events-none z-10">
          <div className="flex items-end justify-between gap-2 pointer-events-auto">
            {/* 左侧书签 - 基础输入模式 */}
            <div className="inline-flex items-end gap-2 pointer-events-auto">
              <div className={`inline-flex items-end gap-2 px-2 py-1 border rounded-t-lg shadow-lg transition-all duration-200 ${
                isBasicMode
                  ? 'border-sky-500/50 bg-sky-900/40'
                  : 'border-slate-700 bg-slate-900/80'
              }`}>
                {getInputModesByCategory(InputModeCategory.BASIC).map((mode) => {
                  const isActive = mode.key === inputMode;
                  return (
                    <button
                      key={mode.key}
                      type="button"
                      onClick={() => {
                        setInputMode(mode.key);
                      }}
                      className={`relative overflow-visible px-3 py-1 text-xs font-medium rounded-t-md transition-all duration-200 ${
                        isActive
                          ? 'bg-sky-600 text-white shadow-lg shadow-sky-900/40'
                          : 'text-slate-300 hover:text-white'
                      }`}
                    >
                      {mode.label}
                    </button>
                  );
                })}
              </div>
            </div>
            
            {/* 右侧书签 - 扩展输入模式 */}
            <div className="inline-flex items-end gap-2 pointer-events-auto">
              <div className={`inline-flex items-end gap-2 px-2 py-1 border rounded-t-lg shadow-lg transition-all duration-200 ${
                isExtendedMode
                  ? 'border-rose-500/50 bg-rose-900/40'
                  : 'border-rose-400/50 bg-rose-200/20'
              }`}>
                {getInputModesByCategory(InputModeCategory.EXTENDED).map((mode) => {
                  const isActive = mode.key === inputMode;
                  return (
                    <button
                      key={mode.key}
                      type="button"
                      onClick={() => {
                        setInputMode(mode.key);
                      }}
                      disabled={!mode.available}
                      className={`relative overflow-visible px-3 py-1 text-xs font-medium rounded-t-md transition-all duration-200 ${
                        isActive
                          ? 'bg-rose-500 text-white shadow-lg shadow-rose-900/40'
                          : mode.available
                          ? 'text-rose-300 hover:text-rose-100'
                          : 'text-rose-500/50 cursor-not-allowed opacity-50'
                      }`}
                    >
                      {mode.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <textarea
            className={`w-full resize-none rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 text-slate-50 disabled:cursor-not-allowed disabled:opacity-60 transition-colors duration-200 ${
              isExtendedMode
                ? 'bg-rose-200/30 border border-rose-400/50 focus:ring-rose-500'
                : 'bg-slate-900 border border-slate-700 focus:ring-sky-500'
            }`}
            rows={3}
            placeholder={inputPlaceholder}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <div className="flex items-center justify-between gap-2">
            {/* 左侧：目标角色和参与者选择框 */}
            <div className="flex items-center gap-2">
              {/* 目标角色选择框（单选） */}
              <div className="relative character-dropdown">
                <button
                  type="button"
                  onClick={() => {
                    setTargetDropdownOpen(!targetDropdownOpen);
                    setParticipantsDropdownOpen(false);
                  }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-800 border border-slate-700 hover:border-sky-500 text-sm text-slate-200 transition-colors min-w-[120px]"
                >
                  {targetCharacterId ? (
                    <>
                      <div className="w-5 h-5 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center flex-shrink-0 overflow-hidden">
                        {characterAvatarMap.get(targetCharacterId) ? (
                          <img 
                            src={characterAvatarMap.get(targetCharacterId)!} 
                            alt="角色头像" 
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="text-xs">🤖</div>
                        )}
                      </div>
                      <span className="truncate">
                        {allCharacters.find(c => c.character_id === targetCharacterId)?.name || '目标'}
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-400">选择目标</span>
                  )}
                  <span className="ml-auto text-slate-400">▼</span>
                </button>
                {targetDropdownOpen && (
                  <div className="absolute bottom-full left-0 mb-1 w-64 max-h-60 overflow-y-auto bg-slate-800 border border-slate-700 rounded-md shadow-lg z-50">
                    <div className="p-1">
                      <button
                        type="button"
                        onClick={() => {
                          handleTargetCharacterChange('');
                          setTargetDropdownOpen(false);
                        }}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-left transition-colors ${
                          !targetCharacterId
                            ? 'bg-sky-600/20 text-sky-300'
                            : 'text-slate-300 hover:bg-slate-700'
                        }`}
                      >
                        <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
                          <span className="text-xs">—</span>
                        </div>
                        <span>未选择</span>
                      </button>
                      {allCharacters.map((character) => (
                        <button
                          key={character.character_id}
                          type="button"
                          onClick={() => {
                            handleTargetCharacterChange(character.character_id);
                            setTargetDropdownOpen(false);
                          }}
                          className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-left transition-colors ${
                            targetCharacterId === character.character_id
                              ? 'bg-sky-600/20 text-sky-300'
                              : 'text-slate-300 hover:bg-slate-700'
                          }`}
                        >
                          <div className="w-6 h-6 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center flex-shrink-0 overflow-hidden">
                            {character.avatar ? (
                              <img 
                                src={character.avatar} 
                                alt={character.name} 
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="text-xs">🤖</div>
                            )}
                          </div>
                          <span className="truncate">{character.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 参与者选择框（多选） */}
              <div className="relative character-dropdown">
                <button
                  type="button"
                  onClick={() => {
                    setParticipantsDropdownOpen(!participantsDropdownOpen);
                    setTargetDropdownOpen(false);
                  }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-800 border border-slate-700 hover:border-sky-500 text-sm text-slate-200 transition-colors min-w-[120px]"
                >
                  {participantIds.length > 0 ? (
                    <>
                      <div className="flex items-center gap-1 -space-x-2">
                        {participantIds.slice(0, 2).map((id) => (
                          <div
                            key={id}
                            className="w-5 h-5 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center flex-shrink-0 overflow-hidden"
                          >
                            {id === 'user' ? (
                              userAvatar ? (
                                <img 
                                  src={userAvatar} 
                                  alt="用户头像" 
                                  className="w-full h-full object-cover"
                                />
                              ) : (
                                <div className="text-xs">👤</div>
                              )
                            ) : characterAvatarMap.get(id) ? (
                              <img 
                                src={characterAvatarMap.get(id)!} 
                                alt="角色头像" 
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="text-xs">🤖</div>
                            )}
                          </div>
                        ))}
                        {participantIds.length > 2 && (
                          <div className="w-5 h-5 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs">
                            +{participantIds.length - 2}
                          </div>
                        )}
                      </div>
                      <span className="truncate">参与者</span>
                    </>
                  ) : (
                    <span className="text-slate-400">选择参与者</span>
                  )}
                  <span className="ml-auto text-slate-400">▼</span>
                </button>
                {participantsDropdownOpen && (
                  <div className="absolute bottom-full left-0 mb-1 w-64 max-h-60 overflow-y-auto bg-slate-800 border border-slate-700 rounded-md shadow-lg z-50">
                    <div className="p-1">
                      {/* User option */}
                      {(() => {
                        const isUserSelected = participantIds.includes('user');
                        return (
                          <button
                            key="user"
                            type="button"
                            onClick={handleUserParticipantToggle}
                            className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-left transition-colors ${
                              isUserSelected
                                ? 'bg-sky-600/20 text-sky-300 hover:bg-sky-600/30'
                                : 'text-slate-300 hover:bg-slate-700'
                            }`}
                          >
                            <div className="w-5 h-5 rounded border border-slate-600 flex items-center justify-center flex-shrink-0">
                              {isUserSelected && (
                                <span className="text-xs text-sky-400">✓</span>
                              )}
                            </div>
                            <div className="w-6 h-6 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center flex-shrink-0 overflow-hidden">
                              {userAvatar ? (
                                <img 
                                  src={userAvatar} 
                                  alt="用户" 
                                  className="w-full h-full object-cover"
                                />
                              ) : (
                                <div className="text-xs">👤</div>
                              )}
                            </div>
                            <span className="truncate">用户</span>
                          </button>
                        );
                      })()}
                      
                      {/* Character options */}
                      {allCharacters.map((character) => {
                        const isSelected = participantIds.includes(character.character_id);
                        const isTarget = character.character_id === targetCharacterId;
                        const isDisabled = isTarget && isSelected; // 目标是参与者时，不能取消
                        return (
                          <button
                            key={character.character_id}
                            type="button"
                            onClick={() => handleParticipantToggle(character.character_id)}
                            disabled={isDisabled}
                            className={`w-full flex items-center gap-2 px-3 py-2 rounded text-sm text-left transition-colors ${
                              isDisabled
                                ? 'bg-sky-600/30 text-sky-200 cursor-not-allowed opacity-75'
                                : isSelected
                                ? 'bg-sky-600/20 text-sky-300 hover:bg-sky-600/30'
                                : 'text-slate-300 hover:bg-slate-700'
                            }`}
                            title={isDisabled ? '目标角色不能从参与者中移除' : undefined}
                          >
                            <div className="w-5 h-5 rounded border border-slate-600 flex items-center justify-center flex-shrink-0">
                              {isSelected && (
                                <span className="text-xs text-sky-400">✓</span>
                              )}
                            </div>
                            <div className="w-6 h-6 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center flex-shrink-0 overflow-hidden">
                              {character.avatar ? (
                                <img 
                                  src={character.avatar} 
                                  alt={character.name} 
                                  className="w-full h-full object-cover"
                                />
                              ) : (
                                <div className="text-xs">🤖</div>
                              )}
                            </div>
                            <span className="truncate">{character.name}</span>
                            {isTarget && (
                              <span className="ml-auto text-xs text-sky-400">目标</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 右侧：发送和跳过按钮 */}
            <div className="flex gap-2">
              <button
                type="button"
                className="px-4 py-1.5 rounded-md bg-slate-600 hover:bg-slate-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                onClick={() => sendMessage(true)}
                disabled={loading || !sessionId}
                title="跳过当前回合，不发送消息内容"
              >
                跳过
              </button>
              <button
                type="button"
                className="px-4 py-1.5 rounded-md bg-sky-600 hover:bg-sky-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                onClick={() => sendMessage(false)}
                disabled={loading || !input.trim() || !sessionId}
              >
                {loading ? '发送中...' : '发送'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

