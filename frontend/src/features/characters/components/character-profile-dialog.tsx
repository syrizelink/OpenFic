import { Avatar, Box, Button, Dialog, Flex, Text, TextField } from "@radix-ui/themes";
import { Upload } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import Cropper, { type Area } from "react-easy-crop";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import type { CharacterListItem } from "@/lib/character.types";

interface CharacterProfileDialogProps {
  character: CharacterListItem | null;
  open: boolean;
  isSaving?: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: { name: string; image?: File | null }) => void;
}

interface CroppedArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

function getAvatarFallback(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

async function getCroppedImage(imageSrc: string, croppedAreaPixels: CroppedArea): Promise<File> {
  const image = new Image();
  image.src = imageSrc;

  await new Promise((resolve) => {
    image.onload = resolve;
  });

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas context is unavailable");

  canvas.width = croppedAreaPixels.width;
  canvas.height = croppedAreaPixels.height;
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

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Failed to crop avatar"));
        return;
      }
      resolve(new File([blob], "avatar.jpg", { type: "image/jpeg" }));
    }, "image/jpeg");
  });
}

export function CharacterProfileDialog({
  character,
  open,
  isSaving = false,
  onOpenChange,
  onSubmit,
}: CharacterProfileDialogProps) {
  if (!character) {
    return (
      <Dialog.Root
        open={open}
        onOpenChange={onOpenChange}
      />
    );
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <CharacterProfileDialogContent
        key={character.id}
        character={character}
        isSaving={isSaving}
        onSubmit={onSubmit}
      />
    </Dialog.Root>
  );
}

interface CharacterProfileDialogContentProps {
  character: CharacterListItem;
  isSaving: boolean;
  onSubmit: (data: { name: string; image?: File | null }) => void;
}

function CharacterProfileDialogContent({
  character,
  isSaving,
  onSubmit,
}: CharacterProfileDialogContentProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [name, setName] = useState(character.name);
  const [image, setImage] = useState<File | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null);

  const imageObjectUrl = useMemo(() => (image ? URL.createObjectURL(image) : undefined), [image]);
  const imagePreviewUrl = imageObjectUrl ?? character.imageUrl ?? undefined;

  useEffect(() => {
    if (!imageObjectUrl) return;
    return () => URL.revokeObjectURL(imageObjectUrl);
  }, [imageObjectUrl]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    onSubmit({ name: trimmedName, image });
  };

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      setImageSrc(reader.result as string);
      setCrop({ x: 0, y: 0 });
      setZoom(1);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleCropComplete = useCallback((_croppedArea: Area, croppedAreaPixels: Area) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const handleCropCancel = useCallback(() => {
    setImageSrc(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleCropConfirm = useCallback(async () => {
    if (!imageSrc || !croppedAreaPixels) return;
    const croppedFile = await getCroppedImage(imageSrc, croppedAreaPixels);
    setImage(croppedFile);
    setImageSrc(null);
  }, [croppedAreaPixels, imageSrc]);

  return (
    <Dialog.Content maxWidth="420px">
      <Dialog.Title>{t("characters.editProfile")}</Dialog.Title>

      <form onSubmit={handleSubmit}>
        <Flex
          direction="column"
          gap="4"
          mt="4"
        >
          <Flex
            align="center"
            gap="3"
          >
            <Avatar
              src={imagePreviewUrl}
              fallback={getAvatarFallback(name)}
              radius="full"
              size="5"
            />
            <Flex
              direction="column"
              gap="2"
              align="start"
            >
              <Text
                size="2"
                weight="medium"
              >
                {t("characters.avatar")}
              </Text>
              <Button
                type="button"
                size="2"
                variant="soft"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={16} />
                {imagePreviewUrl ? t("characters.changeAvatar") : t("characters.uploadAvatar")}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={handleFileSelect}
              />
            </Flex>
          </Flex>

          <Flex
            direction="column"
            gap="2"
          >
            <Text
              as="label"
              size="2"
              weight="medium"
              htmlFor={inputId}
            >
              {t("characters.name")}
            </Text>
            <TextField.Root
              id={inputId}
              value={name}
              placeholder={t("characters.namePlaceholder")}
              onChange={(event) => setName(event.target.value)}
            />
          </Flex>
        </Flex>

        <Flex
          justify="end"
          gap="3"
          mt="5"
        >
          <Dialog.Close>
            <Button
              type="button"
              variant="soft"
              color="gray"
            >
              {t("common.cancel")}
            </Button>
          </Dialog.Close>
          <Button
            type="submit"
            disabled={!name.trim() || isSaving}
          >
            {isSaving ? <Spinner size={18} /> : null}
            {isSaving ? t("writing.saving") : t("common.save")}
          </Button>
        </Flex>
      </form>

      <Dialog.Root
        open={!!imageSrc}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) handleCropCancel();
        }}
      >
        <Dialog.Content maxWidth="600px">
          <Dialog.Title>{t("characters.cropAvatar")}</Dialog.Title>
          <Dialog.Description
            size="2"
            color="gray"
          >
            {t("characters.cropAvatarDescription")}
          </Dialog.Description>

          <Box
            className="characters-avatar-cropper"
            mt="4"
          >
            {imageSrc && (
              <Cropper
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                aspect={1}
                cropShape="round"
                showGrid={false}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={handleCropComplete}
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
    </Dialog.Content>
  );
}
