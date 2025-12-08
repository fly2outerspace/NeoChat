'use client';

import { useState, useEffect, useRef } from 'react';
import { getAllRelations, type CharacterRelationResponse, type CharacterRelationItem } from '@/lib/api/memory';
import { listCharacters, type Character } from '@/lib/api/character';

export default function RelationView() {
  const [relationData, setRelationData] = useState<CharacterRelationResponse[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isInitializedRef = useRef(false);

  const loadData = async (isInitialLoad = false, showLoading = true, silentRefresh = false) => {
    try {
      // 只在需要显示 loading 时才设置 loading 状态
      // 如果已有数据，则不显示 loading，避免闪烁
      if (!silentRefresh && (showLoading || relationData.length === 0)) {
        setLoading(true);
      }
      setError(null);
      
      // Load relation data (which includes characters from archive database)
      const relationDataResponse = await getAllRelations();
      
      // Extract characters from relation response (from archive database)
      const charactersFromRelations: Character[] = relationDataResponse.characters.map(char => ({
        id: 0, // Archive characters don't have numeric ID
        character_id: char.character_id,
        name: char.character_name,
        roleplay_prompt: null as string | null, // Not included in relation response
        avatar: null as string | null, // Not included in relation response
        created_at: '',
        updated_at: '',
      }));
      
      // Also load characters from settings to get avatar and other info
      // But use archive characters as the primary source
      let charactersWithDetails: Character[] = charactersFromRelations;
      try {
        const settingsCharacters = await listCharacters();
        // Merge: use archive characters, but enrich with settings data if available
        charactersWithDetails = charactersFromRelations.map(archChar => {
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
      setRelationData(relationDataResponse.characters);
      
      // Auto-select first character only on initial load
      if (isInitialLoad && charactersWithDetails.length > 0 && !selectedCharacterId) {
        setSelectedCharacterId(charactersWithDetails[0].character_id);
      }
    } catch (err: any) {
      console.error('Failed to load relation data:', err);
      setError(err.message || '加载关系数据失败');
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

    // 监听页面切换事件（切换到关系页面时静默刷新）
    const handleViewSwitched = (event: CustomEvent) => {
      if (event.detail === 'relation' && isInitializedRef.current) {
        // 静默刷新，不显示 loading，避免闪烁
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

  const selectedCharacter = relationData.find(c => c.character_id === selectedCharacterId);
  const characterInfo = characters.find(c => c.character_id === selectedCharacterId);

  // 只在首次加载且没有数据时显示 loading
  if (loading && relationData.length === 0 && characters.length === 0) {
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
            const relations = relationData.find(r => r.character_id === char.character_id);
            const relationCount = relations?.relations.length || 0;
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
                      {relationCount} 项关系
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
            title="刷新关系数据"
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
                {characterInfo?.name || selectedCharacter.character_name} 的关系
              </h1>
              <p className="text-slate-400 text-sm">
                共 {selectedCharacter.relations.length} 项关系
              </p>
            </div>

            {selectedCharacter.relations.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                该角色暂无关系数据
              </div>
            ) : (
              <div className="space-y-3">
                {selectedCharacter.relations.map((relation) => {
                  return (
                    <div
                      key={relation.relation_id}
                      className="bg-slate-800 border border-slate-700 rounded-lg p-4 hover:border-slate-600 transition-colors"
                    >
                      <div className="flex items-start gap-4">
                        {/* 角色名 */}
                        <div className="flex-shrink-0 w-32">
                          <div className="font-medium text-slate-200">
                            {relation.name || '（无名称）'}
                          </div>
                        </div>
                        
                        {/* knowledge 和 progress - 上下分行，共处一列 */}
                        <div className="flex-1 min-w-0">
                          <div className="space-y-1">
                            {relation.knowledge && (
                              <div className="text-slate-200 whitespace-pre-wrap text-sm">
                                {relation.knowledge}
                              </div>
                            )}
                            {relation.knowledge && relation.progress && (
                              <div className="border-t border-dashed border-slate-600 my-1.5"></div>
                            )}
                            {relation.progress && (
                              <div className="text-slate-300 whitespace-pre-wrap text-sm">
                                {relation.progress}
                              </div>
                            )}
                            {!relation.knowledge && !relation.progress && (
                              <div className="text-slate-400 text-sm">（无内容）</div>
                            )}
                          </div>
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

