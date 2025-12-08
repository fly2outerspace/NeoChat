'use client';

import { useEffect, useRef, useState } from 'react';

type LogItem = {
  level: 'info' | 'error';
  message: string;
  ts: number;
};

export default function TerminalView() {
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [filter, setFilter] = useState<'all' | 'info' | 'error'>('all');
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // 拉取历史日志
    window.backendLog?.getHistory?.().then((history) => {
      if (Array.isArray(history)) {
        const mapped = history.map((item) => ({
          ...item,
          ts: item.ts ?? Date.now(),
        })) as LogItem[];
        setLogs(mapped.slice(-500));
      }
    }).catch(() => {});

    const unsubscribe = window.backendLog?.onLog?.((payload) => {
      setLogs((prev) => {
        const next = [...prev, { ...payload, ts: Date.now() }];
        // 保持最多 500 条
        if (next.length > 500) {
          next.shift();
        }
        return next;
      });
    });
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const filtered = filter === 'all' ? logs : logs.filter((l) => l.level === filter);

  return (
    <div className="h-full flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">终端</h2>
          <p className="text-sm text-slate-400">后端日志（最多保留 500 条）</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="all">全部</option>
            <option value="info">信息</option>
            <option value="error">错误</option>
          </select>
          <button
            onClick={() => setLogs([])}
            className="px-3 py-2 rounded-md bg-slate-800 border border-slate-700 text-sm text-slate-200 hover:border-sky-500 transition-colors"
          >
            清空
          </button>
        </div>
      </div>

      <div className="panel-soft flex-1 overflow-y-auto p-4 font-mono text-sm text-slate-200 space-y-1">
        {filtered.length === 0 && (
          <div className="text-slate-400">暂无日志，等待输出...</div>
        )}
        {filtered.map((log, idx) => (
          <div
            key={log.ts + idx}
            className="text-slate-100 whitespace-pre-wrap break-words"
          >
            {log.message}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

