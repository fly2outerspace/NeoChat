'use client';

import { useState, useEffect } from 'react';
import Sidebar, { ViewType } from '@/components/Sidebar';
import ChatArea from '@/components/ChatArea';
import SessionStatus from '@/components/SessionStatus';
import ArchiveManager from '@/components/ArchiveManager';
import ArchiveLoader from '@/components/ArchiveLoader';
import SystemSettings from '@/components/settings/SystemSettings';
import UserSettings from '@/components/settings/UserSettings';
import RoleSettings from '@/components/settings/RoleSettings';
import ModelSettings from '@/components/settings/ModelSettings';
import { getCurrentSessionId, getAllSessions } from '@/lib/sessions';

export default function HomePage() {
  const [currentView, setCurrentView] = useState<ViewType>('chat');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  useEffect(() => {
    // 初始化时，优先从数据库加载会话列表
    const initializeSessions = async () => {
      try {
        const { syncSessionsFromDatabase } = await import('@/lib/sessions');
        const dbSessions = await syncSessionsFromDatabase();
        
        if (dbSessions.length > 0) {
          // 数据库中有会话，使用第一个会话
          const firstSession = dbSessions[0];
          setCurrentSessionId(firstSession.id);
        } else {
          // 数据库中没有会话，检查 localStorage
          const stored = getCurrentSessionId();
          if (stored) {
            setCurrentSessionId(stored);
          }
          // 如果都没有，保持 null，显示创建会话按钮
        }
      } catch (err) {
        console.error('Failed to sync sessions from database:', err);
        // 失败时从 localStorage 加载
        const stored = getCurrentSessionId();
        if (stored) {
          setCurrentSessionId(stored);
        }
      }
    };
    
    initializeSessions();
  }, []);

  const handleViewChange = (view: ViewType) => {
    setCurrentView(view);
  };

  const handleSessionCreated = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const renderContent = () => {
    switch (currentView) {
      case 'chat':
        return <ChatArea sessionId={currentSessionId} onSessionCreated={handleSessionCreated} />;
      case 'archive-save':
        return <ArchiveManager />;
      case 'archive-load':
        return <ArchiveLoader />;
      case 'system':
        return (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-3xl mx-auto">
              <SystemSettings />
            </div>
          </div>
        );
      case 'user':
        return (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-3xl mx-auto">
              <UserSettings />
            </div>
          </div>
        );
      case 'role':
        return (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-3xl mx-auto">
              <RoleSettings />
            </div>
          </div>
        );
      case 'model':
        return (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-3xl mx-auto">
              <ModelSettings />
            </div>
          </div>
        );
      default:
        return <ChatArea sessionId={currentSessionId} />;
    }
  };

  return (
    <div className="h-screen flex bg-slate-900 text-slate-50 overflow-hidden">
      {/* 左侧栏：统一菜单栏 */}
      <div className="w-64 flex-shrink-0">
        <Sidebar currentView={currentView} onViewChange={handleViewChange} />
      </div>

      {/* 中间栏：内容区域 */}
      <div className="flex-1 min-w-0">
        {renderContent()}
      </div>

      {/* 右侧栏：会话状态（仅在对话界面显示） */}
      {currentView === 'chat' && (
        <div className="w-80 flex-shrink-0">
          <SessionStatus sessionId={currentSessionId} />
        </div>
      )}
    </div>
  );
}
