/**
 * Input mode enum for chat interface
 * Defines all conversation modes available to users
 */
export enum InputMode {
  /** 手机通信 - Phone communication mode */
  PHONE = 'phone',
  /** 面对面说话 - In-person conversation mode */
  IN_PERSON = 'in_person',
  /** 角色内心活动 - Inner voice/thought mode */
  INNER_VOICE = 'inner_voice',
  /** 系统指令 - System command/instruction mode */
  COMMAND = 'command',
  /** 跳过 - Skip mode (no content, no bubble) */
  SKIP = 'skip',
}

/**
 * Input mode category
 * Defines which tab group the input mode belongs to
 */
export enum InputModeCategory {
  /** 基础模式 - Basic input modes (left tabs) */
  BASIC = 'basic',
  /** 扩展模式 - Extended input modes (right tabs) */
  EXTENDED = 'extended',
}

/**
 * Input mode configuration
 * Contains metadata for each input mode
 */
export interface InputModeConfig {
  key: InputMode;
  label: string;
  placeholder: string;
  helper: string;
  available: boolean;
  category: InputModeCategory;
}

/**
 * Input mode options configuration
 * Maps each InputMode enum value to its configuration
 */
export const INPUT_MODE_OPTIONS: readonly InputModeConfig[] = [
  {
    key: InputMode.PHONE,
    label: '手机通信',
    placeholder: '输入短信内容，Enter 发送，Shift+Enter 换行',
    helper: '以手机通信视角与对方沟通',
    available: true,
    category: InputModeCategory.BASIC,
  },
  {
    key: InputMode.IN_PERSON,
    label: '面对面说话',
    placeholder: '输入面对面交流内容，Enter 发送，Shift+Enter 换行',
    helper: '以面对面交流视角与对方沟通',
    available: true,
    category: InputModeCategory.BASIC,
  },
  {
    key: InputMode.INNER_VOICE,
    label: '主角内心活动',
    placeholder: '输入主角内心活动内容（会被AI阅读），Enter 发送，Shift+Enter 换行',
    helper: '以主角内心活动视角记录想法',
    available: true,
    category: InputModeCategory.BASIC,
  },
  {
    key: InputMode.COMMAND,
    label: '系统指令',
    placeholder: '输入系统指令内容，指挥AI行动，Enter 发送，Shift+Enter 换行',
    helper: '发送系统指令消息',
    available: true,
    category: InputModeCategory.EXTENDED,
  },
] as const;

/**
 * Get input mode configuration by key
 */
export function getInputModeConfig(key: InputMode): InputModeConfig | undefined {
  return INPUT_MODE_OPTIONS.find((option) => option.key === key);
}

/**
 * Get default input mode
 */
export function getDefaultInputMode(): InputMode {
  return InputMode.PHONE;
}

/**
 * Get input modes by category
 */
export function getInputModesByCategory(category: InputModeCategory): readonly InputModeConfig[] {
  return INPUT_MODE_OPTIONS.filter((option) => option.category === category);
}

