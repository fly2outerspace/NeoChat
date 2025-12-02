/**
 * 配置管理：存储和读取 API 配置
 */

const CONFIG_KEY = 'neochat_config';

export interface ApiConfig {
  baseUrl: string;
  model: string;
  apiKey?: string;
}

const DEFAULT_CONFIG: ApiConfig = {
  baseUrl: 'http://localhost:8000',
  model: 'Stacy',
};

export function getConfig(): ApiConfig {
  if (typeof window === 'undefined') {
    return DEFAULT_CONFIG;
  }

  try {
    const stored = window.localStorage.getItem(CONFIG_KEY);
    if (stored) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.error('Failed to load config:', e);
  }

  return DEFAULT_CONFIG;
}

export function saveConfig(config: Partial<ApiConfig>): void {
  if (typeof window === 'undefined') return;

  try {
    const current = getConfig();
    const updated = { ...current, ...config };
    window.localStorage.setItem(CONFIG_KEY, JSON.stringify(updated));
  } catch (e) {
    console.error('Failed to save config:', e);
  }
}

/**
 * 头像管理：用户头像和 AI 头像
 */
const USER_AVATAR_KEY = 'neochat_user_avatar';
const AI_AVATAR_KEY = 'neochat_ai_avatar';

export function getUserAvatar(): string | null {
  if (typeof window === 'undefined') return null;

  try {
    return window.localStorage.getItem(USER_AVATAR_KEY);
  } catch (e) {
    console.error('Failed to load user avatar:', e);
    return null;
  }
}

export function saveUserAvatar(avatarDataUrl: string): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(USER_AVATAR_KEY, avatarDataUrl);
    // 触发自定义事件，通知其他组件头像已更新
    window.dispatchEvent(new CustomEvent('avatarUpdated', { detail: { type: 'user', avatar: avatarDataUrl } }));
  } catch (e) {
    console.error('Failed to save user avatar:', e);
  }
}

export function getAiAvatar(): string | null {
  if (typeof window === 'undefined') return null;

  try {
    return window.localStorage.getItem(AI_AVATAR_KEY);
  } catch (e) {
    console.error('Failed to load AI avatar:', e);
    return null;
  }
}

export function saveAiAvatar(avatarDataUrl: string): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(AI_AVATAR_KEY, avatarDataUrl);
    // 触发自定义事件，通知其他组件头像已更新
    window.dispatchEvent(new CustomEvent('avatarUpdated', { detail: { type: 'ai', avatar: avatarDataUrl } }));
  } catch (e) {
    console.error('Failed to save AI avatar:', e);
  }
}

export function clearUserAvatar(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(USER_AVATAR_KEY);
  // 触发自定义事件
  window.dispatchEvent(new CustomEvent('avatarUpdated', { detail: { type: 'user', avatar: null } }));
}

export function clearAiAvatar(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(AI_AVATAR_KEY);
  // 触发自定义事件
  window.dispatchEvent(new CustomEvent('avatarUpdated', { detail: { type: 'ai', avatar: null } }));
}

/**
 * 流式输出设置管理
 */
const STREAMING_ENABLED_KEY = 'neochat_streaming_enabled';

export function getStreamingEnabled(): boolean {
  if (typeof window === 'undefined') return true; // 默认启用流式

  try {
    const stored = window.localStorage.getItem(STREAMING_ENABLED_KEY);
    if (stored === null) {
      return true; // 默认启用流式
    }
    return stored === 'true';
  } catch (e) {
    console.error('Failed to load streaming setting:', e);
    return true; // 默认启用流式
  }
}

export function saveStreamingEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(STREAMING_ENABLED_KEY, enabled.toString());
    // 触发自定义事件，通知其他组件流式设置已更新
    window.dispatchEvent(new CustomEvent('streamingSettingUpdated', { detail: { enabled } }));
  } catch (e) {
    console.error('Failed to save streaming setting:', e);
  }
}

/**
 * Flow 模式设置管理
 */
export type ChatMode = 'agent' | 'flow';

const CHAT_MODE_KEY = 'neochat_chat_mode';
const DEFAULT_CHAT_MODE: ChatMode = 'flow';

export function getChatMode(): ChatMode {
  if (typeof window === 'undefined') {
    return DEFAULT_CHAT_MODE;
  }

  try {
    const stored = window.localStorage.getItem(CHAT_MODE_KEY) as ChatMode | null;
    if (stored) {
      return stored;
    }
  } catch (e) {
    console.error('Failed to load chat mode setting:', e);
  }

  return DEFAULT_CHAT_MODE;
}

export function saveChatMode(mode: ChatMode): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(CHAT_MODE_KEY, mode);
    // 触发自定义事件，通知其他组件聊天模式已更新
    window.dispatchEvent(new CustomEvent('chatModeUpdated', { detail: { mode } }));
  } catch (e) {
    console.error('Failed to save chat mode setting:', e);
  }
}

/**
 * 沉浸模式设置管理
 */
const IMMERSIVE_MODE_KEY = 'neochat_immersive_mode';

export function getImmersiveMode(): boolean {
  if (typeof window === 'undefined') return false;

  try {
    const stored = window.localStorage.getItem(IMMERSIVE_MODE_KEY);
    if (stored === null) {
      return false; // 默认关闭沉浸模式
    }
    return stored === 'true';
  } catch (e) {
    console.error('Failed to load immersive mode setting:', e);
    return false;
  }
}

export function saveImmersiveMode(enabled: boolean): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(IMMERSIVE_MODE_KEY, enabled.toString());
    // 触发自定义事件，通知其他组件沉浸模式已更新
    window.dispatchEvent(new CustomEvent('immersiveModeUpdated', { detail: { enabled } }));
  } catch (e) {
    console.error('Failed to save immersive mode setting:', e);
  }
}

/**
 * 内心想法显示设置管理
 */
const INNER_THOUGHT_ENABLED_KEY = 'neochat_inner_thought_enabled';

export function getInnerThoughtEnabled(): boolean {
  if (typeof window === 'undefined') return true; // 默认开启

  try {
    const stored = window.localStorage.getItem(INNER_THOUGHT_ENABLED_KEY);
    if (stored === null) {
      return true; // 默认开启
    }
    return stored === 'true';
  } catch (e) {
    console.error('Failed to load inner thought setting:', e);
    return true; // 默认开启
  }
}

export function saveInnerThoughtEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(INNER_THOUGHT_ENABLED_KEY, enabled.toString());
    // 触发自定义事件，通知其他组件内心想法设置已更新
    window.dispatchEvent(new CustomEvent('innerThoughtEnabledUpdated', { detail: { enabled } }));
  } catch (e) {
    console.error('Failed to save inner thought setting:', e);
  }
}

/**
 * 主题设置管理
 */
export type ThemeId = 'cyber-noir';

const THEME_SETTING_KEY = 'neochat_theme';
const DEFAULT_THEME_ID: ThemeId = 'cyber-noir';

export function getThemeSetting(): ThemeId {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME_ID;
  }

  try {
    const stored = window.localStorage.getItem(THEME_SETTING_KEY) as ThemeId | null;
    if (stored) {
      return stored;
    }
  } catch (e) {
    console.error('Failed to load theme setting:', e);
  }

  return DEFAULT_THEME_ID;
}

export function saveThemeSetting(themeId: ThemeId): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(THEME_SETTING_KEY, themeId);
    // 触发自定义事件，通知其他组件主题已更新
    window.dispatchEvent(new CustomEvent('themeUpdated', { detail: { themeId } }));
  } catch (e) {
    console.error('Failed to save theme setting:', e);
  }
}

/**
 * Clear all NeoChat-related localStorage data
 * This will clear:
 * - All neochat_* keys (config, sessions, messages, etc.)
 * - selected_character, selected_participants, selected_model
 * - character_editing_state_*, model_editing_state_*
 * - chat_input_* (session input drafts)
 * - role_new_*, model_new_* (creation form drafts)
 * 
 * Note: This will trigger a sync event to reload data from database
 */
export function clearAllLocalStorage(): void {
  if (typeof window === 'undefined') return;

  try {
    // Collect all keys to remove
    const keysToRemove: string[] = [];
    
    // Iterate through all localStorage keys
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (!key) continue;
      
      // Match NeoChat-related keys
      if (
        key.startsWith('neochat_') ||
        key.startsWith('selected_') ||
        key.startsWith('character_editing_state_') ||
        key.startsWith('model_editing_state_') ||
        key.startsWith('chat_input_') ||
        key.startsWith('role_new_') ||
        key.startsWith('model_new_')
      ) {
        keysToRemove.push(key);
      }
    }
    
    // Remove all matched keys
    keysToRemove.forEach(key => {
      window.localStorage.removeItem(key);
    });
    
    console.log(`Cleared ${keysToRemove.length} localStorage keys`);
    
    // Trigger sync event to reload data from database
    window.dispatchEvent(new CustomEvent('localStorageCleared'));
  } catch (e) {
    console.error('Failed to clear localStorage:', e);
    throw e;
  }
}

