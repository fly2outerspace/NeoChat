'use client';

import { useState, useEffect } from 'react';
import {
  listArchives,
  createArchive,
  deleteArchive,
  overwriteArchive,
  type ArchiveInfo,
  type ArchiveListResponse,
} from '@/lib/api/archive';

export default function ArchiveManager() {
  const [archives, setArchives] = useState<ArchiveInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newArchiveName, setNewArchiveName] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    loadArchives();
  }, []);

  const loadArchives = async () => {
    try {
      setLoading(true);
      setError(null);
      const data: ArchiveListResponse = await listArchives();
      setArchives(data.archives);
    } catch (err: any) {
      setError(err.message || '加载存档列表失败');
      console.error('Failed to load archives:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateArchive = async () => {
    if (!newArchiveName.trim()) {
      alert('请输入存档名称');
      return;
    }

    try {
      setCreating(true);
      setError(null);
      await createArchive(newArchiveName.trim());
      setNewArchiveName('');
      await loadArchives();
    } catch (err: any) {
      setError(err.message || '创建存档失败');
      console.error('Failed to create archive:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteArchive = async (archiveName: string) => {
    if (!confirm(`确定要删除存档 "${archiveName}" 吗？此操作不可恢复。`)) {
      return;
    }

    try {
      setDeleting(archiveName);
      setError(null);
      await deleteArchive(archiveName);
      await loadArchives();
    } catch (err: any) {
      setError(err.message || '删除存档失败');
      console.error('Failed to delete archive:', err);
    } finally {
      setDeleting(null);
    }
  };

  const handleOverwriteArchive = async (archiveName: string) => {
    if (!confirm(`确定要覆盖存档 "${archiveName}" 吗？这将用当前数据库内容替换现有存档。`)) {
      return;
    }

    try {
      setError(null);
      // 使用新的覆盖 API，将当前数据库内容复制到目标存档
      await overwriteArchive(archiveName);
      await loadArchives();
    } catch (err: any) {
      setError(err.message || '覆盖存档失败');
      console.error('Failed to overwrite archive:', err);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-full flex flex-col bg-slate-900 text-slate-50">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold">存档管理</h2>
            <p className="text-sm text-slate-400 mt-1">创建、覆盖和删除存档</p>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-md text-sm text-red-300">
              {error}
            </div>
          )}

          {/* 创建新存档 */}
          <div className="bg-slate-950 border border-slate-700 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-medium mb-4">创建新存档（当前数据库的副本）</h3>
            <p className="text-sm text-slate-400 mb-4">创建的新存档将包含当前数据库的所有内容</p>
            <div className="flex gap-3">
              <input
                type="text"
                value={newArchiveName}
                onChange={(e) => setNewArchiveName(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateArchive();
                  }
                }}
                placeholder="输入存档名称"
                className="flex-1 px-4 py-2 bg-slate-900 border border-slate-700 rounded-md text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              <button
                onClick={handleCreateArchive}
                disabled={!newArchiveName.trim() || creating}
                className="px-6 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
              >
                {creating ? '创建中...' : '创建存档'}
              </button>
            </div>
          </div>

          {/* 存档列表 */}
          <div className="bg-slate-950 border border-slate-700 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-700">
              <h3 className="text-lg font-medium">存档列表</h3>
            </div>
            {loading ? (
              <div className="p-8 text-center text-slate-400">加载中...</div>
            ) : archives.length === 0 ? (
              <div className="p-8 text-center text-slate-400">
                <div className="text-4xl mb-2">📦</div>
                <p>暂无存档</p>
                <p className="text-sm mt-1">创建第一个存档开始使用</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-700">
                {archives.map((archive) => (
                  <div
                    key={archive.name}
                    className="p-4 hover:bg-slate-800/50 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <h4 className="text-base font-medium text-slate-200">
                            {archive.name}
                          </h4>
                        </div>
                        <div className="text-sm text-slate-400 space-y-1">
                          <p>大小: {formatFileSize(archive.size)}</p>
                          <p>创建时间: {formatDate(archive.created_at)}</p>
                          <p>修改时间: {formatDate(archive.modified_at)}</p>
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <button
                          onClick={() => handleOverwriteArchive(archive.name)}
                          disabled={deleting === archive.name}
                          className="px-3 py-1.5 text-xs rounded-md bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          title="覆盖存档"
                        >
                          覆盖
                        </button>
                        <button
                          onClick={() => handleDeleteArchive(archive.name)}
                          disabled={deleting === archive.name}
                          className="px-3 py-1.5 text-xs rounded-md bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          title="删除存档"
                        >
                          {deleting === archive.name ? '删除中...' : '删除'}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

