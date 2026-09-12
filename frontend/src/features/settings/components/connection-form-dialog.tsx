import { zodResolver } from "@hookform/resolvers/zod";
import { Dialog, Flex, Button, Text, TextField, Box } from "@radix-ui/themes";
import { Check, Plus, Trash2, X, Component } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useFieldArray, useForm, Controller, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ProviderIdSelect, Spinner } from "@/components";
import type { ModelProvider, ModelProviderCatalogProvider } from "@/lib/model.types";

import { validateProvider } from "../lib/model-api";
import { ProviderIcon } from "../lib/provider-icons";
import { getProviderUrl, isCustomProviderType } from "../lib/provider-utils";

import "./connection-form-dialog.css";

function requiresProviderUrl(
  providerType: string,
  catalogProviders?: ModelProviderCatalogProvider[],
): boolean {
  return Boolean(providerType) && !getProviderUrl(providerType, catalogProviders);
}

const connectionSchema = z.object({
  name: z.string().optional(),
  url: z.string().optional(),
  apiKey: z.string().optional(),
  providerType: z.string().min(1, "providerTypeRequired"),
  customHeaders: z.array(
    z.object({
      key: z.string(),
      value: z.string(),
    }),
  ),
});

type ConnectionFormData = z.infer<typeof connectionSchema>;

const MASKED_CUSTOM_HEADER_VALUE = "••••••••";

function serializeCustomHeaders(headers: ConnectionFormData["customHeaders"]) {
  return headers
    .filter((header) => header.key.trim())
    .map((header) => ({
      key: header.key,
      value: header.value === MASKED_CUSTOM_HEADER_VALUE ? "" : header.value,
    }));
}

interface ConnectionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connection?: ModelProvider;
  catalogProviders?: ModelProviderCatalogProvider[];
  isCatalogLoading?: boolean;
  onSubmit: (data: FormData) => Promise<void>;
  isSubmitting: boolean;
  isAgentSettingsLocked: boolean;
}

export function ConnectionFormDialog({
  open,
  onOpenChange,
  connection,
  catalogProviders,
  isCatalogLoading = false,
  onSubmit,
  isSubmitting,
  isAgentSettingsLocked,
}: ConnectionFormDialogProps) {
  const { t } = useTranslation();
  const isEditing = !!connection;

  const [validationStatus, setValidationStatus] = useState<
    "idle" | "validating" | "success" | "error"
  >("idle");

  const initialFormValues = useMemo<ConnectionFormData>(
    () =>
      connection
        ? {
            name: connection.name || "",
            url: connection.url || "",
            apiKey: "",
            providerType: connection.providerType || "",
            customHeaders: (connection.customHeaderNames || []).map((key) => ({
              key,
              value: MASKED_CUSTOM_HEADER_VALUE,
            })),
          }
        : {
            name: "",
            url: "",
            apiKey: "",
            providerType: "",
            customHeaders: [],
          },
    [connection],
  );

  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
    reset,
    setValue,
  } = useForm<ConnectionFormData>({
    resolver: zodResolver(connectionSchema),
    values: initialFormValues,
  });

  const {
    fields: customHeaderFields,
    append,
    remove,
  } = useFieldArray({
    control,
    name: "customHeaders",
  });

  const providerType = useWatch({ control, name: "providerType" });
  const url = useWatch({ control, name: "url" });
  const apiKey = useWatch({ control, name: "apiKey" });
  const selectedCatalogProvider = useMemo(
    () => catalogProviders?.find((provider) => provider.providerType === providerType),
    [catalogProviders, providerType],
  );
  const providerIconPath = selectedCatalogProvider?.iconPath || connection?.iconPath;

  // Saat berpindah ke penyedia yang meminta alamat dari pengguna, URL hanya dikosongkan sekali.
  useEffect(() => {
    if (!providerType) return;

    if (requiresProviderUrl(providerType, catalogProviders)) {
      if (!isEditing || connection?.providerType !== providerType) {
        setValue("url", "");
      }
    }
  }, [providerType, catalogProviders, setValue, isEditing, connection]);

  // Saat jenis penyedia berubah, URL tetap disetel otomatis
  useEffect(() => {
    if (!providerType || requiresProviderUrl(providerType, catalogProviders)) {
      return;
    }

    // Jenis penyedia lain memakai URL tetap
    const fixedUrl = getProviderUrl(providerType, catalogProviders);
    if (fixedUrl) {
      // Pada mode buat baru, URL tetap disetel otomatis
      // Pada mode sunting, jika URL saat ini kosong atau berupa URL tetap, perbarui ke URL tetap yang baru
      if (!isEditing) {
        setValue("url", fixedUrl);
      } else {
        // Pada mode sunting, periksa apakah URL saat ini kosong atau sama dengan URL tetap yang lama
        const currentUrl = url;
        const oldFixedUrl = connection?.providerType
          ? getProviderUrl(connection.providerType, catalogProviders)
          : null;

        // Jika URL saat ini kosong atau berupa URL tetap lama, perbarui ke URL tetap yang baru
        if (!currentUrl || currentUrl.trim() === "" || currentUrl === oldFixedUrl) {
          setValue("url", fixedUrl);
        }
      }
    }
  }, [providerType, setValue, isEditing, url, connection, catalogProviders]);

  // Memvalidasi koneksi
  const handleValidate = useCallback(async () => {
    const formData = getValues();

    if (!formData.providerType) {
      return;
    }

    // Menentukan URL yang akan dipakai
    let validateUrl = formData.url;
    if (!validateUrl || validateUrl.trim() === "") {
      const fixedUrl = getProviderUrl(formData.providerType, catalogProviders);
      if (fixedUrl) {
        validateUrl = fixedUrl;
      } else {
        // Mode kompatibel OpenAI wajib menyediakan URL
        setValidationStatus("error");
        return;
      }
    }

    // Jika apiKey tidak ada dan sedang mode buat baru, tampilkan galat
    if (!isEditing && !formData.apiKey) {
      setValidationStatus("error");
      return;
    }

    setValidationStatus("validating");

    try {
      // Memvalidasi koneksi lewat backend (backend akan mengakses antarmuka URL/models)
      const result = await validateProvider({
        provider_type: formData.providerType,
        url: validateUrl,
        api_key: formData.apiKey || "", // Boleh kosong saat menyunting
        custom_headers: isCustomProviderType(formData.providerType)
          ? serializeCustomHeaders(formData.customHeaders)
          : [],
      });

      if (result.success) {
        setValidationStatus("success");
      } else {
        setValidationStatus("error");
      }
    } catch {
      setValidationStatus("error");
    }
  }, [catalogProviders, getValues, isEditing]);

  // Mengirim formulir
  const onFormSubmit = useCallback(
    async (data: ConnectionFormData) => {
      if (!isEditing && !data.apiKey?.trim()) {
        return;
      }

      const formData = new FormData();

      formData.append("name", data.name || "");

      // Menentukan URL yang akan dipakai
      let finalUrl = data.url;
      if (!finalUrl || finalUrl.trim() === "") {
        // Jika URL tidak ada, coba ambil URL tetap dari jenis penyedia
        const fixedUrl = getProviderUrl(data.providerType, catalogProviders);
        if (fixedUrl) {
          finalUrl = fixedUrl;
        }
      }

      if (!finalUrl) {
        // Jika URL tetap tidak ada, ini kondisi galat
        setValidationStatus("error");
        return;
      }

      formData.append("url", finalUrl);
      formData.append("provider_type", data.providerType);

      // API Key hanya disertakan bila memang disediakan
      if (data.apiKey) {
        formData.append("api_key", data.apiKey);
      }

      if (isCustomProviderType(data.providerType)) {
        formData.append(
          "custom_headers",
          JSON.stringify(serializeCustomHeaders(data.customHeaders)),
        );
      }

      await onSubmit(formData);
      reset();
      setValidationStatus("idle");
    },
    [catalogProviders, isEditing, onSubmit, reset],
  );

  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        setValidationStatus("idle");
      }
      onOpenChange(newOpen);
    },
    [onOpenChange],
  );

  const canValidate = useMemo(() => {
    if (!providerType) return false;
    if (requiresProviderUrl(providerType, catalogProviders) && (!url || !url.trim())) return false;
    if (!isEditing && !apiKey) return false;
    return true;
  }, [providerType, catalogProviders, url, isEditing, apiKey]);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="500px">
        <Dialog.Title>
          {isEditing ? t("connections.editConnection") : t("connections.createConnection")}
        </Dialog.Title>

        <form onSubmit={handleSubmit(onFormSubmit)}>
          <Flex
            direction="column"
            gap="4"
            mt="4"
          >
            {/* Baris pertama: ikon direktori dan informasi dasar */}
            <Flex
              gap="3"
              align="center"
            >
              <Box
                style={{
                  width: 80,
                  height: 80,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "var(--radius-2)",
                  background: "var(--gray-a3)",
                }}
              >
                {providerIconPath ? (
                  <ProviderIcon
                    iconPath={providerIconPath}
                    size={40}
                  />
                ) : isCustomProviderType(providerType) ? (
                  <Component
                    size={40}
                    aria-hidden="true"
                  />
                ) : null}
              </Box>

              {/* Kanan: nama catatan dan jenis penyedia */}
              <Flex
                direction="column"
                gap="3"
                style={{ flex: 1 }}
              >
                {/* Nama catatan */}
                <Flex
                  direction="column"
                  gap="2"
                >
                  <Text
                    size="2"
                    weight="medium"
                    color="gray"
                  >
                    {t("connections.name")}
                  </Text>
                  <Controller
                    name="name"
                    control={control}
                    render={({ field }) => (
                      <TextField.Root
                        {...field}
                        placeholder={t("connections.namePlaceholder")}
                        disabled={isAgentSettingsLocked}
                      />
                    )}
                  />
                </Flex>

                {/* Jenis penyedia */}
                <Flex
                  direction="column"
                  gap="2"
                >
                  <Text
                    size="2"
                    weight="medium"
                    color="gray"
                  >
                    {t("connections.providerType")}{" "}
                    <Text
                      color="red"
                      style={{ display: "inline" }}
                    >
                      *
                    </Text>
                  </Text>
                  <Controller
                    name="providerType"
                    control={control}
                    render={({ field }) => (
                      <ProviderIdSelect
                        value={field.value}
                        onChange={field.onChange}
                        providers={catalogProviders ?? []}
                        placeholder={t("connections.providerTypePlaceholder")}
                        disabled={isAgentSettingsLocked || isEditing}
                      />
                    )}
                  />
                  {errors.providerType && (
                    <Text
                      size="1"
                      color="red"
                    >
                      {t(`connections.${errors.providerType.message}`)}
                    </Text>
                  )}
                  {!isEditing && isCatalogLoading && (
                    <Text
                      size="1"
                      color="gray"
                    >
                      {t("connections.catalogLoading")}
                    </Text>
                  )}
                </Flex>
              </Flex>
            </Flex>

            {requiresProviderUrl(providerType, catalogProviders) && (
              <Flex
                direction="column"
                gap="2"
              >
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                >
                  {t("connections.url")}{" "}
                  <Text
                    color="red"
                    style={{ display: "inline" }}
                  >
                    *
                  </Text>
                </Text>
                <Controller
                  name="url"
                  control={control}
                  render={({ field }) => (
                    <TextField.Root
                      {...field}
                      placeholder={t("connections.urlPlaceholder")}
                      disabled={isAgentSettingsLocked}
                    />
                  )}
                />
                {errors.url && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t(`connections.${errors.url.message}`)}
                  </Text>
                )}
              </Flex>
            )}

            {/* API Key */}
            <Flex
              direction="column"
              gap="2"
            >
              <Text
                size="2"
                weight="medium"
                color="gray"
              >
                {t("connections.apiKey")}
                {!isEditing && (
                  <Text
                    color="red"
                    style={{ display: "inline" }}
                  >
                    {" "}
                    *
                  </Text>
                )}
              </Text>
              {isEditing ? (
                <Box>
                  <TextField.Root
                    value={apiKey || ""}
                    onChange={(e) => {
                      const form = getValues();
                      reset({
                        ...form,
                        apiKey: e.target.value,
                      });
                    }}
                    type="password"
                    placeholder={
                      apiKey ? t("connections.apiKeyPlaceholderEdit") : "••••••••••••••••"
                    }
                    disabled={isAgentSettingsLocked}
                  />
                  <Text
                    size="1"
                    color="gray"
                    mt="1"
                  >
                    {t("connections.apiKeyEditHint")}
                  </Text>
                </Box>
              ) : (
                <Controller
                  name="apiKey"
                  control={control}
                  render={({ field }) => (
                    <TextField.Root
                      {...field}
                      type="password"
                      placeholder={t("connections.apiKeyPlaceholder")}
                      disabled={isAgentSettingsLocked}
                    />
                  )}
                />
              )}
              {errors.apiKey && (
                <Text
                  size="1"
                  color="red"
                >
                  {t(`connections.${errors.apiKey.message}`)}
                </Text>
              )}
            </Flex>

            {isCustomProviderType(providerType) && (
              <Flex
                direction="column"
                gap="2"
              >
                <Flex
                  align="center"
                  justify="between"
                >
                  <Text
                    size="2"
                    weight="medium"
                    color="gray"
                  >
                    {t("connections.customHeaders")}
                  </Text>
                  <Button
                    type="button"
                    variant="ghost"
                    size="2"
                    className="connection-form-dialog__header-action"
                    aria-label={t("connections.addCustomHeader")}
                    onClick={() => append({ key: "", value: "" })}
                    disabled={isAgentSettingsLocked}
                  >
                    <Plus size={16} />
                  </Button>
                </Flex>
                <Box className="connection-form-dialog__headers-list">
                  <Flex
                    direction="column"
                    gap="2"
                  >
                    {customHeaderFields.map((field, index) => (
                      <Flex
                        key={field.id}
                        className="connection-form-dialog__header-row"
                        align="center"
                        gap="2"
                      >
                        <Controller
                          name={`customHeaders.${index}.key`}
                          control={control}
                          render={({ field: inputField }) => (
                            <TextField.Root
                              {...inputField}
                              className="connection-form-dialog__header-input"
                              placeholder={t("connections.customHeaderKeyPlaceholder")}
                              disabled={isAgentSettingsLocked}
                            />
                          )}
                        />
                        <Controller
                          name={`customHeaders.${index}.value`}
                          control={control}
                          render={({ field: inputField }) => (
                            <TextField.Root
                              {...inputField}
                              className="connection-form-dialog__header-input"
                              placeholder={t("connections.customHeaderValuePlaceholder")}
                              disabled={isAgentSettingsLocked}
                            />
                          )}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="2"
                          className="connection-form-dialog__header-action connection-form-dialog__header-action--delete"
                          aria-label={t("connections.removeCustomHeader")}
                          onClick={() => remove(index)}
                          disabled={isAgentSettingsLocked}
                        >
                          <Trash2 size={16} />
                        </Button>
                      </Flex>
                    ))}
                  </Flex>
                </Box>
              </Flex>
            )}

            {/* Tombol tindakan */}
            <Flex
              gap="3"
              mt="2"
              justify="between"
            >
              <Button
                type="button"
                variant="soft"
                onClick={handleValidate}
                disabled={
                  isAgentSettingsLocked || !canValidate || validationStatus === "validating"
                }
                style={{
                  backgroundColor:
                    validationStatus === "success"
                      ? "var(--green-a3)"
                      : validationStatus === "error"
                        ? "var(--red-a3)"
                        : undefined,
                  color:
                    validationStatus === "success"
                      ? "var(--green-11)"
                      : validationStatus === "error"
                        ? "var(--red-11)"
                        : undefined,
                }}
              >
                {validationStatus === "validating" ? <Spinner size={18} /> : null}
                {validationStatus === "success" && <Check size={16} />}
                {validationStatus === "error" && <X size={16} />}
                {validationStatus === "validating"
                  ? t("connections.validating")
                  : validationStatus === "success"
                    ? t("connections.validateSuccess")
                    : validationStatus === "error"
                      ? t("connections.validateFailed")
                      : t("connections.validate")}
              </Button>

              <Flex gap="3">
                <Dialog.Close>
                  <Button
                    type="button"
                    variant="soft"
                    color="gray"
                    disabled={isSubmitting}
                  >
                    {t("common.cancel")}
                  </Button>
                </Dialog.Close>
                <Button
                  type="submit"
                  disabled={
                    isAgentSettingsLocked || isSubmitting || (!isEditing && !apiKey?.trim())
                  }
                >
                  {isSubmitting ? <Spinner size={18} /> : null}
                  {isEditing ? t("common.save") : t("common.create")}
                </Button>
              </Flex>
            </Flex>
          </Flex>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  );
}
