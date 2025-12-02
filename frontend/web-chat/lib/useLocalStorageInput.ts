'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook for managing input state with localStorage persistence
 * @param key - localStorage key
 * @param defaultValue - default value if key doesn't exist
 * @returns [value, setValue] tuple similar to useState
 */
export function useLocalStorageInput<T>(
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const prevKeyRef = useRef<string>(key);
  
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return defaultValue;
    }
    try {
      const item = window.localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : defaultValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return defaultValue;
    }
  });

  // 当 key 变化时，从新的 key 读取值
  useEffect(() => {
    if (prevKeyRef.current !== key) {
      // Key 变化了，从新的 key 读取值
      if (typeof window !== 'undefined') {
        try {
          const item = window.localStorage.getItem(key);
          if (item !== null) {
            setValue(JSON.parse(item) as T);
          } else {
            setValue(defaultValue);
          }
        } catch (error) {
          console.error(`Error reading localStorage key "${key}":`, error);
          setValue(defaultValue);
        }
      }
      prevKeyRef.current = key;
    }
  }, [key, defaultValue]);

  // 当值变化时，保存到 localStorage
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  }, [key, value]);

  return [value, setValue];
}

