'use client';

import React, { useEffect, useState } from 'react';
import { App, Button, Layout, Menu, Space, Typography } from 'antd';
import {
  MessageOutlined,
  SaveOutlined,
  FolderOpenOutlined,
  SettingOutlined,
  UserOutlined,
  IdcardOutlined,
  RobotOutlined,
  DatabaseOutlined,
  ClusterOutlined,
  ThunderboltOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { createEmptyArchiveAuto } from '@/lib/api/archive';
import { 
  getAllSessions, 
  saveSessions, 
  setCurrentSessionId, 
  clearSessionMessages,
  syncSessionsFromDatabase,
} from '@/lib/sessions';

export type ViewType = 'chat' | 'archive-save' | 'archive-load' | 'system' | 'user' | 'role' | 'model' | 'memory' | 'relation' | 'terminal';

interface SidebarProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
}

export default function Sidebar({ currentView, onViewChange }: SidebarProps) {
  // Avoid SSR/client hydration mismatch from Antd Menu auto-generated ids
  const [hydrated, setHydrated] = useState(false);
  const [creatingNewArchive, setCreatingNewArchive] = useState(false);
  const { modal } = App.useApp();

  useEffect(() => {
    setHydrated(true);
  }, []);
  
  const menuItems: { id: ViewType; label: string; icon: React.ReactNode }[] = [
    { id: 'chat', label: '当前会话', icon: <MessageOutlined /> },
    { id: 'archive-save', label: '存档', icon: <SaveOutlined /> },
    { id: 'archive-load', label: '加载', icon: <FolderOpenOutlined /> },
    { id: 'system', label: '系统设置', icon: <SettingOutlined /> },
    { id: 'user', label: '用户设置', icon: <UserOutlined /> },
    { id: 'role', label: '角色设置', icon: <IdcardOutlined /> },
    { id: 'model', label: '模型设置', icon: <RobotOutlined /> },
    { id: 'memory', label: '记忆', icon: <DatabaseOutlined /> },
    { id: 'relation', label: '关系', icon: <ClusterOutlined /> },
    { id: 'terminal', label: '终端', icon: <ThunderboltOutlined /> },
  ];

  const handleCreateNewArchive = async () => {
    const confirmed = await new Promise<boolean>((resolve) => {
      let settled = false;
      modal.confirm({
        title: '开启新存档？',
        icon: <ThunderboltOutlined />,
        content: '这将创建一个空白存档并切换到该存档。',
        okText: '确定',
        cancelText: '取消',
        centered: true,
        onOk: () => {
          settled = true;
          resolve(true);
        },
        onCancel: () => {
          settled = true;
          resolve(false);
        },
        afterClose: () => {
          if (!settled) resolve(false);
        },
      });
    });

    if (!confirmed) return;

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

  if (!hydrated) {
    return <div style={{ width: 256, height: '100vh' }} />;
  }

  return (
    <Layout.Sider
      width={256}
      theme="dark"
      style={{
        background: 'linear-gradient(180deg, #0b1220 0%, #0a1020 100%)',
        borderRight: '1px solid #1f2937',
        height: '100vh',
      }}
    >
      <div className="h-full flex flex-col">
        <div className="p-3 border-b border-slate-800">
          <Space direction="vertical" size={12} className="w-full">
            <Typography.Title level={5} style={{ color: '#e5e7eb', margin: 0 }}>
              NeoChat
            </Typography.Title>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              block
              size="middle"
              loading={creatingNewArchive}
          onClick={handleCreateNewArchive}
              className="!bg-[#ff0066] !border-[#ff0066] hover:!bg-[#ff3388] hover:!border-[#ff3388] active:!bg-[#cc0055] active:!border-[#cc0055]"
        >
              开启新存档
            </Button>
          </Space>
      </div>
      
        <div className="flex-1 overflow-y-auto">
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[currentView]}
            onClick={({ key }) => onViewChange(key as ViewType)}
            items={menuItems.map((item) => ({
              key: item.id,
              label: item.label,
              icon: item.icon,
            }))}
            style={{ borderRight: 'none', background: 'transparent', padding: '8px' }}
          />
      </div>
    </div>
    </Layout.Sider>
  );
}

