'use client';

import { useState, useEffect, useRef } from 'react';
import {
  listModels,
  createModel,
  updateModel,
  deleteModel,
  getModel,
  type Model,
  type ModelCreateRequest,
  type ModelUpdateRequest,
} from '@/lib/api/model';
import { useLocalStorageInput } from '@/lib/useLocalStorageInput';

export default function ModelSettings() {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 标记是否已经完成首次同步（用于区分首次加载和用户切换）
  const hasInitializedRef = useRef(false);
  // 记录当前同步的模型 ID，用于判断是否是切换模型
  const syncedModelIdRef = useRef<string | null>(null);
  // 记录当前正在编辑的模型 ID
  const currentEditingModelIdRef = useRef<string | null>(null);

  // 辅助函数：保存当前模型的编辑状态到 localStorage（使用模型ID作为key）
  // 注意：这个函数接收状态值作为参数，避免闭包问题
  const saveModelEditingState = (
    modelId: string,
    state: {
      name: string;
      provider: string;
      model: string;
      base_url: string;
      api_key: string;
      max_tokens: number;
      temperature: number;
      api_type: string;
    }
  ) => {
    if (!modelId) return;
    try {
      localStorage.setItem(`model_editing_state_${modelId}`, JSON.stringify(state));
    } catch (e) {
      console.error('Failed to save model editing state:', e);
    }
  };

  // 辅助函数：从 localStorage 加载指定模型的编辑状态
  const loadModelEditingState = (modelId: string): {
    name: string;
    provider: string;
    model: string;
    base_url: string;
    api_key: string;
    max_tokens: number;
    temperature: number;
    api_type: string;
  } | null => {
    if (!modelId) return null;
    try {
      const stored = localStorage.getItem(`model_editing_state_${modelId}`);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to load model editing state:', e);
    }
    return null;
  };

  // 编辑状态 - 使用普通 state，通过 useEffect 同步到 localStorage
  const [editingName, setEditingName] = useState('');
  const [editingProvider, setEditingProvider] = useState('');
  const [editingModel, setEditingModel] = useState('');
  const [editingBaseUrl, setEditingBaseUrl] = useState('');
  const [editingApiKey, setEditingApiKey] = useState('');
  const [editingMaxTokens, setEditingMaxTokens] = useState(4096);
  const [editingTemperature, setEditingTemperature] = useState(1.0);
  const [editingApiType, setEditingApiType] = useState('openai');
  const [showApiKey, setShowApiKey] = useState(false); // 控制API Key显示/隐藏

  // 当编辑状态变化时，保存到 localStorage（针对当前模型）
  useEffect(() => {
    if (currentEditingModelIdRef.current) {
      saveModelEditingState(currentEditingModelIdRef.current, {
        name: editingName,
        provider: editingProvider,
        model: editingModel,
        base_url: editingBaseUrl,
        api_key: editingApiKey,
        max_tokens: editingMaxTokens,
        temperature: editingTemperature,
        api_type: editingApiType,
      });
    }
  }, [editingName, editingProvider, editingModel, editingBaseUrl, editingApiKey, editingMaxTokens, editingTemperature, editingApiType]);

  // 组件卸载时保存当前编辑状态
  useEffect(() => {
    return () => {
      if (currentEditingModelIdRef.current) {
        saveModelEditingState(currentEditingModelIdRef.current, {
          name: editingName,
          provider: editingProvider,
          model: editingModel,
          base_url: editingBaseUrl,
          api_key: editingApiKey,
          max_tokens: editingMaxTokens,
          temperature: editingTemperature,
          api_type: editingApiType,
        });
      }
    };
  }, [editingName, editingProvider, editingModel, editingBaseUrl, editingApiKey, editingMaxTokens, editingTemperature, editingApiType]);

  // 创建新模型的状态 - persist to localStorage
  const [isCreating, setIsCreating] = useState(false);
  const [newModelName, setNewModelName] = useLocalStorageInput('model_new_name', '');
  const [newModelProvider, setNewModelProvider] = useLocalStorageInput('model_new_provider', '');
  const [newModelModel, setNewModelModel] = useLocalStorageInput('model_new_model', '');
  const [newModelBaseUrl, setNewModelBaseUrl] = useLocalStorageInput('model_new_base_url', '');
  const [newModelApiKey, setNewModelApiKey] = useLocalStorageInput('model_new_api_key', '');
  const [newModelMaxTokens, setNewModelMaxTokens] = useLocalStorageInput('model_new_max_tokens', 4096);
  const [newModelTemperature, setNewModelTemperature] = useLocalStorageInput('model_new_temperature', 1.0);
  const [newModelApiType, setNewModelApiType] = useLocalStorageInput('model_new_api_type', 'openai');

  // 页面加载时同步数据
  useEffect(() => {
    loadModels();
  }, []);

  // 监听 localStorage 清空事件，重新加载数据
  useEffect(() => {
    const handleLocalStorageCleared = () => {
      // 重置状态
      hasInitializedRef.current = false;
      syncedModelIdRef.current = null;
      currentEditingModelIdRef.current = null;
      // 重新加载模型列表（会从数据库同步）
      loadModels();
    };

    window.addEventListener('localStorageCleared', handleLocalStorageCleared);
    return () => {
      window.removeEventListener('localStorageCleared', handleLocalStorageCleared);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当选中模型变化时，保存当前编辑状态并加载新模型的编辑状态
  useEffect(() => {
    if (selectedModel) {
      const isModelChanged = syncedModelIdRef.current !== null && 
                            syncedModelIdRef.current !== selectedModel.model_id;
      
      if (isModelChanged) {
        // 切换模型时，先保存当前模型的编辑状态
        if (currentEditingModelIdRef.current) {
          saveModelEditingState(currentEditingModelIdRef.current, {
            name: editingName,
            provider: editingProvider,
            model: editingModel,
            base_url: editingBaseUrl,
            api_key: editingApiKey,
            max_tokens: editingMaxTokens,
            temperature: editingTemperature,
            api_type: editingApiType,
          });
        }
        
        // 加载新模型的编辑状态
        const savedState = loadModelEditingState(selectedModel.model_id);
        if (savedState) {
          // 如果有保存的编辑状态，使用保存的状态
          setEditingName(savedState.name);
          setEditingProvider(savedState.provider);
          setEditingModel(savedState.model);
          setEditingBaseUrl(savedState.base_url);
          setEditingApiKey(savedState.api_key);
          setEditingMaxTokens(savedState.max_tokens);
          setEditingTemperature(savedState.temperature);
          setEditingApiType(savedState.api_type);
        } else {
          // 如果没有保存的编辑状态，使用后台数据
          setEditingName(selectedModel.name);
          setEditingProvider(selectedModel.provider);
          setEditingModel(selectedModel.model);
          setEditingBaseUrl(selectedModel.base_url);
          setEditingApiKey(selectedModel.api_key || '');
          setEditingMaxTokens(selectedModel.max_tokens);
          setEditingTemperature(selectedModel.temperature);
          setEditingApiType(selectedModel.api_type);
        }
        
        currentEditingModelIdRef.current = selectedModel.model_id;
        syncedModelIdRef.current = selectedModel.model_id;
      } else if (!hasInitializedRef.current) {
        // 首次加载时，尝试加载保存的编辑状态，如果没有则使用后台数据
        const savedState = loadModelEditingState(selectedModel.model_id);
        if (savedState) {
          setEditingName(savedState.name);
          setEditingProvider(savedState.provider);
          setEditingModel(savedState.model);
          setEditingBaseUrl(savedState.base_url);
          setEditingApiKey(savedState.api_key);
          setEditingMaxTokens(savedState.max_tokens);
          setEditingTemperature(savedState.temperature);
          setEditingApiType(savedState.api_type);
        } else {
          // 如果没有保存的状态，使用后台数据
          setEditingName(selectedModel.name);
          setEditingProvider(selectedModel.provider);
          setEditingModel(selectedModel.model);
          setEditingBaseUrl(selectedModel.base_url);
          setEditingApiKey(selectedModel.api_key || '');
          setEditingMaxTokens(selectedModel.max_tokens);
          setEditingTemperature(selectedModel.temperature);
          setEditingApiType(selectedModel.api_type);
        }
        
        currentEditingModelIdRef.current = selectedModel.model_id;
        syncedModelIdRef.current = selectedModel.model_id;
        hasInitializedRef.current = true;
      }
    }
  }, [selectedModel]);

  // 不再自动覆盖草稿，保持用户输入
  // 只在创建新模型时，如果 localStorage 中没有草稿，才会使用默认值

  const loadModels = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listModels();
      setModels(data);
      
      // 从 localStorage 加载选中的模型
      const stored = localStorage.getItem('selected_model');
      let modelToSelect: Model | null = null;
      
      if (stored) {
        try {
          const modelInfo = JSON.parse(stored);
          const found = data.find(m => m.model_id === modelInfo.model_id);
          if (found) {
            modelToSelect = found;
          }
        } catch (e) {
          console.error('Failed to parse stored model:', e);
        }
      }
      
      // 如果有选中的模型，更新它（需要重新获取以包含 API key）
      if (selectedModel) {
        try {
          const updated = await getModel(selectedModel.model_id, true);
          setSelectedModel(updated);
        } catch (e) {
          // 如果获取失败，使用列表中的数据
          const updated = data.find(m => m.model_id === selectedModel.model_id);
          if (updated) {
            setSelectedModel(updated);
          } else {
            setSelectedModel(null);
          }
        }
      } else if (modelToSelect) {
        // 从 localStorage 恢复选中的模型
        try {
          const fullModel = await getModel(modelToSelect.model_id, true);
          setSelectedModel(fullModel);
        } catch (e) {
          setSelectedModel(modelToSelect);
        }
      } else if (data.length > 0) {
        // 如果没有选中的模型，自动选择第一个
        try {
          const firstModel = await getModel(data[0].model_id, true);
          setSelectedModel(firstModel);
        } catch (e) {
          setSelectedModel(data[0]);
        }
      }
    } catch (err: any) {
      setError(err.message || '加载模型列表失败');
      console.error('Failed to load models:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectModel = async (model: Model) => {
    setIsCreating(false);
    try {
      // 获取完整模型信息（包含 API key）
      const fullModel = await getModel(model.model_id, true);
      setSelectedModel(fullModel);
      
      // 保存到 localStorage（全局应用）
      const modelInfo = {
        model_id: fullModel.model_id,
        name: fullModel.name,
        provider: fullModel.provider,
        model: fullModel.model,
        base_url: fullModel.base_url,
        api_key: fullModel.api_key,
        max_tokens: fullModel.max_tokens,
        temperature: fullModel.temperature,
        api_type: fullModel.api_type,
      };
      localStorage.setItem('selected_model', JSON.stringify(modelInfo));
      
      // 触发自定义事件，通知其他组件模型已更新
      window.dispatchEvent(new CustomEvent('modelUpdated', { detail: modelInfo }));
    } catch (e) {
      // 如果获取失败，使用列表中的数据
      setSelectedModel(model);
      
      // 仍然保存到 localStorage
      const modelInfo = {
        model_id: model.model_id,
        name: model.name,
        provider: model.provider,
        model: model.model,
        base_url: model.base_url,
        api_key: null, // 无法获取 API key
        max_tokens: model.max_tokens,
        temperature: model.temperature,
        api_type: model.api_type,
      };
      localStorage.setItem('selected_model', JSON.stringify(modelInfo));
      window.dispatchEvent(new CustomEvent('modelUpdated', { detail: modelInfo }));
    }
  };

  const handleCreateNew = () => {
    setIsCreating(true);
    setSelectedModel(null);
    // 不清空，保留草稿以便用户继续编辑
  };

  const handleCreateModel = async () => {
    if (!newModelName.trim() || !newModelProvider.trim() || !newModelModel.trim() || !newModelBaseUrl.trim()) {
      alert('请填写所有必填字段（名称、提供商、模型、基础地址）');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const request: ModelCreateRequest = {
        name: newModelName.trim(),
        provider: newModelProvider.trim(),
        model: newModelModel.trim(),
        base_url: newModelBaseUrl.trim(),
        api_key: newModelApiKey.trim() || null,
        max_tokens: newModelMaxTokens,
        temperature: newModelTemperature,
        api_type: newModelApiType,
      };
      const newModel = await createModel(request);
      await loadModels();
      // 重新获取完整模型信息
      try {
        const fullModel = await getModel(newModel.model_id, true);
        setSelectedModel(fullModel);
      } catch (e) {
        setSelectedModel(newModel);
      }
      setIsCreating(false);
      // 清空创建表单草稿（包括 localStorage）
      setNewModelName('');
      setNewModelProvider('');
      setNewModelModel('');
      setNewModelBaseUrl('');
      setNewModelApiKey('');
      setNewModelMaxTokens(4096);
      setNewModelTemperature(1.0);
      setNewModelApiType('openai');
    } catch (err: any) {
      setError(err.message || '创建模型失败');
      console.error('Failed to create model:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteModel = async (model: Model) => {
    if (!confirm(`确定要删除模型配置 "${model.name}" 吗？此操作不可恢复。`)) {
      return;
    }

    try {
      setError(null);
      await deleteModel(model.model_id);
      await loadModels();
      if (selectedModel?.model_id === model.model_id) {
        setSelectedModel(null);
      }
    } catch (err: any) {
      setError(err.message || '删除模型失败');
      console.error('Failed to delete model:', err);
    }
  };

  const handleSave = async () => {
    if (!selectedModel) return;

    try {
      setSaving(true);
      setError(null);
      const request: ModelUpdateRequest = {
        name: editingName.trim(),
        provider: editingProvider.trim(),
        model: editingModel.trim(),
        base_url: editingBaseUrl.trim(),
        max_tokens: editingMaxTokens,
        temperature: editingTemperature,
        api_type: editingApiType,
      };
      
      // API key 处理：如果原来有值但现在为空，表示用户想清空；如果原来没有值且现在也为空，不发送（不修改）
      const originalApiKey = selectedModel.api_key || '';
      const newApiKey = editingApiKey.trim();
      if (originalApiKey && !newApiKey) {
        // 原来有值，现在为空，表示清空
        request.api_key = null;
      } else if (newApiKey) {
        // 有新值，更新
        request.api_key = newApiKey;
      }
      // 如果原来没有值且现在也没有值，不发送 api_key 字段（不修改）
      
      const updated = await updateModel(selectedModel.model_id, request);
      await loadModels();
      // 使用统一的选择逻辑，同步到全局（localStorage + 自定义事件）
      await handleSelectModel(updated);
    } catch (err: any) {
      setError(err.message || '保存失败');
      console.error('Failed to save model:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateFromTemplate = async () => {
    // 验证必填字段
    if (!editingName.trim() || !editingProvider.trim() || !editingModel.trim() || !editingBaseUrl.trim()) {
      alert('请填写所有必填字段（名称、提供商、模型、基础地址）');
      return;
    }

    try {
      setSaving(true);
      setError(null);
      
      // 生成新名称（在原名称后添加" (副本)"）
      const newName = `${editingName.trim()} (副本)`;
      
      const request: ModelCreateRequest = {
        name: newName,
        provider: editingProvider.trim(),
        model: editingModel.trim(),
        base_url: editingBaseUrl.trim(),
        api_key: editingApiKey.trim() || null,
        max_tokens: editingMaxTokens,
        temperature: editingTemperature,
        api_type: editingApiType,
      };
      
      const newModel = await createModel(request);
      await loadModels();
      // 选中新创建的模型，并同步到全局（localStorage + 自定义事件）
      await handleSelectModel(newModel);
      
      // 提示用户创建成功
      alert(`模型 "${newName}" 创建成功！`);
    } catch (err: any) {
      setError(err.message || '创建模型失败');
      console.error('Failed to create model from template:', err);
      alert(`创建失败: ${err.message || '未知错误'}`);
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = selectedModel && (
    editingName !== selectedModel.name ||
    editingProvider !== selectedModel.provider ||
    editingModel !== selectedModel.model ||
    editingBaseUrl !== selectedModel.base_url ||
    editingApiKey !== (selectedModel.api_key || '') ||
    editingMaxTokens !== selectedModel.max_tokens ||
    editingTemperature !== selectedModel.temperature ||
    editingApiType !== selectedModel.api_type
  );

  return (
    <div>
      {/* 标题和说明 */}
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">模型设置</h2>
        <p className="text-sm text-slate-400 mt-1">
          创建和管理 LLM 模型配置，包括提供商、模型名称、API 地址和参数设置
        </p>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-md text-sm text-red-300">
          {error}
        </div>
      )}

      {/* 模型设置区域 */}
      <div className="bg-slate-950 border border-slate-700 rounded-lg overflow-hidden">
        <div className="flex" style={{ height: 'calc(100vh - 200px)', minHeight: '600px' }}>
          {/* 左侧侧边栏 */}
          <div className="w-64 border-r border-slate-700 flex flex-col">
            <div className="p-4 border-b border-slate-700">
              <button
                onClick={handleCreateNew}
                className="w-full px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-700 text-sm font-medium transition-colors"
              >
                + 创建新模型
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="p-4 text-sm text-slate-400 text-center">加载中...</div>
              ) : models.length === 0 ? (
                <div className="p-4 text-sm text-slate-400 text-center">
                  暂无模型，点击上方按钮创建
                </div>
              ) : (
                <div className="p-2 space-y-1">
                  {models.map((model) => {
                    const isSelected = selectedModel?.model_id === model.model_id;
                    return (
                      <div
                        key={model.model_id}
                        className={`group relative p-3 rounded-md cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-sky-600/30 border-2 border-sky-500 shadow-lg shadow-sky-500/20'
                            : 'hover:bg-slate-800 border border-transparent'
                        }`}
                        onClick={() => handleSelectModel(model)}
                      >
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center overflow-hidden flex-shrink-0">
                          <div className="text-xl text-slate-500">⚙️</div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-slate-200 truncate">
                            {model.name}
                          </div>
                          <div className="text-xs text-slate-400 truncate">
                            {model.provider} - {model.model}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteModel(model);
                        }}
                        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-600/20 text-red-400 hover:text-red-300 transition-opacity"
                        title="删除模型"
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
                      {isSelected && (
                        <div className="absolute top-2 left-2 w-2 h-2 rounded-full bg-sky-500"></div>
                      )}
                    </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* 右侧详情区域 */}
          <div className="flex-1 overflow-y-auto p-6">
            {isCreating ? (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4">创建新模型</h3>
                  
                  {/* 模型名称 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      配置名称 *
                    </label>
                    <input
                      type="text"
                      value={newModelName}
                      onChange={(e) => setNewModelName(e.target.value)}
                      placeholder="例如：GPT-4o"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* 提供商 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      提供商 *
                    </label>
                    <input
                      type="text"
                      value={newModelProvider}
                      onChange={(e) => setNewModelProvider(e.target.value)}
                      placeholder="例如：OpenAI, DeepSeek, xAI"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* 模型名称 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      模型名称 *
                    </label>
                    <input
                      type="text"
                      value={newModelModel}
                      onChange={(e) => setNewModelModel(e.target.value)}
                      placeholder="例如：gpt-4o, deepseek-chat"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* API 基础地址 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      API 基础地址 *
                    </label>
                    <input
                      type="text"
                      value={newModelBaseUrl}
                      onChange={(e) => setNewModelBaseUrl(e.target.value)}
                      placeholder="例如：https://api.openai.com/v1"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* API Key */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      API Key
                    </label>
                    <input
                      type="password"
                      value={newModelApiKey}
                      onChange={(e) => setNewModelApiKey(e.target.value)}
                      placeholder="输入 API Key（将加密存储）"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* Max Tokens */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      最大 Token 数
                    </label>
                    <input
                      type="number"
                      value={newModelMaxTokens}
                      onChange={(e) => setNewModelMaxTokens(parseInt(e.target.value) || 4096)}
                      min="1"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* Temperature */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      温度参数
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={newModelTemperature}
                      onChange={(e) => setNewModelTemperature(parseFloat(e.target.value) || 1.0)}
                      min="0"
                      max="2"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* API Type */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      API 类型
                    </label>
                    <select
                      value={newModelApiType}
                      onChange={(e) => setNewModelApiType(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    >
                      <option value="openai">OpenAI</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>

                  {/* 保存按钮 */}
                  <div className="flex gap-3 pt-4 border-t border-slate-700">
                    <button
                      onClick={handleCreateModel}
                      disabled={!newModelName.trim() || !newModelProvider.trim() || !newModelModel.trim() || !newModelBaseUrl.trim() || saving}
                      className="px-6 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                    >
                      {saving ? '保存中...' : '保存'}
                    </button>
                    <button
                      onClick={() => {
                        setIsCreating(false);
                        if (models.length > 0) {
                          handleSelectModel(models[0]);
                        }
                      }}
                      className="px-6 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-sm font-medium transition-colors"
                    >
                      取消
                    </button>
                  </div>
                </div>
              </div>
            ) : selectedModel ? (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold mb-4">模型详情</h3>
                  
                  {/* 配置名称 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      配置名称
                    </label>
                    <input
                      type="text"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* 提供商 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      提供商
                    </label>
                    <input
                      type="text"
                      value={editingProvider}
                      onChange={(e) => setEditingProvider(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* 模型名称 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      模型名称
                    </label>
                    <input
                      type="text"
                      value={editingModel}
                      onChange={(e) => setEditingModel(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* API 基础地址 */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      API 基础地址
                    </label>
                    <input
                      type="text"
                      value={editingBaseUrl}
                      onChange={(e) => setEditingBaseUrl(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* API Key */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      API Key
                    </label>
                    <div className="relative">
                      <input
                        type={showApiKey ? "text" : "password"}
                        value={editingApiKey}
                        onChange={(e) => setEditingApiKey(e.target.value)}
                        placeholder={selectedModel.has_api_key && !editingApiKey ? '（已设置，留空则不修改）' : '输入 API Key'}
                        className="w-full px-4 py-2 pr-10 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-slate-400 hover:text-slate-200 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 rounded"
                        aria-label={showApiKey ? "隐藏API Key" : "显示API Key"}
                      >
                        {showApiKey ? (
                          // Eye off icon (hidden)
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                            <line x1="1" y1="1" x2="23" y2="23" />
                          </svg>
                        ) : (
                          // Eye icon (visible)
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                          </svg>
                        )}
                      </button>
                    </div>
                    {selectedModel.has_api_key && !editingApiKey && (
                      <p className="text-xs text-slate-500 mt-1">
                        当前已设置 API Key，留空则不修改
                      </p>
                    )}
                  </div>

                  {/* Max Tokens */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      最大 Token 数
                    </label>
                    <input
                      type="number"
                      value={editingMaxTokens}
                      onChange={(e) => setEditingMaxTokens(parseInt(e.target.value) || 4096)}
                      min="1"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* Temperature */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      温度参数
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={editingTemperature}
                      onChange={(e) => setEditingTemperature(parseFloat(e.target.value) || 1.0)}
                      min="0"
                      max="2"
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  {/* API Type */}
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      API 类型
                    </label>
                    <select
                      value={editingApiType}
                      onChange={(e) => setEditingApiType(e.target.value)}
                      className="w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    >
                      <option value="openai">OpenAI</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>

                  {/* 保存按钮和以当前模板创建按钮 */}
                  <div className="pt-4 border-t border-slate-700">
                    <div className="flex gap-3 items-center">
                      <button
                        onClick={handleSave}
                        disabled={!hasChanges || saving}
                        className="px-6 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                      >
                        {saving ? '保存中...' : '保存更改'}
                      </button>
                      <button
                        onClick={handleCreateFromTemplate}
                        disabled={saving || !editingName.trim() || !editingProvider.trim() || !editingModel.trim() || !editingBaseUrl.trim()}
                        className="px-6 py-2 rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                        title="使用当前草稿内容创建新的模型配置"
                      >
                        {saving ? '创建中...' : '以当前模板创建'}
                      </button>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      将使用当前所有配置创建一个新模型（名称会自动添加"副本"后缀）
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-400">
                <div className="text-center">
                  <div className="text-4xl mb-4">⚙️</div>
                  <p>请从左侧选择一个模型配置，或创建新模型</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}



