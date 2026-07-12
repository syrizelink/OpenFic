import { zodResolver } from "@hookform/resolvers/zod";
import { Dialog, Flex, Button, Text, TextField, Box } from "@radix-ui/themes";
import { Check, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useForm, Controller, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ProviderIdSelect, Spinner } from "@/components";
import type { ModelProvider, ModelProviderCatalogProvider } from "@/lib/model.types";

import { validateProvider } from "../lib/model-api";
import { ProviderIcon } from "../lib/provider-icons";
import { getProviderUrl } from "../lib/provider-utils";

const connectionSchema = z
  .object({
    name: z.string().optional(),
    url: z.string().optional(), // URL 现在是可选的，因为固定提供商会自动填充
    apiKey: z.string().optional(),
    providerType: z.string().min(1, "providerTypeRequired"),
  })
  .refine(
    (data) => {
      // 如果是 OpenAI 兼容模式，URL 是必需的
      if (data.providerType === "openai-compatible") {
        return data.url && data.url.trim().length > 0;
      }
      // 其他模式，URL 会自动填充，不需要验证
      return true;
    },
    {
      message: "urlRequired",
      path: ["url"],
    },
  );

type ConnectionFormData = z.infer<typeof connectionSchema>;

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

  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
    reset,
    setValue,
  } = useForm<ConnectionFormData>({
    resolver: zodResolver(connectionSchema),
    values: connection
      ? {
          name: connection.name || "",
          url: connection.url || "",
          apiKey: "",
          providerType: connection.providerType || "",
        }
      : {
          name: "",
          url: "",
          apiKey: "",
          providerType: "",
        },
  });

  const providerType = useWatch({ control, name: "providerType" });
  const url = useWatch({ control, name: "url" });
  const apiKey = useWatch({ control, name: "apiKey" });
  const selectedCatalogProvider = useMemo(
    () => catalogProviders?.find((provider) => provider.providerType === providerType),
    [catalogProviders, providerType],
  );

  // 切换到 OpenAI-compatible 时只清空一次 URL，不要在每次输入时重置。
  useEffect(() => {
    if (!providerType) return;

    if (providerType === "openai-compatible") {
      // 切换到 OpenAI 兼容模式时，清空 URL（除非是编辑模式且原本就是 OpenAI 兼容）
      if (!isEditing || connection?.providerType !== "openai-compatible") {
        setValue("url", "");
      }
    }
  }, [providerType, setValue, isEditing, connection]);

  // 当提供商类型改变时，自动设置固定 URL
  useEffect(() => {
    if (!providerType || providerType === "openai-compatible") {
      return;
    }

    // 其他提供商类型，使用固定 URL
    const fixedUrl = getProviderUrl(providerType, catalogProviders);
    if (fixedUrl) {
      // 在新建模式下，自动设置固定 URL
      // 在编辑模式下，如果当前 URL 为空或者是固定 URL，则更新为新的固定 URL
      if (!isEditing) {
        setValue("url", fixedUrl);
      } else {
        // 编辑模式下，检查当前 URL 是否为空或等于旧的固定 URL
        const currentUrl = url;
        const oldFixedUrl = connection?.providerType
          ? getProviderUrl(connection.providerType, catalogProviders)
          : null;

        // 如果当前 URL 为空，或者是旧的固定 URL，则更新为新的固定 URL
        if (!currentUrl || currentUrl.trim() === "" || currentUrl === oldFixedUrl) {
          setValue("url", fixedUrl);
        }
      }
    }
  }, [providerType, setValue, isEditing, url, connection, catalogProviders]);

  // 验证连接
  const handleValidate = useCallback(async () => {
    const formData = getValues();

    if (!formData.providerType) {
      return;
    }

    // 确定要使用的 URL
    let validateUrl = formData.url;
    if (!validateUrl || validateUrl.trim() === "") {
      const fixedUrl = getProviderUrl(formData.providerType, catalogProviders);
      if (fixedUrl) {
        validateUrl = fixedUrl;
      } else {
        // OpenAI 兼容模式必须提供 URL
        setValidationStatus("error");
        return;
      }
    }

    // 如果没有apiKey且是新建模式，显示错误
    if (!isEditing && !formData.apiKey) {
      setValidationStatus("error");
      return;
    }

    setValidationStatus("validating");

    try {
      // 通过后端验证连接（后端会访问 URL/models 接口）
      const result = await validateProvider({
        provider_type: formData.providerType,
        url: validateUrl,
        api_key: formData.apiKey || "", // 编辑时可以为空
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

  // 提交表单
  const onFormSubmit = useCallback(
    async (data: ConnectionFormData) => {
      const formData = new FormData();

      formData.append("name", data.name || "");

      // 确定要使用的 URL
      let finalUrl = data.url;
      if (!finalUrl || finalUrl.trim() === "") {
        // 如果没有 URL，尝试从提供商类型获取固定 URL
        const fixedUrl = getProviderUrl(data.providerType, catalogProviders);
        if (fixedUrl) {
          finalUrl = fixedUrl;
        }
      }

      if (!finalUrl) {
        // 如果还是没有 URL，这是错误情况
        setValidationStatus("error");
        return;
      }

      formData.append("url", finalUrl);
      formData.append("provider_type", data.providerType);

      // 只有在提供了 API Key 时才包含它
      if (data.apiKey) {
        formData.append("api_key", data.apiKey);
      }

      await onSubmit(formData);
      reset();
      setValidationStatus("idle");
    },
    [catalogProviders, onSubmit, reset],
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
    if (providerType === "openai-compatible" && (!url || !url.trim())) return false;
    if (!isEditing && !apiKey) return false;
    return true;
  }, [providerType, url, isEditing, apiKey]);

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
            {/* 第一行：目录图标和基本信息 */}
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
                <ProviderIcon
                  iconPath={selectedCatalogProvider?.iconPath || connection?.iconPath}
                  size={40}
                />
              </Box>

              {/* 右侧：备注名称和提供商类型 */}
              <Flex
                direction="column"
                gap="3"
                style={{ flex: 1 }}
              >
                {/* 备注名称 */}
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

                {/* 提供商类型 */}
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

            {/* 服务 URL - 仅 OpenAI 兼容模式显示 */}
            {providerType === "openai-compatible" && (
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

            {/* 操作按钮 */}
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
                    isAgentSettingsLocked ||
                    isSubmitting ||
                    (!isEditing && validationStatus !== "success")
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
