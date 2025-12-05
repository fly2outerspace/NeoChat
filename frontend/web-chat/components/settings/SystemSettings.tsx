'use client';

import { useState, useEffect, type ChangeEvent } from 'react';
import { getStreamingEnabled, saveStreamingEnabled, getThemeSetting, saveThemeSetting, getChatMode, saveChatMode, getImmersiveMode, saveImmersiveMode, getInnerThoughtEnabled, saveInnerThoughtEnabled, clearAllLocalStorage, type ThemeId, type ChatMode } from '@/lib/config';
import { CHAT_THEMES } from '@/lib/themes';

export default function SystemSettings() {
  const [streamingEnabled, setStreamingEnabled] = useState<boolean>(true);
  const [saved, setSaved] = useState(false);
  const [themeId, setThemeId] = useState<ThemeId>('cyber-noir');
  const [themeSaved, setThemeSaved] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>('flow');
  const [chatModeSaved, setChatModeSaved] = useState(false);
  const [immersiveMode, setImmersiveMode] = useState<boolean>(false);
  const [immersiveModeSaved, setImmersiveModeSaved] = useState(false);
  const [innerThoughtEnabled, setInnerThoughtEnabled] = useState<boolean>(true);
  const [innerThoughtSaved, setInnerThoughtSaved] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearSuccess, setClearSuccess] = useState(false);

  useEffect(() => {
    const stored = getStreamingEnabled();
    setStreamingEnabled(stored);
    setThemeId(getThemeSetting());
    setChatMode(getChatMode());
    setImmersiveMode(getImmersiveMode());
    setInnerThoughtEnabled(getInnerThoughtEnabled());
  }, []);

  // 监听流式设置更新事件
  useEffect(() => {
    const handleStreamingUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ enabled: boolean }>;
      setStreamingEnabled(customEvent.detail.enabled);
    };

    window.addEventListener('streamingSettingUpdated', handleStreamingUpdate);
    return () => {
      window.removeEventListener('streamingSettingUpdated', handleStreamingUpdate);
    };
  }, []);

  useEffect(() => {
    const handleThemeUpdated = (e: Event) => {
      const customEvent = e as CustomEvent<{ themeId: ThemeId }>;
      setThemeId(customEvent.detail.themeId);
    };

    window.addEventListener('themeUpdated', handleThemeUpdated);
    return () => window.removeEventListener('themeUpdated', handleThemeUpdated);
  }, []);

  useEffect(() => {
    const handleChatModeUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ mode: ChatMode }>;
      setChatMode(customEvent.detail.mode);
    };

    window.addEventListener('chatModeUpdated', handleChatModeUpdate);
    return () => window.removeEventListener('chatModeUpdated', handleChatModeUpdate);
  }, []);

  useEffect(() => {
    const handleImmersiveModeUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ enabled: boolean }>;
      setImmersiveMode(customEvent.detail.enabled);
    };

    window.addEventListener('immersiveModeUpdated', handleImmersiveModeUpdate);
    return () => window.removeEventListener('immersiveModeUpdated', handleImmersiveModeUpdate);
  }, []);

  useEffect(() => {
    const handleInnerThoughtEnabledUpdate = (e: Event) => {
      const customEvent = e as CustomEvent<{ enabled: boolean }>;
      setInnerThoughtEnabled(customEvent.detail.enabled);
    };

    window.addEventListener('innerThoughtEnabledUpdated', handleInnerThoughtEnabledUpdate);
    return () => window.removeEventListener('innerThoughtEnabledUpdated', handleInnerThoughtEnabledUpdate);
  }, []);

  const handleToggleStreaming = () => {
    const newValue = !streamingEnabled;
    setStreamingEnabled(newValue);
    saveStreamingEnabled(newValue);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleThemeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selectedTheme = event.target.value as ThemeId;
    setThemeId(selectedTheme);
    saveThemeSetting(selectedTheme);
    setThemeSaved(true);
    setTimeout(() => setThemeSaved(false), 2000);
  };

  const handleChatModeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selectedMode = event.target.value as ChatMode;
    setChatMode(selectedMode);
    saveChatMode(selectedMode);
    setChatModeSaved(true);
    setTimeout(() => setChatModeSaved(false), 2000);
  };

  const handleToggleImmersiveMode = () => {
    const newValue = !immersiveMode;
    setImmersiveMode(newValue);
    saveImmersiveMode(newValue);
    setImmersiveModeSaved(true);
    setTimeout(() => setImmersiveModeSaved(false), 2000);
  };

  const handleToggleInnerThought = () => {
    const newValue = !innerThoughtEnabled;
    setInnerThoughtEnabled(newValue);
    saveInnerThoughtEnabled(newValue);
    setInnerThoughtSaved(true);
    setTimeout(() => setInnerThoughtSaved(false), 2000);
  };

  const handleClearLocalStorage = () => {
    if (!confirm('确定要清空所有本地存储数据吗？\n\n这将清除：\n- 所有会话和消息历史\n- 选中的角色和模型\n- 编辑草稿\n- 输入框内容\n\n清空后将从数据库重新同步角色和模型数据。')) {
      return;
    }

    try {
      setClearing(true);
      clearAllLocalStorage();
      setClearSuccess(true);
      setTimeout(() => {
        setClearSuccess(false);
        setClearing(false);
      }, 3000);
    } catch (error: any) {
      console.error('Failed to clear localStorage:', error);
      alert(`清空失败: ${error.message}`);
      setClearing(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">系统设置</h2>
        <p className="text-sm text-slate-400 mt-1">系统相关配置</p>
      </div>

      <div className="space-y-6">
        {/* 主题配色 */}
        <div className="bg-slate-950 border border-slate-700 rounded-lg p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex-1">
              <h3 className="text-lg font-medium mb-1">聊天配色方案</h3>
              <p className="text-sm text-slate-400">
                选择一个主题应用于 Telegram、面对面与工具输出等配色
              </p>
            </div>
            <div className="w-full md:w-auto flex flex-col gap-2">
              <select
                value={themeId}
                onChange={handleThemeChange}
                className="bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                {Object.values(CHAT_THEMES).map((theme) => (
                  <option key={theme.id} value={theme.id}>
                    {theme.name}
                  </option>
                ))}
              </select>
              {themeSaved && <span className="text-xs text-sky-400">✓ 主题已保存</span>}
            </div>
          </div>
        </div>

        {/* 聊天模式设置 */}
        <div className="bg-slate-950 border border-slate-700 rounded-lg p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-lg font-medium">聊天模式</h3>
                <div className="relative group">
                  <div className="w-5 h-5 rounded-full border border-slate-500 text-slate-400 flex items-center justify-center text-xs cursor-help hover:border-slate-400 hover:text-slate-300 transition-colors">
                    ?
                  </div>
                  <div className="absolute left-0 top-6 w-64 p-3 bg-slate-800 border border-slate-600 rounded-md text-xs text-slate-200 shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-10">
                    flow模式会在后台处理日程等记忆添加，让对话响应更快
                  </div>
                </div>
              </div>
              <p className="text-sm text-slate-400">
                选择使用 Agent 模式（单智能体）或 Flow 模式（多智能体流程，加速对话过程，后台处理记录记忆和关系网）
              </p>
            </div>
            <div className="w-full md:w-auto flex flex-col gap-2">
              <select
                value={chatMode}
                onChange={handleChatModeChange}
                className="bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                <option value="agent">Agent 模式</option>
                <option value="flow">Flow 模式</option>
              </select>
              {chatModeSaved && <span className="text-xs text-sky-400">✓ 模式已保存</span>}
            </div>
          </div>
        </div>

        {/* 沉浸模式设置 */}
        <div className="bg-slate-950 border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <h3 className="text-lg font-medium mb-1">沉浸模式</h3>
              <p className="text-sm text-slate-400">
                开启后关闭所有工具调用展示
              </p>
            </div>
            <div className="ml-6 flex items-center gap-3">
              <button
                onClick={handleToggleImmersiveMode}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${
                  immersiveMode ? 'bg-sky-600' : 'bg-slate-700'
                }`}
                role="switch"
                aria-checked={immersiveMode}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    immersiveMode ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              {immersiveModeSaved && (
                <span className="text-xs text-sky-400">✓ 已保存</span>
              )}
            </div>
          </div>
        </div>

        {/* 内心想法设置 */}
        <div className="bg-slate-950 border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <h3 className="text-lg font-medium mb-1">内心想法</h3>
              <p className="text-sm text-slate-400">
                控制是否在对话窗口中显示 AI 的内心想法
              </p>
            </div>
            <div className="ml-6 flex items-center gap-3">
              <button
                onClick={handleToggleInnerThought}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${
                  innerThoughtEnabled ? 'bg-sky-600' : 'bg-slate-700'
                }`}
                role="switch"
                aria-checked={innerThoughtEnabled}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    innerThoughtEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              {innerThoughtSaved && (
                <span className="text-xs text-sky-400">✓ 已保存</span>
              )}
            </div>
          </div>
        </div>

        {/* 流式输出设置 */}
        <div className="bg-slate-950 border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <h3 className="text-lg font-medium mb-1">流式输出</h3>
              <p className="text-sm text-slate-400">
                启用后，AI 回复将实时逐字显示，提供更好的交互体验
              </p>
            </div>
            <div className="ml-6 flex items-center gap-3">
              <button
                onClick={handleToggleStreaming}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${
                  streamingEnabled ? 'bg-sky-600' : 'bg-slate-700'
                }`}
                role="switch"
                aria-checked={streamingEnabled}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    streamingEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              {saved && (
                <span className="text-xs text-sky-400">✓ 已保存</span>
              )}
            </div>
          </div>
        </div>

        {/* 清空本地存储 */}
        <div className="bg-slate-950 border border-red-700/50 rounded-lg p-6">
          <div className="flex flex-col gap-4">
            <div className="flex-1">
              <h3 className="text-lg font-medium mb-1 text-red-400">清空本地存储</h3>
              <p className="text-sm text-slate-400">
                清空所有本地缓存数据（会话、消息、草稿等），清空后将从数据库重新同步角色和模型数据
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleClearLocalStorage}
                disabled={clearing}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-600/50 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                {clearing ? '清空中...' : '清空本地存储'}
              </button>
              {clearSuccess && (
                <span className="text-xs text-green-400">✓ 已清空，正在同步数据库...</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

