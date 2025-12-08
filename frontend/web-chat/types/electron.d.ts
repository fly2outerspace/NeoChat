export {};

declare global {
  interface Window {
    backendLog?: {
      onLog: (callback: (payload: { level: 'info' | 'error'; message: string }) => void) => () => void;
      getHistory: () => Promise<Array<{ level: 'info' | 'error'; message: string; ts?: number }>>;
    };
  }
}





