'use client';

import { useState, useEffect, useRef } from 'react';
import {
  getCharacter,
  createCharacter,
  updateCharacter,
  type Character,
  type CharacterCreateRequest,
  type CharacterUpdateRequest,
} from '@/lib/api/character';

const USER_CHARACTER_ID = 'user';
const USER_NAME = '{{user}}';

export default function UserSettings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // User character data
  const [userCharacter, setUserCharacter] = useState<Character | null>(null);
  const [editingName] = useState(USER_NAME); // Fixed name, not editable
  const [editingPrompt, setEditingPrompt] = useState('');
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load user character on mount
  useEffect(() => {
    loadUserCharacter();
  }, []);

  const loadUserCharacter = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try to get existing user character
      try {
        const character = await getCharacter(USER_CHARACTER_ID);
        setUserCharacter(character);
        // Use backend data, or fallback to localStorage draft if backend is empty
        const backendPrompt = character.roleplay_prompt || '';
        const draftPrompt = (() => {
          try {
            const draft = localStorage.getItem('user_prompt');
            return draft ? JSON.parse(draft) : '';
          } catch {
            return '';
          }
        })();
        // Prefer backend data, but if it's empty and we have a draft, use draft
        const promptToUse = backendPrompt || draftPrompt;
        setEditingPrompt(promptToUse);
        setAvatarPreview(character.avatar);
        // Update localStorage with current data
        localStorage.setItem('user_prompt', JSON.stringify(promptToUse));
      } catch (err: any) {
        // If character doesn't exist (404), create it
        if (err.message?.includes('404') || err.message?.includes('not found')) {
          // Try to load draft from localStorage
          const draftPrompt = (() => {
            try {
              const draft = localStorage.getItem('user_prompt');
              return draft ? JSON.parse(draft) : '';
            } catch {
              return '';
            }
          })();
          
          // Create default user character
          const request: CharacterCreateRequest = {
            name: USER_NAME,
            roleplay_prompt: draftPrompt || '',
            avatar: null,
            character_id: USER_CHARACTER_ID,
          };
          const newCharacter = await createCharacter(request);
          setUserCharacter(newCharacter);
          setEditingPrompt(draftPrompt);
          setAvatarPreview(null);
          // Update localStorage
          localStorage.setItem('user_prompt', JSON.stringify(draftPrompt));
          // Trigger characters reload event to update character list in ChatArea
          window.dispatchEvent(new CustomEvent('charactersReloaded'));
        } else {
          throw err;
        }
      }
    } catch (err: any) {
      setError(err.message || '加载用户设置失败');
      console.error('Failed to load user character:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check file type
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    // Check file size (limit 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert('图片大小不能超过 2MB');
      return;
    }

    // Read file and convert to Base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      setAvatarPreview(result);
    };
    reader.readAsDataURL(file);
  };

  // Save prompt draft to localStorage when editing
  useEffect(() => {
    if (userCharacter) {
      localStorage.setItem('user_prompt', JSON.stringify(editingPrompt));
    }
  }, [editingPrompt, userCharacter]);

  const handleSave = async () => {
    if (!userCharacter) return;

    try {
      setSaving(true);
      setError(null);
      
      const request: CharacterUpdateRequest = {
        name: USER_NAME, // Always use fixed name
        roleplay_prompt: editingPrompt.trim() || null,
        avatar: avatarPreview || null,
      };
      
      const updated = await updateCharacter(USER_CHARACTER_ID, request);
      setUserCharacter(updated);
      
      // Update localStorage with saved data
      localStorage.setItem('user_prompt', JSON.stringify(updated.roleplay_prompt || ''));
      
      // Update localStorage and trigger event
      const characterInfo = {
        character_id: updated.character_id,
        name: updated.name,
        roleplay_prompt: updated.roleplay_prompt || null,
      };
      
      // Check if this user is currently selected
      const storedCharacter = localStorage.getItem('selected_character');
      if (storedCharacter) {
        try {
          const storedCharacterInfo = JSON.parse(storedCharacter);
          if (storedCharacterInfo.character_id === USER_CHARACTER_ID) {
            localStorage.setItem('selected_character', JSON.stringify(characterInfo));
            // Trigger event to notify ChatArea
            window.dispatchEvent(new CustomEvent('characterUpdated', { 
              detail: characterInfo 
            }));
          }
        } catch (e) {
          console.error('Failed to parse stored character:', e);
        }
      }
      
      // Trigger characters reload event to update character list in ChatArea
      window.dispatchEvent(new CustomEvent('charactersReloaded'));
      
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: any) {
      setError(err.message || '保存失败');
      console.error('Failed to save user character:', err);
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

  const hasChanges = userCharacter && (
    editingPrompt !== (userCharacter.roleplay_prompt || '') ||
    avatarPreview !== (userCharacter.avatar || null)
  );

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">用户设置</h2>
        <p className="text-sm text-slate-400 mt-1">
          管理用户信息，包括名称、提示词和头像
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-md text-sm text-red-300">
          {error}
        </div>
      )}

      {/* User settings area */}
      <div className="panel p-6">
        {loading ? (
          <div className="text-center py-8 text-slate-400">加载中...</div>
        ) : (
          <div className="space-y-6">
            {/* User name */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                用户名称
              </label>
              <input
                type="text"
                value={editingName}
                disabled
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-400 cursor-not-allowed"
              />
              <p className="text-xs text-slate-500 mt-1">
                用户名称固定为 {USER_NAME}，不可更改
              </p>
            </div>

            {/* User avatar */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                用户头像
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
                      <div className="text-4xl text-slate-500">👤</div>
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

            {/* User prompt */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                用户提示词
              </label>
              <textarea
                value={editingPrompt}
                onChange={(e) => setEditingPrompt(e.target.value)}
                placeholder="请输入用户提示词..."
                rows={12}
                className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono text-sm"
              />
              <p className="text-xs text-slate-500 mt-1">
                定义用户角色的提示词，用于角色扮演场景
              </p>
            </div>

            {/* Save button */}
            <div className="flex gap-3 pt-4 border-t border-slate-700">
              <button
                onClick={handleSave}
                disabled={!hasChanges || saving}
                className="px-6 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
              >
                {saving ? '保存中...' : saved ? '✓ 已保存' : '保存更改'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
