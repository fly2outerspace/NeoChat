'use client';

import { useState, useEffect, useRef } from 'react';
import {
  listCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  type Character,
  type CharacterCreateRequest,
  type CharacterUpdateRequest,
} from '@/lib/api/character';
import { useLocalStorageInput } from '@/lib/useLocalStorageInput';

export default function RoleSettings() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 标记是否已经完成首次同步（用于区分首次加载和用户切换）
  const hasInitializedRef = useRef(false);
  // 记录当前同步的角色 ID，用于判断是否是切换角色
  const syncedCharacterIdRef = useRef<string | null>(null);
  // 记录当前正在编辑的角色 ID
  const currentEditingCharacterIdRef = useRef<string | null>(null);

  // 辅助函数：保存当前角色的编辑状态到 localStorage（使用角色ID作为key）
  // 注意：这个函数接收状态值作为参数，避免闭包问题
  const saveCharacterEditingState = (
    characterId: string,
    state: {
      name: string;
      prompt: string;
      avatar: string | null;
    }
  ) => {
    if (!characterId) return;
    try {
      localStorage.setItem(`character_editing_state_${characterId}`, JSON.stringify(state));
    } catch (e) {
      console.error('Failed to save character editing state:', e);
    }
  };

  // 辅助函数：从 localStorage 加载指定角色的编辑状态
  const loadCharacterEditingState = (characterId: string): {
    name: string;
    prompt: string;
    avatar: string | null;
  } | null => {
    if (!characterId) return null;
    try {
      const stored = localStorage.getItem(`character_editing_state_${characterId}`);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to load character editing state:', e);
    }
    return null;
  };

  // 编辑状态 - 使用普通 state，通过 useEffect 同步到 localStorage
  const [editingName, setEditingName] = useState('');
  const [editingPrompt, setEditingPrompt] = useState('');
  const [editingAvatar, setEditingAvatar] = useState<string | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 当编辑状态变化时，保存到 localStorage（针对当前角色）
  useEffect(() => {
    if (currentEditingCharacterIdRef.current) {
      saveCharacterEditingState(currentEditingCharacterIdRef.current, {
        name: editingName,
        prompt: editingPrompt,
        avatar: avatarPreview,
      });
    }
  }, [editingName, editingPrompt, avatarPreview]);

  // 组件卸载时保存当前编辑状态
  useEffect(() => {
    return () => {
      if (currentEditingCharacterIdRef.current) {
        saveCharacterEditingState(currentEditingCharacterIdRef.current, {
          name: editingName,
          prompt: editingPrompt,
          avatar: avatarPreview,
        });
      }
    };
  }, [editingName, editingPrompt, avatarPreview]);

  // 创建新角色的状态 - persist to localStorage
  const [isCreating, setIsCreating] = useState(false);
  const [newCharacterName, setNewCharacterName] = useLocalStorageInput('role_new_name', '');
  const [newCharacterPrompt, setNewCharacterPrompt] = useLocalStorageInput('role_new_prompt', '');
  const [newCharacterAvatar, setNewCharacterAvatar] = useState<string | null>(null);
  const [newCharacterAvatarPreview, setNewCharacterAvatarPreview] = useState<string | null>(null);
  const newCharacterFileInputRef = useRef<HTMLInputElement>(null);

  // 页面加载时同步数据
  useEffect(() => {
    loadCharacters();
  }, []);

  // 监听 localStorage 清空事件，重新加载数据
  useEffect(() => {
    const handleLocalStorageCleared = () => {
      // 重置状态
      hasInitializedRef.current = false;
      syncedCharacterIdRef.current = null;
      currentEditingCharacterIdRef.current = null;
      // 重新加载角色列表（会从数据库同步）
      loadCharacters();
    };

    window.addEventListener('localStorageCleared', handleLocalStorageCleared);
    return () => {
      window.removeEventListener('localStorageCleared', handleLocalStorageCleared);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当选择角色变化时，保存当前编辑状态并加载新角色的编辑状态
  useEffect(() => {
    if (selectedCharacter) {
      const isCharacterChanged = syncedCharacterIdRef.current !== null && 
                                 syncedCharacterIdRef.current !== selectedCharacter.character_id;
      
      if (isCharacterChanged) {
        // 切换角色时，先保存当前角色的编辑状态
        if (currentEditingCharacterIdRef.current) {
          saveCharacterEditingState(currentEditingCharacterIdRef.current, {
            name: editingName,
            prompt: editingPrompt,
            avatar: avatarPreview,
          });
        }
        
        // 加载新角色的编辑状态
        const savedState = loadCharacterEditingState(selectedCharacter.character_id);
        if (savedState) {
          // 如果有保存的编辑状态，使用保存的状态
          setEditingName(savedState.name);
          setEditingPrompt(savedState.prompt);
          setEditingAvatar(savedState.avatar);
          setAvatarPreview(savedState.avatar);
        } else {
          // 如果没有保存的编辑状态，使用后台数据
          setEditingName(selectedCharacter.name);
          setEditingPrompt(selectedCharacter.roleplay_prompt || '');
          setEditingAvatar(selectedCharacter.avatar);
          setAvatarPreview(selectedCharacter.avatar);
        }
        
        currentEditingCharacterIdRef.current = selectedCharacter.character_id;
        syncedCharacterIdRef.current = selectedCharacter.character_id;
      } else if (!hasInitializedRef.current) {
        // 首次加载时，尝试加载保存的编辑状态，如果没有则使用后台数据
        const savedState = loadCharacterEditingState(selectedCharacter.character_id);
        if (savedState) {
          setEditingName(savedState.name);
          setEditingPrompt(savedState.prompt);
          setEditingAvatar(savedState.avatar);
          setAvatarPreview(savedState.avatar);
        } else {
          // 如果没有保存的状态，使用后台数据
          setEditingName(selectedCharacter.name);
          setEditingPrompt(selectedCharacter.roleplay_prompt || '');
          setEditingAvatar(selectedCharacter.avatar);
          setAvatarPreview(selectedCharacter.avatar);
        }
        
        currentEditingCharacterIdRef.current = selectedCharacter.character_id;
        syncedCharacterIdRef.current = selectedCharacter.character_id;
        hasInitializedRef.current = true;
      }
    } else {
      // 不选择角色时不清空，保留草稿
      setEditingAvatar(null);
      setAvatarPreview(null);
    }
  }, [selectedCharacter]);

  const loadCharacters = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listCharacters();
      setCharacters(data);
      
      // 从 localStorage 加载选中的角色
      const stored = localStorage.getItem('selected_character');
      let characterToSelect: Character | null = null;
      
      if (stored) {
        try {
          const characterInfo = JSON.parse(stored);
          const found = data.find(c => c.character_id === characterInfo.character_id);
          if (found) {
            characterToSelect = found;
          }
        } catch (e) {
          console.error('Failed to parse stored character:', e);
        }
      }
      
      // 如果有选中的角色，更新它
      if (selectedCharacter) {
        const updated = data.find(c => c.character_id === selectedCharacter.character_id);
        if (updated) {
          setSelectedCharacter(updated);
        } else {
          // 如果选中的角色被删除了，清空选择
          setSelectedCharacter(null);
        }
      } else if (characterToSelect) {
        // 从 localStorage 恢复选中的角色
        setSelectedCharacter(characterToSelect);
      } else if (data.length > 0) {
        // 如果没有选中的角色，自动选择第一个
        setSelectedCharacter(data[0]);
      }
    } catch (err: any) {
      setError(err.message || '加载角色列表失败');
      console.error('Failed to load characters:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCharacter = (character: Character) => {
    setSelectedCharacter(character);
    setIsCreating(false);
  };

  const handleCreateNew = () => {
    setIsCreating(true);
    setSelectedCharacter(null);
    // 不清空草稿，保留用户之前的输入
    // 只清空头像（因为头像不是文本输入）
    setNewCharacterAvatar(null);
    setNewCharacterAvatarPreview(null);
    if (newCharacterFileInputRef.current) {
      newCharacterFileInputRef.current.value = '';
    }
  };

  const handleCreateCharacter = async () => {
    if (!newCharacterName.trim()) {
      alert('请输入角色名称');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const request: CharacterCreateRequest = {
        name: newCharacterName.trim(),
        roleplay_prompt: newCharacterPrompt.trim() || null,
        avatar: newCharacterAvatarPreview || null,
      };
      const newCharacter = await createCharacter(request);
      await loadCharacters();
      setSelectedCharacter(newCharacter);
      setIsCreating(false);
      // 清空创建表单（包括 localStorage 草稿）
      setNewCharacterName('');
      setNewCharacterPrompt('');
      setNewCharacterAvatar(null);
      setNewCharacterAvatarPreview(null);
      if (newCharacterFileInputRef.current) {
        newCharacterFileInputRef.current.value = '';
      }
    } catch (err: any) {
      setError(err.message || '创建角色失败');
      console.error('Failed to create character:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleNewCharacterFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 检查文件类型
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    // 检查文件大小（限制 2MB）
    if (file.size > 2 * 1024 * 1024) {
      alert('图片大小不能超过 2MB');
      return;
    }

    // 读取文件并转换为 Base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      setNewCharacterAvatarPreview(result);
    };
    reader.readAsDataURL(file);
  };

  const handleClearNewCharacterAvatar = () => {
    setNewCharacterAvatarPreview(null);
    if (newCharacterFileInputRef.current) {
      newCharacterFileInputRef.current.value = '';
    }
  };

  const handleNewCharacterUploadClick = () => {
    newCharacterFileInputRef.current?.click();
  };

  const handleDeleteCharacter = async (character: Character) => {
    if (!confirm(`确定要删除角色 "${character.name}" 吗？此操作不可恢复。`)) {
      return;
    }

    try {
      setError(null);
      await deleteCharacter(character.character_id);
      await loadCharacters();
      if (selectedCharacter?.character_id === character.character_id) {
        setSelectedCharacter(null);
      }
    } catch (err: any) {
      setError(err.message || '删除角色失败');
      console.error('Failed to delete character:', err);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 检查文件类型
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    // 检查文件大小（限制 2MB）
    if (file.size > 2 * 1024 * 1024) {
      alert('图片大小不能超过 2MB');
      return;
    }

    // 读取文件并转换为 Base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      setAvatarPreview(result);
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    if (!selectedCharacter) return;

    try {
      setSaving(true);
      setError(null);
      const request: CharacterUpdateRequest = {
        name: editingName.trim(),
        roleplay_prompt: editingPrompt.trim() || null,
        avatar: avatarPreview || null,
      };
      const updated = await updateCharacter(selectedCharacter.character_id, request);
      await loadCharacters();
      setSelectedCharacter(updated);
      
      // 如果当前保存的角色是当前选中的角色（在 localStorage 中），则更新 localStorage 并触发事件
      const storedCharacter = localStorage.getItem('selected_character');
      if (storedCharacter) {
        try {
          const storedCharacterInfo = JSON.parse(storedCharacter);
          if (storedCharacterInfo.character_id === updated.character_id) {
            // 更新 localStorage
            const characterInfo = {
              character_id: updated.character_id,
              name: updated.name,
              roleplay_prompt: updated.roleplay_prompt || null,
            };
            localStorage.setItem('selected_character', JSON.stringify(characterInfo));
            
            // 触发事件通知 ChatArea 更新
            window.dispatchEvent(new CustomEvent('characterUpdated', { 
              detail: characterInfo 
            }));
          }
        } catch (e) {
          console.error('Failed to parse stored character:', e);
        }
      }
    } catch (err: any) {
      setError(err.message || '保存失败');
      console.error('Failed to save character:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleClearAvatar = () => {
    setAvatarPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const hasChanges = selectedCharacter && (
    editingName !== selectedCharacter.name ||
    editingPrompt !== (selectedCharacter.roleplay_prompt || '') ||
    avatarPreview !== (selectedCharacter.avatar || null)
  );

  return (
    <div>
      {/* 标题和说明 */}
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">角色设置</h2>
        <p className="text-sm text-slate-400 mt-1">
          创建和管理 AI 角色，包括角色名称、头像和角色扮演提示词
        </p>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-md text-sm text-red-300">
          {error}
        </div>
      )}

      {/* 角色设置区域 */}
      <div className="bg-slate-950 border border-slate-700 rounded-lg overflow-hidden">
        <div className="flex" style={{ height: 'calc(100vh - 200px)', minHeight: '600px' }}>
          {/* 左侧侧边栏 */}
          <div className="w-64 border-r border-slate-700 flex flex-col">
            <div className="p-4 border-b border-slate-700">
              <button
                onClick={handleCreateNew}
                className="w-full px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-700 text-sm font-medium transition-colors"
              >
                + 创建新角色
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="p-4 text-sm text-slate-400 text-center">加载中...</div>
              ) : characters.length === 0 ? (
                <div className="p-4 text-sm text-slate-400 text-center">
                  暂无角色，点击上方按钮创建
                </div>
              ) : (
                <div className="p-2 space-y-1">
                  {characters.map((character) => (
                    <div
                      key={character.character_id}
                      className={`group relative p-3 rounded-md cursor-pointer transition-colors ${
                        selectedCharacter?.character_id === character.character_id
                          ? 'bg-sky-600/20 border border-sky-600'
                          : 'hover:bg-slate-800'
                      }`}
                      onClick={() => handleSelectCharacter(character)}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                          {character.avatar ? (
                            <img
                              src={character.avatar}
                              alt={character.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="text-xl text-slate-500">🤖</div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-slate-200 truncate">
                            {character.name}
                          </div>
                          <div className="text-xs text-slate-400 truncate">
                            {character.character_id}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteCharacter(character);
                        }}
                        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-600/20 text-red-400 hover:text-red-300 transition-opacity"
                        title="删除角色"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 右侧详情区域 */}
          <div className="flex-1 overflow-y-auto p-6">
            {isCreating ? (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4">创建新角色</h3>
                  
                  {/* 角色名称 */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      角色名称 *
                    </label>
                    <input
                      type="text"
                      value={newCharacterName}
                      onChange={(e) => setNewCharacterName(e.target.value)}
                      placeholder="请输入角色名称"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* 角色头像 */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      角色头像
                    </label>
                    <div className="flex items-start space-x-4">
                      <div className="flex-shrink-0">
                        <div className="w-24 h-24 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center overflow-hidden">
                          {newCharacterAvatarPreview ? (
                            <img
                              src={newCharacterAvatarPreview}
                              alt="头像预览"
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="text-4xl text-slate-500">🤖</div>
                          )}
                        </div>
                      </div>
                      <div className="flex-1 space-y-2">
                        <input
                          ref={newCharacterFileInputRef}
                          type="file"
                          accept="image/*"
                          onChange={handleNewCharacterFileSelect}
                          className="hidden"
                        />
                        <button
                          onClick={handleNewCharacterUploadClick}
                          className="px-4 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-sm font-medium transition-colors"
                        >
                          选择图片
                        </button>
                        {newCharacterAvatarPreview && (
                          <button
                            onClick={handleClearNewCharacterAvatar}
                            className="px-4 py-2 rounded-md bg-red-600 hover:bg-red-700 text-sm font-medium transition-colors"
                          >
                            清除头像
                          </button>
                        )}
                        <p className="text-xs text-slate-500">
                          支持 JPG、PNG、WebP 格式，最大 2MB
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 角色提示词 */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      角色扮演提示词
                    </label>
                    <textarea
                      value={newCharacterPrompt}
                      onChange={(e) => setNewCharacterPrompt(e.target.value)}
                      placeholder="请输入角色扮演提示词..."
                      rows={24}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono text-sm"
                    />
                  </div>

                  {/* 保存按钮 */}
                  <div className="flex gap-3 pt-4 border-t border-slate-700">
                    <button
                      onClick={handleCreateCharacter}
                      disabled={!newCharacterName.trim() || saving}
                      className="px-6 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                    >
                      {saving ? '保存中...' : '保存'}
                    </button>
                    <button
                      onClick={() => {
                        setIsCreating(false);
                        setNewCharacterName('');
                        setNewCharacterPrompt('');
                        setNewCharacterAvatar(null);
                        setNewCharacterAvatarPreview(null);
                        if (newCharacterFileInputRef.current) {
                          newCharacterFileInputRef.current.value = '';
                        }
                        if (characters.length > 0) {
                          setSelectedCharacter(characters[0]);
                        }
                      }}
                      className="px-6 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-sm font-medium transition-colors"
                    >
                      取消
                    </button>
                  </div>
                </div>
              </div>
            ) : selectedCharacter ? (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4">角色详情</h3>
                  
                  {/* 角色名称 */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      角色名称
                    </label>
                    <input
                      type="text"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* 角色头像 */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      角色头像
                    </label>
                    <div className="flex items-start space-x-4">
                      <div className="flex-shrink-0">
                        <div className="w-24 h-24 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center overflow-hidden">
                          {avatarPreview ? (
                            <img
                              src={avatarPreview}
                              alt="头像预览"
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="text-4xl text-slate-500">🤖</div>
                          )}
                        </div>
                      </div>
                      <div className="flex-1 space-y-2">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/*"
                          onChange={handleFileSelect}
                          className="hidden"
                        />
                        <button
                          onClick={handleUploadClick}
                          className="px-4 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-sm font-medium transition-colors"
                        >
                          选择图片
                        </button>
                        {avatarPreview && (
                          <button
                            onClick={handleClearAvatar}
                            className="px-4 py-2 rounded-md bg-red-600 hover:bg-red-700 text-sm font-medium transition-colors"
                          >
                            清除头像
                          </button>
                        )}
                        <p className="text-xs text-slate-500">
                          支持 JPG、PNG、WebP 格式，最大 2MB
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 角色提示词 */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      角色扮演提示词
                    </label>
                    <textarea
                      value={editingPrompt}
                      onChange={(e) => setEditingPrompt(e.target.value)}
                      placeholder="请输入角色扮演提示词..."
                      rows={24}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono text-sm"
                    />
                  </div>

                  {/* 保存按钮 */}
                  <div className="flex gap-3 pt-4 border-t border-slate-700">
                    <button
                      onClick={handleSave}
                      disabled={!hasChanges || saving}
                      className="px-6 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                    >
                      {saving ? '保存中...' : '保存更改'}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400">
                <div className="text-center">
                  <div className="text-4xl mb-4">📝</div>
                  <p>请从左侧选择一个角色，或创建新角色</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


