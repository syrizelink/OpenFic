import { Badge, Button, Dialog, Flex, Progress, Text, TextField } from "@radix-ui/themes";
import { useQueryClient } from "@tanstack/react-query";
import {
  CircleCheck,
  ChevronLeft,
  ChevronRight,
  CloudDownload,
  FolderArchive,
  Upload,
} from "lucide-react";
import {
  animate,
  AnimatePresence,
  motion,
  useIsPresent,
  useMotionValue,
  useReducedMotion,
  type Variants,
} from "motion/react";
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuid } from "uuid";

import { showErrorToast } from "@/components/toast";
import { getSocket } from "@/lib/socket-client";

import {
  installPlugin,
  installPluginFromRepository,
  pluginError,
  PLUGINS_QUERY_KEY,
  type InstalledPlugin,
} from "./api";
import { PluginDescription, PluginImage } from "./plugin-summary";

const PROGRESS_EVENT = "plugins:install-progress";
const WATCH_INSTALL_EVENT = "plugins:watch-install";
const MAX_PACKAGE_BYTES = 20 * 1024 * 1024;
const GITHUB_REPOSITORY =
  /^https:\/\/github\.com\/[a-z0-9][a-z0-9-]{0,38}\/([a-z0-9_.-]{1,104})(?:\/tree\/[^?#\s]+)?\/?$/i;
const stageLabels = {
  uploading: "plugins.installation.uploading",
  downloading: "plugins.installation.downloading",
  validating: "plugins.installation.validating",
  installing: "plugins.installation.installing",
  complete: "plugins.installation.finishing",
} as const;

type Method = "file" | "repository";
type Stage = keyof typeof stageLabels;

const installMethods = [
  { source: "file", icon: FolderArchive },
  { source: "repository", icon: CloudDownload },
] as const;

const panelTransition = { duration: 0.24, ease: [0.22, 1, 0.36, 1] } as const;
const panelVariants: Variants = {
  enter: (direction: number) => ({ x: direction * 40, opacity: 0 }),
  visible: { x: 0, opacity: 1 },
  exit: (direction: number) => ({ x: -direction * 40, opacity: 0 }),
};

function InstallPanel({
  children,
  direction,
  onHeightChange,
}: {
  children: ReactNode;
  direction: number;
  onHeightChange: (height: number) => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const isPresent = useIsPresent();
  useLayoutEffect(() => {
    const panel = panelRef.current;
    if (!isPresent || !panel) return;
    const measure = () => onHeightChange(Number.parseFloat(getComputedStyle(panel).height));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(panel);
    return () => observer.disconnect();
  }, [isPresent, onHeightChange]);

  return (
    <motion.div
      ref={panelRef}
      className="plugin-install-step"
      data-exiting={isPresent ? undefined : "true"}
      inert={!isPresent}
      aria-hidden={isPresent ? undefined : true}
      custom={direction}
      variants={panelVariants}
      initial="enter"
      animate="visible"
      exit="exit"
      transition={panelTransition}
    >
      {children}
    </motion.div>
  );
}

interface InstallProgress {
  stage: Stage;
  progress: number;
}

interface PluginInstallDialogProps {
  updateId?: string;
  onClose: () => void;
}

export function PluginInstallDialog({ updateId, onClose }: PluginInstallDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [method, setMethod] = useState<Method | null>(updateId ? "file" : null);
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [progress, setProgress] = useState<InstallProgress | null>(null);
  const [completedPlugin, setCompletedPlugin] = useState<InstalledPlugin | null>(null);
  const [installedPlugin, setInstalledPlugin] = useState<InstalledPlugin | null>(null);
  const [panelHeight, setPanelHeight] = useState<number>();
  const animatedHeight = useMotionValue<number | "auto">("auto");
  const fileInput = useRef<HTMLInputElement>(null);
  const activeOperation = useRef<string | null>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();
  useLayoutEffect(() => {
    if (prefersReducedMotion || panelHeight === undefined) {
      animatedHeight.jump("auto");
      return;
    }
    if (animatedHeight.get() === "auto") {
      animatedHeight.jump(panelHeight);
      return;
    }
    const animation = animate(animatedHeight, panelHeight, panelTransition);
    return () => animation.stop();
  }, [animatedHeight, panelHeight, prefersReducedMotion]);
  const level = installedPlugin ? 4 : progress ? 3 : method ? 2 : 1;
  const panelId = `${useId()}-${level}`;
  const titleId = `${panelId}-title`;
  const descriptionId = `${panelId}-description`;
  const previousLevel = useRef(level);
  const [committedLevel, setCommittedLevel] = useState(level);
  const [direction, setDirection] = useState(1);
  if (level !== committedLevel) {
    setCommittedLevel(level);
    setDirection(level > committedLevel ? 1 : -1);
  }
  useLayoutEffect(() => {
    if (previousLevel.current !== level)
      document.getElementById(titleId)?.focus({ preventScroll: true });
    previousLevel.current = level;
  }, [level, titleId]);

  useEffect(() => {
    if (!completedPlugin) return;
    const indicator = progressRef.current?.querySelector(".rt-ProgressIndicator");
    const animations = indicator?.getAnimations() ?? [];
    let timeout: number | undefined;
    let cancelled = false;
    void Promise.allSettled(animations.map((animation) => animation.finished)).then(() => {
      if (cancelled) return;
      timeout = window.setTimeout(() => {
        activeOperation.current = null;
        setInstalledPlugin(completedPlugin);
        setProgress(null);
      }, 500);
    });
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [completedPlugin]);

  function handleFile(selected: File) {
    setFile(null);
    if (
      !/\.zip$/i.test(selected.name) ||
      selected.size === 0 ||
      selected.size > MAX_PACKAGE_BYTES
    ) {
      const detail = t(
        /\.zip$/i.test(selected.name)
          ? "plugins.installation.invalidSize"
          : "plugins.installation.invalidPackage",
      );
      showErrorToast(detail, `${detail}\n${selected.name}`);
      return;
    }
    setFile(selected);
  }

  async function handleInstall() {
    if (!method || activeOperation.current || (method === "file" && !file)) return;
    const repositoryUrl = url.trim();
    if (method === "repository") {
      const repo = GITHUB_REPOSITORY.exec(repositoryUrl)?.[1].replace(/\.git$/i, "");
      if (!repo || repo === "." || repo === ".." || repo.length > 100) {
        const detail = t("plugins.installation.invalidRepository");
        showErrorToast(detail, detail);
        return;
      }
    }

    const operationId = uuid();
    activeOperation.current = operationId;
    setProgress({ stage: method === "file" ? "uploading" : "downloading", progress: 0 });
    const socket = getSocket();
    function handleProgress(event: Partial<InstallProgress> & { operation_id?: string }) {
      if (
        event?.operation_id !== operationId ||
        !event.stage ||
        !Object.hasOwn(stageLabels, event.stage) ||
        typeof event.progress !== "number" ||
        !Number.isFinite(event.progress)
      )
        return;
      const next = { stage: event.stage, progress: Math.max(0, Math.min(100, event.progress)) };
      setProgress((previous) => (previous && next.progress >= previous.progress ? next : previous));
    }
    function handleConnect() {
      socket.emit(WATCH_INSTALL_EVENT, operationId);
    }
    socket.on(PROGRESS_EVENT, handleProgress);
    socket.on("connect", handleConnect);
    try {
      if (socket.connected) handleConnect();
      else if (!socket.active) socket.connect();
      const installed =
        method === "repository"
          ? await installPluginFromRepository(repositoryUrl, operationId)
          : await installPlugin(file!, operationId, updateId, ({ progress: upload }) => {
              if (upload === undefined) return;
              setProgress((previous) =>
                previous?.stage === "uploading"
                  ? {
                      stage: "uploading",
                      progress: Math.max(previous.progress, Math.round(upload * 45)),
                    }
                  : previous,
              );
            });
      setProgress({ stage: "complete", progress: 100 });
      setCompletedPlugin(installed);
    } catch (failure) {
      showErrorToast(
        t(updateId ? "plugins.installation.updateFailed" : "plugins.installation.installFailed"),
        pluginError(failure),
      );
      activeOperation.current = null;
      setProgress(null);
    } finally {
      socket.off("connect", handleConnect);
      socket.off(PROGRESS_EVENT, handleProgress);
      if (socket.connected) socket.emit(WATCH_INSTALL_EVENT, null);
      void queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY });
    }
  }

  const title = installedPlugin
    ? t(updateId ? "plugins.installation.updateSuccess" : "plugins.installation.success")
    : progress
      ? t("plugins.installation.progress")
      : t(
          updateId
            ? "plugins.update"
            : method === "file"
              ? "plugins.installation.file"
              : method === "repository"
                ? "plugins.installation.repository"
                : "plugins.install",
        );

  const description = installedPlugin
    ? null
    : progress
      ? t(stageLabels[progress.stage])
      : method === "repository"
        ? t("plugins.installation.repositoryHint")
        : null;

  const panel = (
    <>
      <Dialog.Title
        id={titleId}
        size="3"
        tabIndex={-1}
        className={installedPlugin ? "plugin-install-success" : undefined}
      >
        {installedPlugin && (
          <CircleCheck
            size={40}
            className="plugin-install-check"
            aria-hidden="true"
          />
        )}
        {title}
      </Dialog.Title>
      {description !== null && (
        <Text
          as="p"
          id={descriptionId}
          size="2"
          color="gray"
          mb="4"
        >
          {description}
        </Text>
      )}

      {installedPlugin ? (
        <Flex
          direction="column"
          gap="4"
        >
          <Flex
            align="start"
            gap="3"
            className="plugin-install-summary"
          >
            <PluginImage
              plugin={installedPlugin}
              placement="detail"
            />
            <Flex
              direction="column"
              gap="1"
              className="plugin-detail-identity"
            >
              <Flex
                align="center"
                gap="2"
                className="plugin-install-summary-title"
              >
                <Text
                  size="2"
                  weight="medium"
                  truncate
                  title={installedPlugin.name}
                >
                  {installedPlugin.name}
                </Text>
                <Badge color="green">{installedPlugin.version}</Badge>
              </Flex>
              <PluginDescription
                description={installedPlugin.description || t("plugins.noDescription")}
              />
            </Flex>
          </Flex>
          <Flex justify="end">
            <Button onClick={onClose}>{t("import.finish")}</Button>
          </Flex>
        </Flex>
      ) : progress ? (
        <Flex
          direction="column"
          gap="2"
        >
          <Progress
            ref={progressRef}
            className="plugin-install-progress"
            value={progress.progress}
            aria-label={t(stageLabels[progress.stage])}
          />
          <Text
            size="1"
            color="gray"
            role="status"
            align="right"
          >
            {progress.progress > 0 ? `${progress.progress}%` : t("plugins.working")}
          </Text>
        </Flex>
      ) : !method ? (
        <Flex
          direction="column"
          gap="2"
        >
          {installMethods.map(({ source, icon: Icon }) => (
            <Button
              key={source}
              variant="outline"
              color="gray"
              size="3"
              className="plugin-install-method"
              onClick={() => setMethod(source)}
            >
              <Icon
                size={20}
                aria-hidden="true"
              />
              <span className="plugin-install-method-label">
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                  highContrast
                >
                  {t(`plugins.installation.${source}`)}
                </Text>
                <Text
                  size="1"
                  weight="regular"
                  color="gray"
                >
                  {t(`plugins.installation.${source}Description`)}
                </Text>
              </span>
              <ChevronRight
                size={16}
                aria-hidden="true"
              />
            </Button>
          ))}
        </Flex>
      ) : (
        <form
          className="plugin-install-source-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleInstall();
          }}
        >
          <Flex
            direction="column"
            gap="4"
          >
            {method === "file" ? (
              <>
                <input
                  ref={fileInput}
                  type="file"
                  accept=".zip"
                  hidden
                  aria-label={t("plugins.package")}
                  onChange={(event) => {
                    const selected = event.currentTarget.files?.[0];
                    if (selected) handleFile(selected);
                    event.currentTarget.value = "";
                  }}
                />
                <button
                  type="button"
                  className="plugin-install-dropzone"
                  onClick={() => fileInput.current?.click()}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    const selected = event.dataTransfer.files[0];
                    if (selected) handleFile(selected);
                  }}
                >
                  <Upload
                    size={28}
                    aria-hidden="true"
                  />
                  <Text
                    size="2"
                    weight="medium"
                  >
                    {file?.name ?? t("plugins.installation.dropHint")}
                  </Text>
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("plugins.installation.packageLimit")}
                  </Text>
                </button>
              </>
            ) : (
              <label>
                <Text
                  as="div"
                  size="2"
                  weight="medium"
                  mb="2"
                >
                  {t("plugins.installation.repositoryUrl")}
                </Text>
                <TextField.Root
                  type="text"
                  inputMode="url"
                  autoCapitalize="none"
                  spellCheck={false}
                  maxLength={256}
                  placeholder="https://github.com/owner/repo"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                />
              </label>
            )}
            <Flex
              justify="between"
              gap="2"
              wrap="wrap"
            >
              <Button
                type="button"
                color="gray"
                variant="soft"
                onClick={() => {
                  if (updateId) onClose();
                  else setMethod(null);
                }}
              >
                {!updateId && (
                  <ChevronLeft
                    size={16}
                    aria-hidden="true"
                  />
                )}
                {t(updateId ? "plugins.cancel" : "common.back")}
              </Button>
              <Button
                type="submit"
                disabled={method === "file" ? !file : !url.trim()}
              >
                {t(updateId ? "plugins.update" : "plugins.installation.start")}
              </Button>
            </Flex>
          </Flex>
        </form>
      )}
    </>
  );

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !activeOperation.current) onClose();
      }}
    >
      <Dialog.Content
        className="plugin-install-dialog"
        maxWidth="480px"
        aria-busy={!!progress}
        aria-labelledby={titleId}
        aria-describedby={description === null ? undefined : descriptionId}
      >
        {prefersReducedMotion ? (
          panel
        ) : (
          <motion.div
            className="plugin-install-steps"
            style={{ height: animatedHeight }}
          >
            <AnimatePresence
              initial={false}
              custom={direction}
            >
              <InstallPanel
                key={level}
                direction={direction}
                onHeightChange={setPanelHeight}
              >
                {panel}
              </InstallPanel>
            </AnimatePresence>
          </motion.div>
        )}
      </Dialog.Content>
    </Dialog.Root>
  );
}
