'use client';

import { useState, useEffect, useRef } from 'react';
import { getAllMemory, type CharacterMemoryResponse, type CharacterMemoryItem } from '@/lib/api/memory';
import { listCharacters, type Character } from '@/lib/api/character';

export default function MemoryView() {
  const [memoryData, setMemoryData] = useState<CharacterMemoryResponse[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedScenarios, setExpandedScenarios] = useState<Set<string>>(new Set());
  const isInitializedRef = useRef(false);

  const loadData = async (isInitialLoad = false, showLoading = true, silentRefresh = false) => {
    try {
      // 只在需要显示 loading 时才设置 loading 状态
      // 如果已有数据，则不显示 loading，避免闪烁
      if (!silentRefresh && (showLoading || memoryData.length === 0)) {
        setLoading(true);
      }
      setError(null);
      
      // Load memory data (which includes characters from archive database)
      const memoryDataResponse = await getAllMemory();
      
      // Extract characters from memory response (from archive database)
      const charactersFromMemory: Character[] = memoryDataResponse.characters.map(char => ({
        id: 0, // Archive characters don't have numeric ID
        character_id: char.character_id,
        name: char.character_name,
        roleplay_prompt: null as string | null, // Not included in memory response
        avatar: null as string | null, // Not included in memory response
        created_at: '',
        updated_at: '',
      }));
      
      // Also load characters from settings to get avatar and other info
      // But use archive characters as the primary source
      let charactersWithDetails: Character[] = charactersFromMemory;
      try {
        const settingsCharacters = await listCharacters();
        // Merge: use archive characters, but enrich with settings data if available
        charactersWithDetails = charactersFromMemory.map(archChar => {
          const settingsChar = settingsCharacters.find(s => s.character_id === archChar.character_id);
          if (settingsChar) {
            return {
              ...archChar,
              id: settingsChar.id,
              roleplay_prompt: settingsChar.roleplay_prompt,
              avatar: settingsChar.avatar,
              created_at: settingsChar.created_at,
              updated_at: settingsChar.updated_at,
            };
          }
          return archChar;
        });
      } catch (err) {
        // If settings API fails, just use archive characters
        console.warn('Failed to load character details from settings:', err);
      }
      
      setCharacters(charactersWithDetails);
      setMemoryData(memoryDataResponse.characters);
      
      // Auto-select first character only on initial load
      if (isInitialLoad && charactersWithDetails.length > 0 && !selectedCharacterId) {
        setSelectedCharacterId(charactersWithDetails[0].character_id);
      }
    } catch (err: any) {
      console.error('Failed to load memory data:', err);
      setError(err.message || '加载记忆数据失败');
    } finally {
      if (!silentRefresh) {
      setLoading(false);
      }
    }
  };

  useEffect(() => {
    // 只在首次挂载时加载数据
    if (!isInitializedRef.current) {
      loadData(true, true);
      isInitializedRef.current = true;
    }

    // 监听存档切换事件（切换存档时重新加载）
    const handleArchiveSwitched = () => {
      // 延迟加载，确保数据库已切换
      // 存档切换后需要显示 loading，因为数据会变化
      setTimeout(() => {
        loadData(false, true);
      }, 200);
    };

    // 监听页面切换事件（切换到记忆页面时静默刷新）
    const handleViewSwitched = (event: CustomEvent) => {
      if (event.detail === 'memory' && isInitializedRef.current) {
      // 静默刷新，不改变 loading，避免侧栏闪烁
      loadData(false, false, true);
      }
    };

    window.addEventListener('archiveSwitched', handleArchiveSwitched);
    window.addEventListener('viewSwitched', handleViewSwitched as EventListener);

    return () => {
      window.removeEventListener('archiveSwitched', handleArchiveSwitched);
      window.removeEventListener('viewSwitched', handleViewSwitched as EventListener);
    };
  }, []);

  const selectedCharacter = memoryData.find(c => c.character_id === selectedCharacterId);
  const characterInfo = characters.find(c => c.character_id === selectedCharacterId);

  const toggleScenario = (scenarioId: string) => {
    setExpandedScenarios(prev => {
      const next = new Set(prev);
      if (next.has(scenarioId)) {
        next.delete(scenarioId);
      } else {
        next.add(scenarioId);
      }
      return next;
    });
  };

  const formatTime = (timeStr: string): string => {
    try {
      // Format: 'YYYY-MM-DD HH:MM:SS' -> 'YYYY-MM-DD HH:MM'
      const date = new Date(timeStr.replace(' ', 'T'));
      if (Number.isNaN(date.getTime())) return timeStr;
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hour = String(date.getHours()).padStart(2, '0');
      const minute = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day} ${hour}:${minute}`;
    } catch (e) {
      return timeStr;
    }
  };

  // 只在首次加载且没有数据时显示 loading
  if (loading && memoryData.length === 0 && characters.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400">加载中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400">错误：{error}</div>
      </div>
    );
  }

  return (
    <div className="h-full flex bg-slate-900">
      {/* 左侧角色侧边栏 */}
      <div className="w-64 flex-shrink-0 border-r border-slate-800 bg-gradient-to-b from-[#0b1220] to-[#0a1020] flex flex-col shadow-[0_10px_28px_rgba(0,0,0,0.28)]">
        <div className="p-4 border-b border-slate-800 flex-shrink-0">
          <h2 className="text-lg font-semibold text-slate-100">角色列表</h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          {characters.map((char) => {
            const memory = memoryData.find(m => m.character_id === char.character_id);
            const itemCount = memory?.items.length || 0;
            const isSelected = selectedCharacterId === char.character_id;
            
            return (
              <button
                key={char.character_id}
                onClick={() => setSelectedCharacterId(char.character_id)}
                className={`w-full text-left px-4 py-3 border-b border-slate-800/70 hover:bg-slate-800/60 transition-colors ${
                  isSelected ? 'bg-sky-600/25 border-l-4 border-l-sky-500 shadow-inner shadow-sky-900/40' : ''
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 overflow-hidden shadow-sm">
                    {char.avatar ? (
                      <img src={char.avatar} alt={char.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="text-lg">🎭</div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`font-medium truncate ${isSelected ? 'text-sky-200' : 'text-slate-100'}`}>
                      {char.name}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {itemCount} 项记忆
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
        {/* 刷新按钮 */}
        <div className="p-2 border-t border-slate-700 flex-shrink-0">
          <button
            onClick={() => loadData(false, false)}
            disabled={loading}
            className="w-full px-3 py-2 rounded-md bg-transparent hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            title="刷新记忆数据"
          >
            <span className="text-lg">🔄</span>
            <span className="text-sm">刷新</span>
          </button>
        </div>
      </div>

      {/* 右侧内容区域 */}
      <div className="flex-1 overflow-y-auto p-6">
        {selectedCharacter ? (
          <div>
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-slate-100 mb-2">
                {characterInfo?.name || selectedCharacter.character_name} 的记忆
              </h1>
              <p className="text-slate-400 text-sm">
                共 {selectedCharacter.items.length} 项记忆（按时间排序）
              </p>
            </div>

            {selectedCharacter.items.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                该角色暂无记忆数据
              </div>
            ) : (
              <div className="space-y-3">
                {selectedCharacter.items.map((item, index) => {
                  const isScenario = item.type === 'scenario';
                  const itemId = isScenario ? item.scenario_id! : item.entry_id!;
                  const isExpanded = expandedScenarios.has(itemId);
                  
                  return (
                    <div
                      key={`${item.type}-${itemId}-${index}`}
                      className="bg-slate-800 border border-slate-700 rounded-lg p-4 hover:border-slate-600 transition-colors"
                    >
                      <div className="flex items-start gap-4">
                        {/* 时间范围 */}
                        <div className="flex-shrink-0 w-48 text-sm text-slate-400 font-mono">
                          <div>{formatTime(item.start_at)}</div>
                          <div className="text-slate-500">~ {formatTime(item.end_at)}</div>
                        </div>
                        
                        {/* 类型标签 */}
                        <div className="flex-shrink-0">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            isScenario
                              ? 'bg-purple-600/20 text-purple-300 border border-purple-600/30'
                              : 'bg-blue-600/20 text-blue-300 border border-blue-600/30'
                          }`}>
                            {isScenario ? 'scenario' : 'schedule'}
                          </span>
                        </div>
                        
                        {/* 内容 */}
                        <div className="flex-1 min-w-0">
                          {isScenario ? (
                            <div>
                              <button
                                onClick={() => toggleScenario(itemId)}
                                className="text-left w-full hover:text-sky-400 transition-colors"
                              >
                                <div className="font-medium text-slate-200 mb-1">
                                  {item.title || item.content || '（无标题）'}
                                </div>
                                <div className="text-xs text-slate-400">
                                  {isExpanded ? '点击收起内容' : '点击查看内容'}
                                </div>
                              </button>
                              {isExpanded && item.content && (
                                <div className="mt-3 pt-3 border-t border-slate-700 text-slate-300 whitespace-pre-wrap">
                                  {item.content}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-slate-200 whitespace-pre-wrap">
                              {item.content || '（无内容）'}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-12 text-slate-400">
            请从左侧选择一个角色
          </div>
        )}
      </div>
    </div>
  );
}

