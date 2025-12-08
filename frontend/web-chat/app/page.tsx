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
import MemoryView from '@/components/MemoryView';
import RelationView from '@/components/RelationView';
import TerminalView from '@/components/TerminalView';
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

  // 监听外部切换视图事件（用于从其他组件触发视图切换）
  useEffect(() => {
    const handleSwitchToView = (event: CustomEvent) => {
      const targetView = event.detail as ViewType;
      if (targetView) {
        setCurrentView(targetView);
      }
    };

    window.addEventListener('switchToView', handleSwitchToView as EventListener);
    return () => {
      window.removeEventListener('switchToView', handleSwitchToView as EventListener);
    };
  }, []);

  const handleSessionCreated = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  // 监听页面切换，当切换到特定页面时触发刷新事件
  useEffect(() => {
    if (currentView === 'memory') {
      // 延迟一小段时间，确保组件已经渲染
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('viewSwitched', { detail: 'memory' }));
      }, 50);
    } else if (currentView === 'relation') {
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('viewSwitched', { detail: 'relation' }));
      }, 50);
    } else if (currentView === 'archive-save') {
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('viewSwitched', { detail: 'archive-save' }));
      }, 50);
    } else if (currentView === 'archive-load') {
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('viewSwitched', { detail: 'archive-load' }));
      }, 50);
    }
    // 终端视图无需额外事件
  }, [currentView]);

  return (
    <div className="h-screen flex bg-slate-900 text-slate-50 overflow-hidden">
      {/* 左侧栏：统一菜单栏 */}
      <div className="w-64 flex-shrink-0">
        <Sidebar currentView={currentView} onViewChange={handleViewChange} />
      </div>

      {/* 中间栏：内容区域 - 所有组件始终挂载，通过显示/隐藏控制 */}
      <div className="flex-1 min-w-0 relative">
        {/* ChatArea - 始终挂载，切换页面时不会被卸载 */}
        <div className={currentView === 'chat' ? 'h-full' : 'hidden'}>
          <ChatArea sessionId={currentSessionId} onSessionCreated={handleSessionCreated} />
        </div>

        {/* Archive Manager - 始终挂载 */}
        <div className={currentView === 'archive-save' ? 'h-full' : 'hidden'}>
          <ArchiveManager />
        </div>

        {/* Archive Loader - 始终挂载 */}
        <div className={currentView === 'archive-load' ? 'h-full' : 'hidden'}>
          <ArchiveLoader />
        </div>

        {/* System Settings - 始终挂载 */}
        <div className={currentView === 'system' ? 'h-full overflow-y-auto p-8' : 'hidden'}>
          <div className="max-w-3xl mx-auto">
            <SystemSettings />
          </div>
        </div>

        {/* User Settings - 始终挂载 */}
        <div className={currentView === 'user' ? 'h-full overflow-y-auto p-8' : 'hidden'}>
          <div className="max-w-3xl mx-auto">
            <UserSettings />
          </div>
        </div>

        {/* Role Settings - 始终挂载 */}
        <div className={currentView === 'role' ? 'h-full overflow-y-auto p-8' : 'hidden'}>
          <div className="max-w-3xl mx-auto">
            <RoleSettings />
          </div>
        </div>

        {/* Model Settings - 始终挂载 */}
        <div className={currentView === 'model' ? 'h-full overflow-y-auto p-8' : 'hidden'}>
          <div className="max-w-3xl mx-auto">
            <ModelSettings />
          </div>
        </div>

        {/* Memory View - 始终挂载 */}
        <div className={currentView === 'memory' ? 'h-full' : 'hidden'}>
          <MemoryView />
        </div>

        {/* Relation View - 始终挂载 */}
        <div className={currentView === 'relation' ? 'h-full' : 'hidden'}>
          <RelationView />
        </div>

        {/* Terminal View - 日志输出 */}
        <div className={currentView === 'terminal' ? 'h-full overflow-y-auto p-4' : 'hidden'}>
          <div className="max-w-5xl mx-auto h-full">
            <TerminalView />
          </div>
        </div>
      </div>

      {/* 右侧栏：会话状态 - 始终挂载，仅在对话界面显示 */}
      <div className={`w-80 flex-shrink-0 ${currentView === 'chat' ? '' : 'hidden'}`}>
        <SessionStatus sessionId={currentSessionId} />
      </div>
    </div>
  );
}
