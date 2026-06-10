import { useEffect, useRef, useState } from "react";

export interface UseLocalStorageOptions<T> {
  /** Сериализация значения в строку (по умолчанию JSON.stringify). */
  serialize?: (value: T) => string;
  /**
   * Разбор сырой строки из localStorage (по умолчанию JSON.parse).
   * Вернуть undefined или бросить исключение, чтобы взять значение по умолчанию.
   */
  deserialize?: (raw: string) => T | undefined;
}

function defaultSerialize<T>(value: T): string {
  return JSON.stringify(value);
}

function defaultDeserialize<T>(raw: string): T {
  return JSON.parse(raw) as T;
}

/**
 * Типизированный useState, синхронизированный с localStorage:
 * ленивая инициализация из хранилища и запись при каждом изменении.
 */
export function useLocalStorage<T>(
  key: string,
  defaultValue: T | (() => T),
  options?: UseLocalStorageOptions<T>
) {
  const serialize = options?.serialize ?? defaultSerialize<T>;
  const deserialize = options?.deserialize ?? defaultDeserialize<T>;

  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw !== null) {
        const parsed = deserialize(raw);
        if (parsed !== undefined) return parsed;
      }
    } catch {
      // битое значение или недоступный localStorage — берём дефолт
    }
    return defaultValue instanceof Function ? defaultValue() : defaultValue;
  });

  const serializeRef = useRef(serialize);
  useEffect(() => {
    serializeRef.current = serialize;
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, serializeRef.current(value));
    } catch {
      // localStorage недоступен (private mode и т.п.) — молча пропускаем
    }
  }, [key, value]);

  return [value, setValue] as const;
}
