/**
 * Thinking Parser
 *
 * 解析AI回复中的思考标签（<think>和<thinking>）
 */

export interface ThinkingBlock {
  /** 思考内容 */
  content: string;
  /** 开始时间（相对于回复开始） */
  startTime: number;
  /** 结束时间（相对于回复开始） */
  endTime: number;
  /** 思考时长（秒） */
  duration: number;
}

export interface ParsedMessage {
  /** 实际显示的内容（不含思考标签） */
  displayContent: string;
  /** 思考块列表 */
  thinkingBlocks: ThinkingBlock[];
  /** 是否正在思考中 */
  isThinking: boolean;
}

/**
 * 解析消息中的思考标签
 * 支持 <think>...</think> 和 <thinking>...</thinking> 两种标签
 */
export function parseThinkingTags(content: string, currentTime: number): ParsedMessage {
  // 匹配 <think> 或 <thinking> 标签
  const thinkRegex = /<think(?:ing)?>([\s\S]*?)(?:<\/think(?:ing)?>|$)/gi;
  const thinkingBlocks: ThinkingBlock[] = [];
  let displayContent = content;
  let isThinking = false;

  // 提取所有思考块
  let match;
  while ((match = thinkRegex.exec(content)) !== null) {
    const thinkContent = match[1];
    const isComplete = match[0].includes("</");
    
    if (isComplete) {
      // 完整的思考块
      thinkingBlocks.push({
        content: thinkContent,
        startTime: currentTime,
        endTime: currentTime,
        duration: 0, // 将在后续计算
      });
    } else {
      // 正在思考中
      isThinking = true;
    }
  }

  // 移除思考标签，只保留显示内容
  displayContent = content.replace(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/gi, "");
  
  // 如果正在思考中，也要移除未闭合的标签
  displayContent = displayContent.replace(/<think(?:ing)?>([\s\S]*?)$/gi, "");

  return {
    displayContent: displayContent.trim(),
    thinkingBlocks,
    isThinking,
  };
}

/**
 * 实时解析流式内容中的思考标签
 */
export class ThinkingStreamParser {
  private buffer: string = "";
  private thinkingBlocks: ThinkingBlock[] = [];
  private currentThinkingStart: number | null = null;
  private startTime: number;

  constructor() {
    this.startTime = Date.now();
  }

  /**
   * 添加新的内容片段
   */
  add(chunk: string): ParsedMessage {
    this.buffer += chunk;
    return this.parse();
  }

  /**
   * 获取当前缓冲区的内容
   */
  getBuffer(): string {
    return this.buffer;
  }

  /**
   * 解析当前缓冲区
   */
  private parse(): ParsedMessage {
    const currentTime = (Date.now() - this.startTime) / 1000;

    // 检查是否有未闭合的思考标签
    const openThinkMatch = this.buffer.match(/<think(?:ing)?>/i);
    const closeThinkMatch = this.buffer.match(/<\/think(?:ing)?>/i);

    let isThinking = false;

    if (openThinkMatch && !closeThinkMatch) {
      // 正在思考中
      isThinking = true;
      if (this.currentThinkingStart === null) {
        this.currentThinkingStart = currentTime;
      }
    } else if (openThinkMatch && closeThinkMatch) {
      // 思考结束
      if (this.currentThinkingStart !== null) {
        const thinkContent = this.buffer.match(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/i)?.[1] || "";
        this.thinkingBlocks.push({
          content: thinkContent,
          startTime: this.currentThinkingStart,
          endTime: currentTime,
          duration: currentTime - this.currentThinkingStart,
        });
        this.currentThinkingStart = null;
      }
    }

    // 移除思考标签
    const displayContent = this.buffer
      .replace(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/gi, "")
      .replace(/<think(?:ing)?>([\s\S]*?)$/gi, "")
      .trim();

    return {
      displayContent,
      thinkingBlocks: this.thinkingBlocks,
      isThinking,
    };
  }

  /**
   * 完成解析
   */
  finish(): ParsedMessage {
    // 如果还有未闭合的思考标签，强制闭合
    if (this.currentThinkingStart !== null) {
      const currentTime = (Date.now() - this.startTime) / 1000;
      const thinkContent = this.buffer.match(/<think(?:ing)?>([\s\S]*?)$/i)?.[1] || "";
      this.thinkingBlocks.push({
        content: thinkContent,
        startTime: this.currentThinkingStart,
        endTime: currentTime,
        duration: currentTime - this.currentThinkingStart,
      });
      this.currentThinkingStart = null;
    }

    const displayContent = this.buffer
      .replace(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/gi, "")
      .replace(/<think(?:ing)?>([\s\S]*?)$/gi, "")
      .trim();

    return {
      displayContent,
      thinkingBlocks: this.thinkingBlocks,
      isThinking: false,
    };
  }
}
