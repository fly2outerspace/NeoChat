'use client';

import { useEffect, useState } from 'react';
import { Session, getAllSessions, createSession, deleteSession, setCurrentSessionId, getCurrentSessionId } from '@/lib/sessions';

interface SessionListProps {
  currentSessionId: string | null;
  onSessionChange: (sessionId: string) => void;
}

export default function SessionList({ currentSessionId, onSessionChange }: SessionListProps) {
  const [sessions, setSessions] = useState<Session[]>([]);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = () => {
    const all = getAllSessions();
    setSessions(all);

    // 如果没有会话，自动创建一个
    if (all.length === 0) {
      const newSession = createSession();
      setSessions([newSession]);
      setCurrentSessionId(newSession.id);
      onSessionChange(newSession.id);
    } else {
      // 如果有会话但没有当前会话，选择第一个
      const current = getCurrentSessionId();
      if (!current || !all.find((s) => s.id === current)) {
        const first = all[0];
        setCurrentSessionId(first.id);
        onSessionChange(first.id);
      } else {
        onSessionChange(current);
      }
    }
  };

  const handleCreateSession = () => {
    const newSession = createSession();
    setSessions((prev) => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    onSessionChange(newSession.id);
  };

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (confirm('确定要删除这个会话吗？')) {
      deleteSession(sessionId);
      loadSessions();
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    onSessionChange(sessionId);
  };

  return (
    <div className="h-full flex flex-col bg-slate-950 border-r border-slate-700">
      {/* 头部：新建会话按钮 */}
      <div className="p-3 border-b border-slate-700">
        <button
          onClick={handleCreateSession}
          className="w-full px-3 py-2 rounded-md bg-sky-600 hover:bg-sky-700 text-sm font-medium transition-colors"
        >
          + 新建会话
        </button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-sm text-slate-500 text-center">
            还没有会话
            <br />
            点击上方按钮创建
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelectSession(session.id)}
                className={`group relative px-3 py-2 rounded-md cursor-pointer transition-colors ${
                  currentSessionId === session.id
                    ? 'bg-sky-600/20 border border-sky-500/50'
                    : 'hover:bg-slate-800'
                }`}
              >
                <div className="text-sm font-medium text-slate-200 truncate">
                  {session.title}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {new Date(session.updatedAt).toLocaleString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
                {/* 删除按钮（hover 时显示） */}
                <button
                  onClick={(e) => handleDeleteSession(e, session.id)}
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-600/20 text-red-400 hover:text-red-300 transition-opacity"
                  title="删除会话"
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
  );
}

