/**
 * IconCropper Component
 *
 * 图标裁剪器组件，支持图片选择、预览和裁剪（固定 1:1 比例）。
 */

import { Box, Button, Dialog, Flex } from "@radix-ui/themes";
import { Upload } from "lucide-react";
import { useState, useCallback, useRef } from "react";
import Cropper, { type Area } from "react-easy-crop";
import { useTranslation } from "react-i18next";

import type { ProviderType } from "@/lib/model.types";

import { ProviderIcon } from "../lib/provider-icons";

interface IconCropperProps {
  /** 当前裁剪后的文件 */
  value: File | null;
  /** 文件变更回调 */
  onChange: (file: File | null) => void;
  /** 现有图标预览 URL（编辑模式） */
  previewUrl?: string | null;
  /** 提供商类型（用于显示默认图标） */
  providerType?: ProviderType;
  /** 内置 catalog 图标路径 */
  catalogIconPath?: string | null;
  /** 图标大小 */
  size?: number;
}

/** 裁剪区域信息 */
interface CroppedArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * 创建裁剪后的图片文件。
 */
async function getCroppedImage(imageSrc: string, croppedAreaPixels: CroppedArea): Promise<File> {
  const image = new Image();
  image.src = imageSrc;

  await new Promise((resolve) => {
    image.onload = resolve;
  });

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;

  // 设置画布尺寸为裁剪区域尺寸
  canvas.width = croppedAreaPixels.width;
  canvas.height = croppedAreaPixels.height;

  // 绘制裁剪后的图片
  ctx.drawImage(
    image,
    croppedAreaPixels.x,
    croppedAreaPixels.y,
    croppedAreaPixels.width,
    croppedAreaPixels.height,
    0,
    0,
    croppedAreaPixels.width,
    croppedAreaPixels.height,
  );

  // 转换为 Blob
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(new File([blob], "icon.jpg", { type: "image/jpeg" }));
      }
    }, "image/jpeg");
  });
}

export function IconCropper({
  value,
  onChange,
  previewUrl,
  providerType,
  catalogIconPath,
  size = 80,
}: IconCropperProps) {
  const { t } = useTranslation();
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 显示模式：优先显示自定义图标，否则显示默认图标
  const hasCustomIcon = value || previewUrl;

  /** 处理文件选择 */
  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      setImageSrc(reader.result as string);
      // 重置裁剪状态
      setCrop({ x: 0, y: 0 });
      setZoom(1);
    };
    reader.readAsDataURL(file);
  }, []);

  /** 裁剪完成回调 */
  const onCropComplete = useCallback((_croppedArea: Area, croppedAreaPixels: Area) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  /** 确认裁剪 */
  const handleCropConfirm = useCallback(async () => {
    if (!imageSrc || !croppedAreaPixels) return;

    try {
      const croppedFile = await getCroppedImage(imageSrc as string, croppedAreaPixels);
      onChange(croppedFile);
      setImageSrc(null);
    } catch (error) {
      console.error("裁剪失败:", error);
    }
  }, [imageSrc, croppedAreaPixels, onChange]);

  /** 取消裁剪 */
  const handleCropCancel = useCallback(() => {
    setImageSrc(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  return (
    <Box>
      <Box
        style={{
          width: size,
          height: size,
          position: "relative",
          cursor: "pointer",
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          fileInputRef.current?.click();
        }}
      >
        <Box
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "var(--radius-2)",
            background: hasCustomIcon ? "#ffffff" : "var(--gray-a3)",
            border: hasCustomIcon ? "1px solid var(--gray-a4)" : "none",
            overflow: "hidden",
          }}
        >
          {hasCustomIcon ? (
            <img
              src={value ? URL.createObjectURL(value) : previewUrl!}
              alt="Provider icon"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
              }}
            />
          ) : providerType ? (
            <ProviderIcon
              providerType={providerType}
              catalogIconPath={catalogIconPath}
              size={size * 0.5}
            />
          ) : (
            <Upload
              size={24}
              style={{ color: "var(--gray-a9)" }}
            />
          )}
        </Box>

        {/* Hover 遮罩 */}
        {isHovered && (
          <Box
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(0, 0, 0, 0.5)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-2)",
            }}
          >
            <Upload
              size={24}
              style={{ color: "white" }}
            />
          </Box>
        )}
      </Box>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handleFileSelect}
      />

      {/* 裁剪弹窗 */}
      <Dialog.Root
        open={!!imageSrc}
        onOpenChange={(open) => {
          if (!open) {
            handleCropCancel();
          }
        }}
      >
        <Dialog.Content maxWidth="600px">
          <Dialog.Title>{t("connections.cropIcon")}</Dialog.Title>
          <Dialog.Description
            size="2"
            color="gray"
          >
            {t("connections.cropIconDescription")}
          </Dialog.Description>

          <Box
            mt="4"
            style={{
              position: "relative",
              width: "100%",
              height: "400px",
              background: "var(--gray-a3)",
              borderRadius: "var(--radius-3)",
            }}
          >
            {imageSrc && (
              <Cropper
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                aspect={1}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={onCropComplete}
              />
            )}
          </Box>

          <Flex
            gap="3"
            mt="4"
            justify="end"
          >
            <Button
              variant="soft"
              color="gray"
              type="button"
              onClick={handleCropCancel}
            >
              {t("common.cancel")}
            </Button>
            <Button
              type="button"
              onClick={handleCropConfirm}
            >
              {t("common.confirm")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
