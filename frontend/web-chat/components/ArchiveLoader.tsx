'use client';

import { useState, useEffect } from 'react';
import {
  listArchives,
  loadArchive,
  type ArchiveInfo,
  type ArchiveListResponse,
  type ArchiveResponse,
} from '@/lib/api/archive';
import { 
  getAllSessions, 
  saveSessions, 
  setCurrentSessionId, 
  clearSessionMessages,
  syncSessionsFromDatabase,
} from '@/lib/sessions';

export default function ArchiveLoader() {
  const [archives, setArchives] = useState<ArchiveInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingArchive, setLoadingArchive] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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

  const handleLoadArchive = async (archiveName: string) => {
    if (!confirm(`确定要加载存档 "${archiveName}" 吗？这将覆盖当前工作数据库并刷新索引。`)) {
      return;
    }

    try {
      setLoadingArchive(archiveName);
      setError(null);
      setSuccess(null);
      const response: ArchiveResponse = await loadArchive(archiveName);
      
      // 检查是否有新导入的角色
      if (response.imported_characters && response.imported_characters.length > 0) {
        const characterIds = response.imported_characters.join(', ');
        alert(`存档加载成功！\n\n以下角色已从存档导入到全局角色库：\n${characterIds}`);
      }
      
      // 清空本地缓存（localStorage），但保留数据库中的前端消息
      // 因为每个存档都有自己的数据库文件，切换存档后会自动加载新数据库中的消息
      try {
        // 清空所有会话的 localStorage 消息
        const sessions = getAllSessions();
        sessions.forEach(session => {
          clearSessionMessages(session.id);
        });
        
        // 清空会话列表
        saveSessions([]);
        setCurrentSessionId(null);
        
        // 从数据库同步会话列表到 localStorage
        const dbSessions = await syncSessionsFromDatabase();
        
        // 如果数据库中有会话，自动选择第一个
        if (dbSessions.length > 0) {
          setCurrentSessionId(dbSessions[0].id);
        }
        
        // 注意：不清空数据库中的前端消息，因为：
        // 1. 每个存档都有自己的数据库文件
        // 2. 切换存档后，后端已经切换到新的数据库文件
        // 3. 新数据库中的前端消息会在页面刷新后自动加载
      } catch (err) {
        console.error('Failed to clear local cache or sync sessions:', err);
      }
      
      setSuccess(`已成功加载存档 "${archiveName}"`);
      await loadArchives();
      
      // 触发存档加载事件（通知其他组件刷新数据）
      window.dispatchEvent(new CustomEvent('archiveSwitched'));
      
      // 刷新页面以加载新存档的数据
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (err: any) {
      setError(err.message || '加载存档失败');
      console.error('Failed to load archive:', err);
    } finally {
      setLoadingArchive(null);
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
            <h2 className="text-2xl font-semibold">加载存档</h2>
            <p className="text-sm text-slate-400 mt-1">选择存档进行加载，或切换回活跃数据库</p>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-md text-sm text-red-300">
              {error}
            </div>
          )}

          {/* 成功提示 */}
          {success && (
            <div className="mb-4 p-3 bg-green-900/50 border border-green-700 rounded-md text-sm text-green-300">
              {success}
            </div>
          )}

          {/* 存档列表 */}
          <div className="bg-slate-950 border border-slate-700 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-700">
              <h3 className="text-lg font-medium">可用存档</h3>
            </div>
            {loading ? (
              <div className="p-8 text-center text-slate-400">加载中...</div>
            ) : archives.length === 0 ? (
              <div className="p-8 text-center text-slate-400">
                <div className="text-4xl mb-2">📦</div>
                <p>暂无存档</p>
                <p className="text-sm mt-1">前往"存档"页面创建存档</p>
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
                      <div className="ml-4">
                        <button
                          onClick={() => handleLoadArchive(archive.name)}
                          disabled={loadingArchive === archive.name}
                          className="px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                        >
                          {loadingArchive === archive.name ? '加载中...' : '加载存档'}
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

