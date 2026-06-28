/**
 * Tag Input Component
 *
 * 通用标签输入组件，支持添加、删除标签，并使用HSL生成随机浅色背景。
 */

import { useState, useCallback } from "react";
import {
  Flex,
  Text,
  TextField,
  Badge,
} from "@radix-ui/themes";
import { X } from "lucide-react";

/**
 * 基于标签文本生成HSL颜色
 * 使用文本的hash值生成固定的颜色，确保相同标签总是相同颜色
 */
function generateTagColor(tag: string): { background: string; textColor: string } {
  // 简单的hash函数
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    const char = tag.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // 转换为32位整数
  }

  // 使用hash值生成HSL颜色
  // H (色相): 0-360，使用hash映射到不同色相
  const hue = Math.abs(hash) % 360;
  
  // S (饱和度): 30-50%，生成柔和的颜色
  const saturation = 30 + (Math.abs(hash) % 21); // 30-50%
  
  // L (亮度): 85-95%，生成浅色背景
  const lightness = 85 + (Math.abs(hash) % 11); // 85-95%

  const background = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  
  // 根据亮度计算文字颜色，确保有足够对比度
  // 对于浅色背景（lightness > 80%），使用深色文字
  const textColor = lightness > 80 ? "hsl(0, 0%, 20%)" : "hsl(0, 0%, 80%)";

  return { background, textColor };
}

interface TagInputProps {
  /** 当前标签列表 */
  tags: string[];
  /** 标签变化回调 */
  onChange: (tags: string[]) => void;
  /** 是否禁用 */
  disabled?: boolean;
  /** 标签文本 */
  label?: string;
  /** 输入框占位符 */
  placeholder?: string;
  /** 已存在的标签列表（用于快速添加） */
  existingTags?: string[];
  /** 已存在标签的提示文本 */
  existingTagsLabel?: string;
}

export function TagInput({
  tags = [],
  onChange,
  disabled = false,
  label,
  placeholder,
  existingTags,
  existingTagsLabel,
}: TagInputProps) {
  const [tagInput, setTagInput] = useState("");

  /** 添加标签 */
  const handleAddTag = useCallback(() => {
    const trimmed = tagInput.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
      setTagInput("");
    }
  }, [tagInput, tags, onChange]);

  /** 删除标签 */
  const handleRemoveTag = useCallback(
    (tag: string) => {
      onChange(tags.filter((t) => t !== tag));
    },
    [tags, onChange]
  );

  /** 从已存在标签快速添加 */
  const handleQuickAddTag = useCallback(
    (tag: string) => {
      if (!tags.includes(tag)) {
        onChange([...tags, tag]);
      }
    },
    [tags, onChange]
  );

  /** 处理键盘事件 */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddTag();
      } else if (e.key === "Backspace" && !tagInput && tags.length > 0) {
        // 删除最后一个标签
        onChange(tags.slice(0, -1));
      }
    },
    [handleAddTag, tagInput, tags, onChange]
  );

  return (
    <Flex direction="column" gap="2">
      {label && (
        <Text size="2" weight="medium">
          {label}
        </Text>
      )}
      <TextField.Root
        value={tagInput}
        onChange={(e) => setTagInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleAddTag}
        placeholder={placeholder}
        disabled={disabled}
      />
      {tags.length > 0 && (
        <Flex gap="2" wrap="wrap">
          {tags.map((tag) => {
            const { background, textColor } = generateTagColor(tag);
            return (
              <Badge
                key={tag}
                size="2"
                style={{
                  backgroundColor: background,
                  color: textColor,
                  border: `1px solid ${background}`,
                }}
              >
                {tag}
                {!disabled && (
                  <X
                    size={12}
                    style={{
                      cursor: "pointer",
                      marginLeft: 4,
                      color: textColor,
                    }}
                    onClick={() => handleRemoveTag(tag)}
                  />
                )}
              </Badge>
            );
          })}
        </Flex>
      )}
      {existingTags && existingTags.length > 0 && (
        <Flex direction="column" gap="1">
          {existingTagsLabel && (
            <Text size="1" color="gray">
              {existingTagsLabel}:
            </Text>
          )}
          <Flex gap="2" wrap="wrap">
            {existingTags.map((tag) => {
              const { background, textColor } = generateTagColor(tag);
              return (
                <Badge
                  key={tag}
                  size="1"
                  variant="soft"
                  style={{
                    backgroundColor: background,
                    color: textColor,
                    cursor: disabled ? "default" : "pointer",
                    opacity: disabled ? 0.6 : 1,
                  }}
                  onClick={() => !disabled && handleQuickAddTag(tag)}
                >
                  {tag}
                </Badge>
              );
            })}
          </Flex>
        </Flex>
      )}
    </Flex>
  );
}
