/**
 * 会话管理：创建、删除、切换会话
 */

const SESSIONS_KEY = 'neochat_sessions';
const CURRENT_SESSION_KEY = 'neochat_current_session';

// Cache for tracking last saved message count per session
// This is used for incremental saving
const lastSavedCountCache = new Map<string, number>();

// Cache for tracking message IDs in database (sessionId -> messageIndex -> messageId)
// This is used for updating existing messages instead of creating duplicates
const messageIdCache = new Map<string, Map<number, number>>();

// Export function to update cache (used when loading messages from database)
export function updateLastSavedCount(sessionId: string, count: number): void {
  lastSavedCountCache.set(sessionId, count);
}

// Export function to update message ID cache (used when loading messages from database)
export function updateMessageIdCache(sessionId: string, messageIndex: number, messageId: number): void {
  if (!messageIdCache.has(sessionId)) {
    messageIdCache.set(sessionId, new Map());
  }
  messageIdCache.get(sessionId)!.set(messageIndex, messageId);
}

// Export function to clear message ID cache for a session
export function clearMessageIdCache(sessionId: string): void {
  messageIdCache.delete(sessionId);
}

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

function generateSessionId(): string {
  // Generate 16-character UUID (32 hex chars, take first 16)
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    const uuid = crypto.randomUUID().replace(/-/g, '');
    return uuid.substring(0, 16);
  }
  // Fallback: generate 16 random hex characters
  const chars = '0123456789abcdef';
  let result = '';
  for (let i = 0; i < 16; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export function getAllSessions(): Session[] {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const stored = window.localStorage.getItem(SESSIONS_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to load sessions:', e);
  }

  return [];
}

/**
 * Sync sessions from database to localStorage
 * This is called after switching archives to load sessions from the new database
 */
export async function syncSessionsFromDatabase(): Promise<Session[]> {
  try {
    // Direct import - no circular dependency since this is a utility function
    const { getSessions } = await import('@/lib/api/sessions');
    const dbSessions = await getSessions();
    
    // Convert database session format to localStorage format
    const localStorageSessions: Session[] = dbSessions.map(dbSession => ({
      id: dbSession.id,
      title: dbSession.name,
      createdAt: new Date(dbSession.created_at).getTime(),
      updatedAt: new Date(dbSession.updated_at).getTime(),
    }));
    
    // Save to localStorage
    if (localStorageSessions.length > 0) {
      saveSessions(localStorageSessions);
    }
    
    return localStorageSessions;
  } catch (err) {
    console.error('Failed to sync sessions from database:', err);
    return [];
  }
}

export function saveSessions(sessions: Session[]): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
  } catch (e) {
    console.error('Failed to save sessions:', e);
  }
}

export function createSession(title?: string): Session {
  const now = Date.now();
  const session: Session = {
    id: generateSessionId(),
    title: title || `新会话 ${new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}`,
    createdAt: now,
    updatedAt: now,
  };

  const sessions = getAllSessions();
  sessions.unshift(session); // 新会话放在最前面
  saveSessions(sessions);

  return session;
}

export function deleteSession(sessionId: string): void {
  const sessions = getAllSessions();
  const filtered = sessions.filter((s) => s.id !== sessionId);
  saveSessions(filtered);

  // 删除会话时，同时删除该会话的消息历史
  clearSessionMessages(sessionId);

  // 如果删除的是当前会话，清空当前会话
  const current = getCurrentSessionId();
  if (current === sessionId) {
    setCurrentSessionId(null);
  }
}

export function updateSession(sessionId: string, updates: Partial<Session>): void {
  const sessions = getAllSessions();
  const index = sessions.findIndex((s) => s.id === sessionId);
  if (index >= 0) {
    sessions[index] = { ...sessions[index], ...updates, updatedAt: Date.now() };
    saveSessions(sessions);
  }
}

export function getCurrentSessionId(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.localStorage.getItem(CURRENT_SESSION_KEY);
}

export function setCurrentSessionId(sessionId: string | null): void {
  if (typeof window === 'undefined') return;

  if (sessionId) {
    window.localStorage.setItem(CURRENT_SESSION_KEY, sessionId);
  } else {
    window.localStorage.removeItem(CURRENT_SESSION_KEY);
  }
}

/**
 * 消息管理：为每个会话存储消息历史
 */
export interface ToolOutput {
  toolName: string;
  content: string;
  toolCallId?: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  toolOutputs?: ToolOutput[];
  toolName?: string; // Tool name for inline tools (send_telegram_message, speak_in_person)
  inputMode?: string; // Input mode for user messages (phone, in_person, inner_voice)
  character_id?: string; // Character ID associated with this message (for assistant messages)
  clientMessageId?: string; // Stable client message ID for database upsert
  virtualTime?: string; // Virtual time when the message was created (format: 'YYYY-MM-DD HH:MM:SS')
}

function getMessagesKey(sessionId: string): string {
  return `neochat_messages_${sessionId}`;
}

export function getSessionMessages(sessionId: string): Message[] {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const stored = window.localStorage.getItem(getMessagesKey(sessionId));
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to load messages:', e);
  }

  return [];
}


interface ClientMessageCacheEntry {
  id?: number;
  content: string;
  tool_name?: string;
}

// Cache for tracking client_message_id to database metadata (id + last content snapshot)
const clientMessageIdCache = new Map<string, Map<string, ClientMessageCacheEntry>>(); // sessionId -> client_message_id -> entry

function getClientMessageCache(sessionId: string): Map<string, ClientMessageCacheEntry> {
  if (!clientMessageIdCache.has(sessionId)) {
    clientMessageIdCache.set(sessionId, new Map());
  }
  return clientMessageIdCache.get(sessionId)!;
}

function setClientMessageCacheEntry(
  sessionId: string,
  clientMessageId: string,
  entry: ClientMessageCacheEntry
): void {
  getClientMessageCache(sessionId).set(clientMessageId, entry);
}

function getClientMessageCacheEntry(
  sessionId: string,
  clientMessageId: string
): ClientMessageCacheEntry | undefined {
  return clientMessageIdCache.get(sessionId)?.get(clientMessageId);
}

function clearClientMessageCache(sessionId: string): void {
  clientMessageIdCache.delete(sessionId);
}

export function primeClientMessageCache(
  sessionId: string,
  payload: {
    client_message_id: string;
    id?: number;
    content?: string;
    tool_name?: string;
  }
): void {
  if (!sessionId || !payload?.client_message_id) {
    return;
  }
  setClientMessageCacheEntry(sessionId, payload.client_message_id, {
    id: payload.id,
    content: payload.content ?? '',
    tool_name: payload.tool_name,
  });
}

export function saveSessionMessages(sessionId: string, messages: Message[]): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(getMessagesKey(sessionId), JSON.stringify(messages));
    
    // Save to database (async, don't block)
    if (messages.length > 0) {
      // Import dynamically to avoid circular dependencies
      import('@/lib/api/frontendMessages').then(({ createFrontendMessage, updateFrontendMessage }) => {
        // Convert messages array to flat list of database messages
        // Each tool output becomes a separate message, text messages are separate
        const dbMessages: Array<{
          client_message_id: string;
          role: 'user' | 'assistant';
          message_kind: 'text' | 'tool_output' | 'user' | 'system';
          content: string;
          tool_name?: string;
          tool_call_id?: string;
          input_mode?: string;
          character_id?: string;
          display_order: number;
          created_at?: string; // Virtual time
        }> = [];
        
        let displayOrder = 0;
        
        messages.forEach((msg, msgIndex) => {
          // Save tool outputs as separate messages
          if (msg.toolOutputs && msg.toolOutputs.length > 0) {
            msg.toolOutputs.forEach((toolOutput) => {
              const toolCallId = toolOutput.toolCallId || `tool_${sessionId}_${msgIndex}_${toolOutput.toolName}`;
              dbMessages.push({
                client_message_id: toolCallId,
                role: msg.role,
                message_kind: 'tool_output',
                content: toolOutput.content,
                tool_name: toolOutput.toolName,
                tool_call_id: toolCallId,
                character_id: msg.character_id,
                display_order: displayOrder,
              });
              displayOrder++;
            });
          }
          
          // Save text message if it has content or toolName (for inline tools)
          const hasContent = msg.content && msg.content.trim();
          const hasToolName = msg.toolName && msg.toolName.trim();
          
          if (hasContent || hasToolName) {
            // Use clientMessageId from message (set by backend message_id) or generate a stable one
            // Backend message_id is preferred as it's the authoritative source
            const textMessageId = msg.clientMessageId || 
              (msg.toolName 
                ? `text_${sessionId}_${msgIndex}_${msg.toolName}`
                : `text_${sessionId}_${msgIndex}_${msg.role}`);
            
            dbMessages.push({
              client_message_id: textMessageId,
                  role: msg.role,
              message_kind: msg.role === 'user' ? 'user' : 'text',
              content: msg.content || '',
                  tool_name: msg.toolName,
                  input_mode: msg.inputMode,
                  character_id: msg.character_id,
              display_order: displayOrder,
              created_at: msg.virtualTime, // Pass virtual time to database
            });
            displayOrder++;
          }
        });
        
        const saveOperations: Promise<void>[] = [];
        dbMessages.forEach((dbMsg, index) => {
          const normalizedContent = dbMsg.content ?? '';
          const normalizedToolName = dbMsg.tool_name ?? '';
          const cachedEntry = getClientMessageCacheEntry(sessionId, dbMsg.client_message_id);
          const hasChanges =
            !cachedEntry ||
            cachedEntry.content !== normalizedContent ||
            (cachedEntry.tool_name ?? '') !== normalizedToolName;

          if (!cachedEntry) {
            saveOperations.push(
              new Promise<void>((resolve) => {
            setTimeout(() => {
              createFrontendMessage({
                session_id: sessionId,
                client_message_id: dbMsg.client_message_id,
                role: dbMsg.role,
                message_kind: dbMsg.message_kind,
                    content: normalizedContent,
                tool_name: dbMsg.tool_name,
                tool_call_id: dbMsg.tool_call_id,
                input_mode: dbMsg.input_mode,
                character_id: dbMsg.character_id,
                    display_order: dbMsg.display_order,
                    created_at: (dbMsg as any).created_at, // Pass virtual time
                  })
                    .then((savedMessage) => {
                      setClientMessageCacheEntry(sessionId, dbMsg.client_message_id, {
                        id: savedMessage.id,
                        content: normalizedContent,
                        tool_name: normalizedToolName,
                      });
                      resolve();
                    })
                    .catch((err) => {
                      console.error(`Failed to save message ${dbMsg.client_message_id}:`, err);
                      resolve();
                    });
                }, index * 15);
              })
            );
          } else if (hasChanges) {
            const targetId = cachedEntry.id;
            if (targetId) {
              saveOperations.push(
                new Promise<void>((resolve) => {
                  setTimeout(() => {
                    updateFrontendMessage(targetId, {
                      content: normalizedContent,
                      tool_name: dbMsg.tool_name,
                      created_at: dbMsg.created_at,
                    })
                      .then(() => {
                        setClientMessageCacheEntry(sessionId, dbMsg.client_message_id, {
                          id: targetId,
                          content: normalizedContent,
                          tool_name: normalizedToolName,
                        });
                        resolve();
                      })
                      .catch((err) => {
                        // If update fails (e.g., 404 not found), fallback to create new message
                        // This can happen when database was reset or archive was switched
                        console.debug(`Update failed for message ${dbMsg.client_message_id}, attempting to create new:`, err.message);
                        createFrontendMessage({
                          session_id: sessionId,
                          client_message_id: dbMsg.client_message_id,
                          role: dbMsg.role,
                          message_kind: dbMsg.message_kind,
                          content: normalizedContent,
                          tool_name: dbMsg.tool_name,
                          tool_call_id: dbMsg.tool_call_id,
                          input_mode: dbMsg.input_mode,
                          character_id: dbMsg.character_id,
                          display_order: dbMsg.display_order,
                          created_at: (dbMsg as any).created_at,
                        })
                          .then((savedMessage) => {
                            setClientMessageCacheEntry(sessionId, dbMsg.client_message_id, {
                              id: savedMessage.id,
                              content: normalizedContent,
                              tool_name: normalizedToolName,
                            });
                            resolve();
                          })
                          .catch((createErr) => {
                            // Silently ignore if create also fails (might be duplicate)
                            console.debug(`Create fallback also failed for ${dbMsg.client_message_id}:`, createErr.message);
                            resolve();
                          });
                      });
                  }, index * 15);
                })
              );
            } else {
              // Missing database ID (likely saved before cache was hydrated) - fallback to create
              saveOperations.push(
                new Promise<void>((resolve) => {
                  setTimeout(() => {
                    createFrontendMessage({
                      session_id: sessionId,
                      client_message_id: dbMsg.client_message_id,
                      role: dbMsg.role,
                      message_kind: dbMsg.message_kind,
                      content: normalizedContent,
                      tool_name: dbMsg.tool_name,
                      tool_call_id: dbMsg.tool_call_id,
                      input_mode: dbMsg.input_mode,
                      character_id: dbMsg.character_id,
                      display_order: dbMsg.display_order,
                      created_at: (dbMsg as any).created_at, // Pass virtual time
                })
                  .then((savedMessage) => {
                        setClientMessageCacheEntry(sessionId, dbMsg.client_message_id, {
                          id: savedMessage.id,
                          content: normalizedContent,
                          tool_name: normalizedToolName,
                        });
                    resolve();
                  })
                      .catch((err) => {
                  console.error(`Failed to save message ${dbMsg.client_message_id}:`, err);
                        resolve();
                  });
                  }, index * 15);
                })
              );
            }
          }
        });

        if (saveOperations.length > 0) {
          Promise.all(saveOperations).catch((err) => {
            console.error('Failed to persist some frontend messages:', err);
            });
        }
      }).catch(err => {
        console.error('Failed to import frontendMessages API:', err);
      });
    }
  } catch (e) {
    console.error('Failed to save messages:', e);
  }
}

export function addSessionMessage(sessionId: string, message: Message): void {
  const messages = getSessionMessages(sessionId);
  messages.push(message);
  saveSessionMessages(sessionId, messages);
}

export function clearSessionMessages(sessionId: string): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.removeItem(getMessagesKey(sessionId));
    clearClientMessageCache(sessionId);
  } catch (e) {
    console.error('Failed to clear messages:', e);
  }
}

