'use client';

import { useState, useEffect, useRef } from 'react';
import { getUserAvatar, saveUserAvatar, clearUserAvatar } from '@/lib/config';

export default function UserSettings() {
  const [avatar, setAvatar] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const stored = getUserAvatar();
    setAvatar(stored);
    setPreview(stored);
  }, []);

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
      setPreview(result);
    };
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    if (preview) {
      saveUserAvatar(preview);
      setAvatar(preview);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  const handleClear = () => {
    if (confirm('确定要清除用户头像吗？')) {
      clearUserAvatar();
      setAvatar(null);
      setPreview(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">用户设置</h2>
        <p className="text-sm text-slate-400 mt-1">上传和管理你的用户头像</p>
      </div>

      <div className="bg-slate-950 border border-slate-700 rounded-lg p-6">
        <div className="flex flex-col items-center space-y-6">
          {/* 头像预览 */}
          <div className="flex flex-col items-center space-y-4">
            <div className="relative">
              <div className="w-32 h-32 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center overflow-hidden">
                {preview ? (
                  <img
                    src={preview}
                    alt="用户头像预览"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-4xl text-slate-500">👤</div>
                )}
              </div>
            </div>
            <p className="text-sm text-slate-400">
              {preview ? '头像预览' : '暂无头像'}
            </p>
          </div>

          {/* 上传按钮 */}
          <div className="w-full space-y-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={handleUploadClick}
              className="w-full px-4 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-sm font-medium transition-colors"
            >
              选择图片
            </button>
            <p className="text-xs text-slate-500 text-center">
              支持 JPG、PNG、WebP 格式，最大 2MB
            </p>
          </div>

          {/* 操作按钮 */}
          <div className="w-full flex gap-3 pt-4 border-t border-slate-700">
            <button
              onClick={handleSave}
              disabled={!preview || preview === avatar}
              className="flex-1 px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
            >
              {saved ? '✓ 已保存' : '保存头像'}
            </button>
            {avatar && (
              <button
                onClick={handleClear}
                className="px-4 py-2 rounded-md bg-red-600 hover:bg-red-700 text-sm font-medium transition-colors"
              >
                清除
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

