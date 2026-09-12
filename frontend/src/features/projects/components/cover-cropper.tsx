/**
 * CoverCropper Component
 *
 * Komponen pemotong sampul, mendukung pemilihan gambar, pratinjau, dan pemotongan (rasio tetap 2:3).
 * Fungsi pemotongan ditampilkan lewat dialog berlapis.
 */

import { Box, Button, Dialog, Flex, Text } from "@radix-ui/themes";
import { Upload } from "lucide-react";
import { useState, useCallback, useRef } from "react";
import Cropper, { type Area } from "react-easy-crop";
import { useTranslation } from "react-i18next";

interface CoverCropperProps {
  /** Berkas hasil pemotongan saat ini */
  value: File | null;
  /** Callback perubahan berkas */
  onChange: (file: File | null) => void;
  /** URL pratinjau sampul yang sudah ada (mode sunting) */
  previewUrl?: string | null;
}

/** Informasi area pemotongan */
interface CroppedArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Membuat berkas gambar hasil pemotongan.
 */
async function getCroppedImage(imageSrc: string, croppedAreaPixels: CroppedArea): Promise<File> {
  const image = new Image();
  image.src = imageSrc;

  await new Promise((resolve) => {
    image.onload = resolve;
  });

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;

  // Menyetel ukuran kanvas sesuai ukuran area pemotongan
  canvas.width = croppedAreaPixels.width;
  canvas.height = croppedAreaPixels.height;

  // Menggambar gambar hasil pemotongan
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

  // Mengubah menjadi Blob
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(new File([blob], "cover.jpg", { type: "image/jpeg" }));
      }
    }, "image/jpeg");
  });
}

export function CoverCropper({ value, onChange, previewUrl }: CoverCropperProps) {
  const { t } = useTranslation();
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /** Menangani pemilihan berkas */
  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      setImageSrc(reader.result as string);
      // Mereset status pemotongan
      setCrop({ x: 0, y: 0 });
      setZoom(1);
    };
    reader.readAsDataURL(file);
  }, []);

  /** Callback pemotongan selesai */
  const onCropComplete = useCallback((_croppedArea: Area, croppedAreaPixels: Area) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  /** Mengonfirmasi pemotongan */
  const handleCropConfirm = useCallback(async () => {
    if (!imageSrc || !croppedAreaPixels) return;

    try {
      const croppedFile = await getCroppedImage(imageSrc as string, croppedAreaPixels);
      onChange(croppedFile);
      setImageSrc(null);
    } catch (error) {
      console.error("Gagal memotong:", error);
    }
  }, [imageSrc, croppedAreaPixels, onChange]);

  /** Membatalkan pemotongan */
  const handleCropCancel = useCallback(() => {
    setImageSrc(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  // Mode tampilan (sampul sudah ada atau pratinjau)
  const displayUrl = value ? URL.createObjectURL(value) : previewUrl;

  return (
    <Box>
      <Text
        as="label"
        size="2"
        weight="medium"
        mb="2"
        style={{ display: "block" }}
      >
        {t("coverCropper.projectCover")}
      </Text>

      {displayUrl ? (
        <Box>
          <Box
            style={{
              width: "160px",
              aspectRatio: "2/3",
              overflow: "hidden",
              borderRadius: "var(--radius-3)",
              background: "var(--gray-a3)",
            }}
          >
            <img
              src={displayUrl}
              alt={t("coverCropper.coverPreview")}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          </Box>
          <Button
            mt="2"
            variant="soft"
            size="2"
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            {t("coverCropper.changeCover")}
          </Button>
        </Box>
      ) : (
        <Box
          style={{
            width: "160px",
            aspectRatio: "2/3",
            border: "2px dashed var(--gray-a7)",
            borderRadius: "var(--radius-3)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "border-color 0.15s, background-color 0.15s",
            background: "var(--gray-a2)",
          }}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInputRef.current?.click();
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--accent-a8)";
            e.currentTarget.style.background = "var(--accent-a2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--gray-a7)";
            e.currentTarget.style.background = "var(--gray-a2)";
          }}
        >
          <Upload
            size={24}
            style={{ color: "var(--gray-a9)", marginBottom: "8px" }}
          />
          <Text
            size="1"
            color="gray"
          >
            {t("coverCropper.uploadCover")}
          </Text>
        </Box>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handleFileSelect}
      />

      {/* Dialog pemotongan */}
      <Dialog.Root
        open={!!imageSrc}
        onOpenChange={(open) => {
          if (!open) {
            handleCropCancel();
          }
        }}
      >
        <Dialog.Content maxWidth="600px">
          <Dialog.Title>{t("coverCropper.cropCover")}</Dialog.Title>
          <Dialog.Description
            size="2"
            color="gray"
          >
            {t("coverCropper.cropDescription")}
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
                aspect={2 / 3}
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
              {t("coverCropper.confirmCrop")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
