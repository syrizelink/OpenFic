import { useCallback, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  ScrollArea,
  Spinner,
  Text,
} from "@radix-ui/themes";
import {
  AlertCircle,
  Check,
  ChevronLeft,
  FileText,
  Upload,
} from "lucide-react";

import type { SkillCreate } from "@/lib/skill.types";
import { parseSkillMarkdown } from "../lib/skill-import";
import "./import-skill-dialog.css";

interface ImportSkillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: SkillCreate) => void;
}

type Step = "select" | "preview" | "complete";

interface PreviewState {
  payload: SkillCreate;
  fileName: string;
  isRecognized: boolean;
}

export function ImportSkillDialog({
  open,
  onOpenChange,
  onCreate,
}: ImportSkillDialogProps) {
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setStep("select");
    setLoading(false);
    setError(null);
    setPreview(null);
  }, []);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        resetState();
      }
      onOpenChange(nextOpen);
    },
    [onOpenChange, resetState]
  );

  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!selectedFile.name.toLowerCase().endsWith(".md")) {
        setError("仅支持 .md 格式的 Markdown 文件");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const text = await selectedFile.text();
        const payload = parseSkillMarkdown(text);
        const isRecognized = !!(payload.name || payload.summary);

        if (!payload.name) {
          payload.name = selectedFile.name.replace(/\.md$/i, "");
        }

        setPreview({ payload, fileName: selectedFile.name, isRecognized });
        setStep("preview");
      } catch {
        setError("文件读取失败");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const droppedFile = event.dataTransfer.files[0];
      if (droppedFile) {
        void handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect]
  );

  const handleConfirm = useCallback(() => {
    if (!preview) return;
    onCreate(preview.payload);
    setStep("complete");
  }, [preview, onCreate]);

  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <input
              className="import-skill-file-input"
              ref={fileInputRef}
              type="file"
              accept=".md"
              onChange={(event) => {
                const selectedFile = event.target.files?.[0];
                if (selectedFile) {
                  void handleFileSelect(selectedFile);
                }
              }}
            />
            <Box
              className="import-skill-dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={48} className="import-skill-upload-icon" />
              <Text as="p" size="3" weight="medium" mb="2">
                拖放或点击选择文件
              </Text>
              <Text as="p" size="2" color="gray">
                支持 .md 格式的 Markdown 文件
              </Text>
            </Box>

            {loading && (
              <Flex align="center" gap="2" mt="4" justify="center">
                <Spinner size="2" />
                <Text size="2" color="gray">
                  正在解析...
                </Text>
              </Flex>
            )}
          </Box>
        );

      case "preview":
        return (
          <Box>
            {preview && (
              <ScrollArea className="import-skill-preview-scroll">
                <Flex gap="3" mb="3" align="center">
                  <FileText size={16} color="var(--gray-9)" />
                  <Text size="2" weight="medium" truncate style={{ flex: 1 }}>
                    {preview.fileName}
                  </Text>
                  <Badge size="1" color={preview.isRecognized ? "green" : "amber"}>
                    {preview.isRecognized ? "已识别为 Skill" : "未识别格式"}
                  </Badge>
                </Flex>

                <Flex direction="column" gap="3">
                  <Box>
                    <Text size="1" color="gray" mb="1" className="import-skill-label">
                      名称
                    </Text>
                    <Text size="2">
                      {preview.payload.name || "（无）"}
                    </Text>
                  </Box>

                  {preview.payload.skillId && (
                    <Box>
                      <Text size="1" color="gray" mb="1" className="import-skill-label">
                        ID
                      </Text>
                      <Text size="2">
                        {preview.payload.skillId}
                      </Text>
                    </Box>
                  )}

                  {preview.payload.summary && (
                    <Box>
                      <Text size="1" color="gray" mb="1" className="import-skill-label">
                        简述
                      </Text>
                      <ScrollArea className="import-skill-summary-preview">
                        <Text size="2" style={{ whiteSpace: "pre-wrap" }}>
                          {preview.payload.summary}
                        </Text>
                      </ScrollArea>
                    </Box>
                  )}

                  {preview.payload.content && (
                    <Box>
                      <Text size="1" color="gray" mb="1" className="import-skill-label">
                        内容预览
                      </Text>
                      <ScrollArea className="import-skill-content-preview">
                        <Box p="2">
                          <Text size="2" style={{ whiteSpace: "pre-wrap" }}>
                            {preview.payload.content.length > 2000
                              ? preview.payload.content.slice(0, 2000) + "..."
                              : preview.payload.content}
                          </Text>
                        </Box>
                      </ScrollArea>
                    </Box>
                  )}
                </Flex>

                {!preview.isRecognized && (
                  <Flex align="center" gap="2" mt="3">
                    <AlertCircle size={14} color="var(--amber-9)" />
                    <Text size="1" color="amber">
                      未识别为标准 Skill 格式，文件内容将作为技能内容导入
                    </Text>
                  </Flex>
                )}
              </ScrollArea>
            )}
          </Box>
        );

      case "complete":
        return (
          <Box className="import-skill-complete">
            <Box className="import-skill-complete-icon">
              <Check size={32} color="var(--green-9)" />
            </Box>
            <Text as="p" size="5" weight="bold" mb="2">
              导入成功
            </Text>
            <Text as="p" size="2" color="gray">
              技能「{preview?.payload.name}」已创建
            </Text>
          </Box>
        );
    }
  };

  const renderFooter = () => {
    switch (step) {
      case "select":
        return (
          <Button variant="soft" color="gray" onClick={() => handleOpenChange(false)}>
            关闭
          </Button>
        );
      case "preview":
        return (
          <Flex gap="3" justify="between" className="import-skill-preview-footer">
            <Button variant="soft" color="gray" onClick={() => setStep("select")}>
              <ChevronLeft size={16} />
              返回
            </Button>
            <Button onClick={handleConfirm}>确认导入</Button>
          </Flex>
        );
      case "complete":
        return <Button onClick={() => handleOpenChange(false)}>完成</Button>;
    }
  };

  const getStepTitle = () => {
    switch (step) {
      case "select":
        return "选择要导入的 Markdown 文件";
      case "preview":
        return "确认导入内容";
      case "complete":
        return "导入完成";
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content maxWidth="680px">
        <Dialog.Title>导入技能</Dialog.Title>
        <Dialog.Description size="2" color="gray" mb="4">
          {getStepTitle()}
        </Dialog.Description>

        {renderStepContent()}

        {error && (
          <Flex align="center" gap="2" mt="3">
            <AlertCircle size={14} color="var(--red-9)" />
            <Text size="2" color="red">
              {error}
            </Text>
          </Flex>
        )}

        <Flex gap="3" mt="5" justify="end">
          {renderFooter()}
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
