"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchSessionTime,
  nudgeSessionTime,
  setSessionTimeSpeed,
  seekSessionTime,
  updateSessionTime,
  type SessionTimeResponse,
} from '@/lib/api/sessionTime';

interface SessionStatusProps {
  sessionId: string | null;
}

/**
 * 右侧状态栏组件
 */
export default function SessionStatus({ sessionId }: SessionStatusProps) {
  const [clockLoading, setClockLoading] = useState(false);
  const [clockActionLoading, setClockActionLoading] = useState(false);
  const [clockError, setClockError] = useState<string | null>(null);
  const [clockInfo, setClockInfo] = useState<SessionTimeResponse | null>(null);
  const [displayVirtual, setDisplayVirtual] = useState<string>('--');
  const [displayReal, setDisplayReal] = useState<string>('--');
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [timelineExpanded, setTimelineExpanded] = useState(false);
  const [timelineParts, setTimelineParts] = useState({
    year: '',
    month: '',
    day: '',
    hour: '',
    minute: '',
    second: '',
  });


  const parseServerTime = (value: string): Date => {
    // Server returns "YYYY-MM-DD HH:MM:SS"
    return new Date(value.replace(' ', 'T'));
  };

  const formatDateTime = (date: Date): string => {
    if (Number.isNaN(date.getTime())) return '--';
    return date.toLocaleString('zh-CN', {
      hour12: false,
    });
  };

  const formatDateShort = (date: Date): string => {
    if (Number.isNaN(date.getTime())) return '--';
    return date.toLocaleTimeString('zh-CN', { hour12: false });
  };

  const formatServerPayloadTime = (date: Date): string => {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  };

  const computeVirtualDate = (info: SessionTimeResponse, realNow: Date): Date => {
    let virtual = parseServerTime(info.base_virtual).getTime();
    let realDelta = (realNow.getTime() - parseServerTime(info.base_real).getTime()) / 1000;

    info.actions.forEach((action) => {
      if (action.type === 'scale') {
        realDelta *= action.value;
      } else if (action.type === 'offset') {
        virtual += action.value * 1000;
      } else if (action.type === 'freeze') {
        realDelta = 0;
      }
    });

    virtual += realDelta * 1000;
    return new Date(virtual);
  };

  const refreshDisplay = useCallback((info: SessionTimeResponse) => {
    const now = new Date();
    setDisplayReal(formatDateShort(now));
    setDisplayVirtual(formatDateTime(computeVirtualDate(info, now)));
  }, []);

  const loadClock = useCallback(async () => {
    if (!sessionId) {
      setClockInfo(null);
      setDisplayVirtual('--');
      setDisplayReal('--');
      setClockError(null);
      return;
    }
    try {
      setClockLoading(true);
      const data = await fetchSessionTime(sessionId);
      setClockInfo(data);
      refreshDisplay(data);
      setClockError(null);
      setLastSync(formatDateShort(new Date()));
    } catch (err: any) {
      console.error('Failed to load session time:', err);
      setClockError(err?.message ?? '无法获取虚拟时间');
    } finally {
      setClockLoading(false);
    }
  }, [sessionId, refreshDisplay]);

  useEffect(() => {
    if (!sessionId) return;
    loadClock();
    const timer = setInterval(loadClock, 60_000);
    return () => clearInterval(timer);
  }, [sessionId, loadClock]);

  useEffect(() => {
    if (!clockInfo) return;
    const interval = setInterval(() => {
      refreshDisplay(clockInfo);
    }, 1000);
    return () => clearInterval(interval);
  }, [clockInfo, refreshDisplay]);
  const handleClockAction = async (action: () => Promise<SessionTimeResponse>) => {
    if (!sessionId) return;
    try {
      setClockActionLoading(true);
      const data = await action();
      setClockInfo(data);
      refreshDisplay(data);
      setClockError(null);
      setLastSync(formatDateShort(new Date()));
    } catch (err: any) {
      console.error('Session time action failed:', err);
      setClockError(err?.message ?? '操作失败');
    } finally {
      setClockActionLoading(false);
    }
  };

  const handleNudge = (seconds: number) =>
    handleClockAction(() => nudgeSessionTime(sessionId!, seconds));

  const handleSpeed = (speed: number) =>
    handleClockAction(() => setSessionTimeSpeed(sessionId!, speed));

  const handleSeekNow = () => {
    const now = new Date();
    return handleClockAction(() => seekSessionTime(sessionId!, formatServerPayloadTime(now)));
  };

  const handleResetReal = () => {
    const now = new Date();
    return handleClockAction(() =>
      updateSessionTime(sessionId!, {
        base_virtual: formatServerPayloadTime(now),
        reset_actions: true,
        actions: [],
      })
    );
  };

  useEffect(() => {
    if (clockInfo) {
      const [datePart, timePart] = clockInfo.base_virtual.split(' ');
      const [year, month, day] = (datePart || '').split('-');
      const [hour, minute, second] = (timePart || '').split(':');
      setTimelineParts({
        year: year || '',
        month: month || '',
        day: day || '',
        hour: hour || '',
        minute: minute || '',
        second: second || '',
      });
    }
  }, [clockInfo]);

  const handleTimelinePartChange = (field: keyof typeof timelineParts, value: string) => {
    setTimelineParts((prev) => ({ ...prev, [field]: value }));
  };

  const handleTimelineSubmit = () => {
    if (!sessionId) return;
    const { year, month, day, hour, minute, second } = timelineParts;
    if (!year || !month || !day || !hour || !minute || !second) {
      setClockError('请完整填写虚拟时间 (YYYY-MM-DD HH:MM:SS)');
      return;
    }
    const pad = (val: string) => val.padStart(2, '0');
    const payload = `${year}-${pad(month)}-${pad(day)} ${pad(hour)}:${pad(minute)}:${pad(second)}`;
    handleClockAction(() =>
      updateSessionTime(sessionId, {
        base_virtual: payload,
        reset_actions: false,
        rebase: false,
      })
    );
  };



  return (
    <div className="h-full flex flex-col bg-gradient-to-b from-[#0b1220] to-[#0a1020] border-l border-slate-800/80 p-4 shadow-inner">
      <div className="text-sm font-semibold text-slate-200 mb-4">会话状态</div>
      
      {sessionId ? (
        <div className="space-y-4">
          <div>
            <div className="text-xs text-slate-500 mb-1">会话 ID</div>
            <div className="text-xs text-slate-300 font-mono break-all">
              {sessionId}
            </div>
          </div>
          
          {/* 虚拟时钟 */}
          <div className="border border-slate-800/80 rounded-xl p-4 bg-slate-900/70 shadow-lg shadow-slate-900/40 backdrop-blur">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-slate-500">虚拟时间</div>
              <button
                onClick={loadClock}
                disabled={clockLoading || clockActionLoading}
                className="text-xs px-2 py-1 rounded-md bg-slate-800 border border-slate-700 text-slate-200 hover:border-sky-500 hover:text-sky-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {clockLoading ? '同步中...' : '同步'}
              </button>
            </div>
            <div className="text-lg font-mono text-sky-300">{displayVirtual}</div>
            <div className="text-[11px] text-slate-500">
              真实时间：{displayReal}
              {lastSync && <span className="ml-2">上次同步 {lastSync}</span>}
            </div>
            {clockError && (
              <div className="mt-1 text-xs text-red-400">
                {clockError}
              </div>
            )}
            {clockInfo && (
              <>
                <div className="mt-2 text-[11px] text-slate-500">
                  当前倍率：
                </div>
                <div className="mt-1 text-sm text-slate-200">
                  {(() => {
                    const speedAction =
                      clockInfo.actions
                        .slice()
                        .reverse()
                        .find((action) => action.type === 'scale');
                    if (!speedAction) {
                      return '1x';
                    }
                    if (speedAction.value === 0) {
                      return '暂停';
                    }
                    return `${speedAction.value}x`;
                  })()}
                </div>

                <div className="mt-3">
                  <button
                    onClick={() => setTimelineExpanded((v) => !v)}
                    className="text-xs text-slate-400 hover:text-sky-300"
                  >
                    {timelineExpanded ? '收起设置' : '展开设置'}
                  </button>
                  {timelineExpanded && (
                    <div className="mt-3 space-y-4 text-slate-200 border border-slate-800 rounded-xl p-4 text-[13px] bg-slate-900/80 shadow-inner shadow-slate-900/50">
                      <div>
                        <div className="text-[11px] text-slate-500 mb-1">偏移</div>
                        {/* 分钟级别 */}
                        <div className="grid grid-cols-4 gap-2 mb-2">
                          {[-3600, -300, 300, 3600].map((delta) => (
                            <button
                              key={delta}
                              onClick={() => handleNudge(delta)}
                              disabled={clockActionLoading}
                              className="text-xs px-2 py-1 rounded-md border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-sky-500 hover:text-sky-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                              {delta > 0 ? `+${delta / 60}m` : `${delta / 60}m`}
                            </button>
                          ))}
                        </div>
                        {/* 小时级别 */}
                        <div className="grid grid-cols-4 gap-2">
                          {[-12 * 3600, -4 * 3600, 4 * 3600, 12 * 3600].map((delta) => (
                            <button
                              key={delta}
                              onClick={() => handleNudge(delta)}
                              disabled={clockActionLoading}
                              className="text-xs px-2 py-1 rounded-md border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-sky-500 hover:text-sky-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                              {delta > 0 ? `+${delta / 3600}h` : `${delta / 3600}h`}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div>
                        <div className="text-[11px] text-slate-500 mb-1">速度</div>
                        <div className="grid grid-cols-4 gap-2">
                          {[0, 0.5, 1, 2, 4, 8].map((speed) => (
                            <button
                              key={speed}
                              onClick={() => handleSpeed(speed)}
                              disabled={clockActionLoading}
                              className="text-xs px-2 py-1 rounded-md border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-sky-500 hover:text-sky-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                              {speed === 0 ? '暂停' : `${speed}x`}
                            </button>
                          ))}
                        </div>
                      </div>

                      <button
                        onClick={handleResetReal}
                        disabled={clockActionLoading}
                        className="w-full text-xs px-2 py-1 rounded-md border border-rose-500 text-rose-200 bg-rose-900/40 hover:bg-rose-800/40 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        恢复真实时间
                      </button>

                      <div>
                        <div className="text-xs text-slate-400 mb-2 font-semibold">设置虚拟时间线</div>
                        <div className="grid grid-cols-3 gap-2">
                          {(['year', 'month', 'day'] as const).map((field, idx) => (
                            <div key={field} className="flex flex-col">
                              <label className="text-[12px] text-slate-500 mb-1">
                                {['年', '月', '日'][idx]}
                              </label>
                              <input
                                value={timelineParts[field]}
                                onChange={(e) => handleTimelinePartChange(field, e.target.value)}
                                placeholder={field === 'year' ? 'YYYY' : 'MM'}
                                className="px-2 py-1 bg-slate-900/90 border border-slate-700 rounded-md text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                              />
                            </div>
                          ))}
                        </div>
                        <div className="grid grid-cols-3 gap-2 mt-2">
                          {(['hour', 'minute', 'second'] as const).map((field, idx) => (
                            <div key={field} className="flex flex-col">
                              <label className="text-[12px] text-slate-500 mb-1">
                                {['时', '分', '秒'][idx]}
                              </label>
                              <input
                                value={timelineParts[field]}
                                onChange={(e) => handleTimelinePartChange(field, e.target.value)}
                                placeholder="00"
                                className="px-2 py-1 bg-slate-900/90 border border-slate-700 rounded-md text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                              />
                            </div>
                          ))}
                        </div>
                        <button
                          onClick={handleTimelineSubmit}
                          disabled={clockActionLoading}
                          className="w-full mt-2 px-2 py-2 rounded-md bg-sky-600 text-white text-xs hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                        >
                          应用时间线
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-500">
          未选择会话
        </div>
      )}
      
      {/* Tips 提示 */}
      <div className="mt-auto pt-4 border-t border-slate-800/80">
        <div className="text-xs text-slate-500 leading-relaxed">
          <span className="text-slate-300 font-medium">tips：</span>
          可以使用<code className="px-1 py-0.5 bg-slate-800 rounded text-slate-200">跳过</code>和<code className="px-1 py-0.5 bg-slate-800 rounded text-slate-200">目标选择</code>来进行灵活地多人/替身对话
        </div>
      </div>
    </div>
  );
}

