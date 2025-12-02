'use client';

import { useState } from 'react';
import { createEmptyArchiveAuto } from '@/lib/api/archive';
import { 
  getAllSessions, 
  saveSessions, 
  setCurrentSessionId, 
  clearSessionMessages,
  syncSessionsFromDatabase,
} from '@/lib/sessions';

export type ViewType = 'chat' | 'archive-save' | 'archive-load' | 'system' | 'user' | 'role' | 'model';

interface SidebarProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
}

export default function Sidebar({ currentView, onViewChange }: SidebarProps) {
  const [creatingNewArchive, setCreatingNewArchive] = useState(false);
  
  const menuItems: { id: ViewType; label: string; icon: string }[] = [
    { id: 'chat', label: '当前会话', icon: '💬' },
    { id: 'archive-save', label: '存档', icon: '💾' },
    { id: 'archive-load', label: '加载', icon: '📂' },
    { id: 'system', label: '系统设置', icon: '⚙️' },
    { id: 'user', label: '用户设置', icon: '👤' },
    { id: 'role', label: '角色设置', icon: '🎭' },
    { id: 'model', label: '模型设置', icon: '🤖' },
  ];

  const handleCreateNewArchive = async () => {
    if (!confirm('确定要开启新存档吗？这将创建一个空白存档并切换到该存档。')) {
      return;
    }

    try {
      setCreatingNewArchive(true);
      // Create empty archive with auto-generated name and switch to it
      await createEmptyArchiveAuto();
      
      // Clear local cache and sync sessions from new database
      try {
        // Clear all session messages from localStorage
        const sessions = getAllSessions();
        sessions.forEach(session => {
          clearSessionMessages(session.id);
        });
        
        // Clear session list
        saveSessions([]);
        setCurrentSessionId(null);
        
        // Sync sessions from new database
        await syncSessionsFromDatabase();
        
        // Trigger archive switch event
        window.dispatchEvent(new CustomEvent('archiveSwitched'));
        
        // Reload page to load new archive data
        setTimeout(() => {
          window.location.reload();
        }, 500);
      } catch (err) {
        console.error('Failed to clear local cache or sync sessions:', err);
      }
    } catch (err: any) {
      alert(err.message || '开启新存档失败');
      console.error('Failed to create new archive:', err);
    } finally {
      setCreatingNewArchive(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-slate-950 border-r border-slate-700">
      {/* 开启新存档按钮 - 在顶部 */}
      <div className="p-2 border-b border-slate-700">
        <button
          onClick={handleCreateNewArchive}
          disabled={creatingNewArchive}
          className="w-full px-3 py-2 rounded-md bg-rose-600 hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors text-white"
          title="创建一个空白存档并切换到该存档"
        >
          {creatingNewArchive ? '创建中...' : '✨ 开启新存档'}
        </button>
      </div>
      
      {/* 菜单项列表 */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={`w-full text-left px-4 py-3 rounded-md text-sm font-medium transition-colors ${
              currentView === item.id
                ? 'bg-sky-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-slate-50'
            }`}
          >
            <span className="mr-2">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

