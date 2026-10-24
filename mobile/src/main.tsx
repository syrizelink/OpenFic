import { Theme, Button, TextField, Dialog, IconButton } from "@radix-ui/themes";
import { Check, Globe, Plus, ScanQrCode, Server, Trash2 } from "lucide-react";
import { StrictMode, useEffect, useRef, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";

import brandLogo from "../../frontend/public/brand.svg";
import { toast } from "../../frontend/src/components/toast";
import { Toaster } from "../../frontend/src/components/toaster";
import { version as appVersion } from "../package.json";
import { AppUpdatePanel } from "./app-update";
import { normalizeInstanceUrl, readInstances, STORAGE_KEY, type Instance } from "./instances.mjs";
import { checkInstance, openInstance, scanInstanceUrl, supportsInstanceScanning } from "./native";

import "../../frontend/src/styles/index.css";
import "./styles.css";

export function App() {
  const [starting, setStarting] = useState(true);
  useEffect(() => {
    const timer = setTimeout(
      () => setStarting(false),
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 650,
    );
    return () => clearTimeout(timer);
  }, []);
  const [instances, setInstances] = useState<Instance[]>(() => readInstances(localStorage));
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [tab, setTab] = useState<"connect" | "about">("connect");
  const [showList, setShowList] = useState(false);
  const [selectedId, setSelectedId] = useState(() =>
    localStorage.getItem("openfic.mobile.last-instance"),
  );
  const [warning, setWarning] = useState<{ instance: Instance; version: string } | null>(null);
  const [skipWarning, setSkipWarning] = useState(false);
  const [adding, setAdding] = useState(instances.length === 0);
  const [removing, setRemoving] = useState<Instance | null>(null);
  const isAddingRef = useRef(false);
  const isOpeningRef = useRef(false);
  const isScanningRef = useRef(false);
  const selected = instances.find((item) => item.id === selectedId) ?? instances[0];

  function save(next: Instance[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setInstances(next);
  }
  async function add(event: FormEvent) {
    event.preventDefault();
    if (isAddingRef.current || isScanningRef.current) return;
    isAddingRef.current = true;
    setBusy(true);
    try {
      const normalized = normalizeInstanceUrl(url);
      if (instances.some((item) => item.url === normalized))
        throw new Error("这个实例已经添加，可以直接打开。");
      const result = await checkInstance(normalized);
      const instance = {
        id: crypto.randomUUID(),
        name: name.trim() || new URL(normalized).hostname,
        url: normalized,
      };
      save([...instances, instance]);
      setShowList(false);
      toast.success(`连接成功 · OpenFic ${result.version}`, { id: "mobile-instance-add-success" });
      setUrl("");
      setName("");
      setAdding(false);
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "连接失败，请检查地址和网络。", {
        id: "mobile-instance-add-error",
      });
    } finally {
      isAddingRef.current = false;
      setBusy(false);
    }
  }
  async function handleScanQrCode() {
    if (isScanningRef.current || isAddingRef.current || isOpeningRef.current) return;
    isScanningRef.current = true;
    setScanning(true);
    try {
      const scannedUrl = await scanInstanceUrl();
      if (scannedUrl !== null) setUrl(scannedUrl);
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "扫描失败，请重试。", {
        id: "mobile-instance-scan-error",
      });
    } finally {
      isScanningRef.current = false;
      setScanning(false);
    }
  }
  async function open(instance: Instance) {
    if (isOpeningRef.current) return;
    isOpeningRef.current = true;
    setActiveId(instance.id);
    try {
      const result = await checkInstance(instance.url);
      const key = `openfic.mobile.version-warning.${appVersion}.${result.version}`;
      if (result.version !== appVersion && localStorage.getItem(key) !== "1") {
        setSkipWarning(false);
        setWarning({ instance, version: result.version });
      } else await enter(instance);
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "连接失败，请检查服务器是否在线。", {
        id: "mobile-instance-open-error",
      });
    } finally {
      isOpeningRef.current = false;
      setActiveId(null);
    }
  }
  async function enter(instance: Instance) {
    await openInstance(instance.url, instance.name);
    localStorage.setItem("openfic.mobile.last-instance", instance.id);
    setSelectedId(instance.id);
  }
  return (
    <Theme
      appearance="light"
      accentColor="gray"
      grayColor="gray"
      radius="medium"
      scaling="100%"
    >
      {starting && (
        <div
          className="mobile-splash"
          role="status"
          aria-label="正在启动 OpenFic"
        >
          <img
            src="/openfic.svg"
            alt="OpenFic"
          />
        </div>
      )}
      <main className="mobile-shell">
        <div className="mobile-content">
          <div
            className={`mobile-tab-panel mobile-connect-panel ${tab === "connect" ? "is-active" : "is-inactive"}`}
            aria-hidden={tab !== "connect"}
          >
            <div className="mobile-connect">
              <div className="mobile-connect-logo">
                <img
                  src={brandLogo}
                  alt="OpenFic"
                />
              </div>
              <div className="mobile-connect-body">
                {instances.length > 0 && !adding ? (
                  <>
                    <section
                      aria-labelledby="instances-title"
                      className="mobile-instances"
                    >
                      <div className="mobile-section-heading">
                        <h2 id="instances-title">{showList ? "选择实例" : "连接实例"}</h2>
                        <Button
                          variant="ghost"
                          onClick={() => setShowList((current) => !current)}
                        >
                          {showList ? "返回" : "查看更多"}
                        </Button>
                      </div>
                      <div className="mobile-instance-list">
                        {(showList ? instances : [selected]).map((instance) => (
                          <article
                            className="mobile-instance"
                            key={instance.id}
                          >
                            <Server
                              size={20}
                              className="mobile-instance-icon"
                            />
                            <button
                              className="mobile-instance-open"
                              disabled={busy || activeId !== null}
                              onClick={() => {
                                if (showList) {
                                  setSelectedId(instance.id);
                                  setShowList(false);
                                } else void open(instance);
                              }}
                            >
                              <span className="mobile-instance-name">
                                <strong>{instance.name}</strong>
                                {instance.id === selectedId && (
                                  <span className="mobile-last-open-badge">上次打开</span>
                                )}
                              </span>
                              <span>{instance.url}</span>
                            </button>
                            <IconButton
                              variant="ghost"
                              color="gray"
                              size="3"
                              disabled={busy || activeId !== null}
                              aria-label={`移除 ${instance.name}`}
                              onClick={() => setRemoving(instance)}
                            >
                              <Trash2 size={17} />
                            </IconButton>
                          </article>
                        ))}
                      </div>
                    </section>
                    {!showList && selected && (
                      <div className="mobile-form-actions">
                        <Button
                          size="3"
                          loading={activeId !== null}
                          onClick={() => void open(selected)}
                        >
                          连接
                        </Button>
                      </div>
                    )}
                    {showList && (
                      <Button
                        className="mobile-add"
                        size="3"
                        variant="soft"
                        disabled={activeId !== null}
                        onClick={() => setAdding(true)}
                      >
                        <Plus size={17} />
                        添加远程实例
                      </Button>
                    )}
                  </>
                ) : (
                  <section
                    className="mobile-connect-form"
                    aria-labelledby="connect-title"
                  >
                    <div className="mobile-section-heading">
                      <h2 id="connect-title">连接远程实例</h2>
                      <Button
                        type="button"
                        variant="ghost"
                        loading={scanning}
                        disabled={
                          busy || scanning || activeId !== null || !supportsInstanceScanning
                        }
                        title={
                          supportsInstanceScanning ? undefined : "请在 Android APP 中扫描二维码"
                        }
                        onClick={() => void handleScanQrCode()}
                      >
                        <ScanQrCode size={17} />
                        扫描二维码
                      </Button>
                    </div>
                    <form onSubmit={add}>
                      <label htmlFor="instance-name">
                        实例名称 <span className="mobile-optional">可选</span>
                      </label>
                      <TextField.Root
                        id="instance-name"
                        placeholder="例如：我的创作空间"
                        size="3"
                        maxLength={60}
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        disabled={busy || scanning}
                      />
                      <label htmlFor="instance-url">服务器地址</label>
                      <TextField.Root
                        id="instance-url"
                        placeholder="https://openfic.example.com"
                        type="url"
                        inputMode="url"
                        autoCapitalize="none"
                        autoCorrect="off"
                        spellCheck={false}
                        required
                        size="3"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        disabled={busy || scanning}
                      />
                      {url.trim().toLowerCase().startsWith("http://") && (
                        <p className="mobile-http-note">
                          HTTP 连接未加密，建议仅在可信局域网内使用。
                        </p>
                      )}
                      <div className="mobile-form-actions">
                        <Button
                          type="submit"
                          size="3"
                          loading={busy}
                          disabled={activeId !== null || scanning}
                        >
                          <Check size={17} />
                          验证并添加
                        </Button>
                        {instances.length > 0 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="3"
                            disabled={busy || scanning}
                            onClick={() => setAdding(false)}
                          >
                            取消
                          </Button>
                        )}
                      </div>
                    </form>
                  </section>
                )}
              </div>
            </div>
          </div>
          <section
            className={`mobile-about mobile-tab-panel ${tab === "about" ? "is-active" : "is-inactive"}`}
            aria-hidden={tab !== "about"}
            aria-label="关于"
          >
            <div className="mobile-about-logo">
              <img
                src={brandLogo}
                alt="OpenFic"
              />
            </div>
            <div className="mobile-about-row">
              <h2>版本</h2>
              <p>Mobile v{appVersion}</p>
            </div>
            <AppUpdatePanel />
            <a
              className="mobile-about-row"
              href="https://github.com/syrizelink/OpenFic/releases"
              target="_blank"
              rel="noreferrer"
            >
              更新日志
            </a>
            <a
              className="mobile-about-row"
              href="https://github.com/syrizelink/OpenFic/blob/main/LICENSE"
              target="_blank"
              rel="noreferrer"
            >
              开源许可证
            </a>
            <a
              className="mobile-about-row"
              href="https://github.com/syrizelink/OpenFic"
              target="_blank"
              rel="noreferrer"
            >
              <span>GitHub</span>
              <span className="mobile-about-value">/syrizelink/OpenFic</span>
            </a>
          </section>
        </div>
        <nav
          className="mobile-bottom-nav"
          aria-label="主导航"
        >
          <button
            aria-current={tab === "connect" ? "page" : undefined}
            onClick={() => setTab("connect")}
          >
            <span className="mobile-nav-pill">
              <Server size={20} />
              <span>连接</span>
            </span>
          </button>
          <button
            aria-current={tab === "about" ? "page" : undefined}
            onClick={() => setTab("about")}
          >
            <span className="mobile-nav-pill">
              <Globe size={20} />
              <span>关于</span>
            </span>
          </button>
        </nav>
      </main>
      <Dialog.Root
        open={removing !== null}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
      >
        <Dialog.Content maxWidth="400px">
          <Dialog.Title>移除实例？</Dialog.Title>
          <Dialog.Description>
            从此设备移除「{removing?.name}」的连接记录。远程实例及其创作数据会保留。
          </Dialog.Description>
          <div className="mobile-dialog-actions">
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                取消
              </Button>
            </Dialog.Close>
            <Button
              color="red"
              onClick={() => {
                if (removing) save(instances.filter((item) => item.id !== removing.id));
                if (removing?.id === selectedId) {
                  localStorage.removeItem("openfic.mobile.last-instance");
                  setSelectedId(null);
                }
                setRemoving(null);
              }}
            >
              移除
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
      <Dialog.Root
        open={warning !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setWarning(null);
        }}
      >
        <Dialog.Content
          maxWidth="420px"
          className="mobile-version-warning"
        >
          <Dialog.Title>版本不匹配</Dialog.Title>
          <Dialog.Description>
            App 版本 {appVersion}，实例版本 {warning?.version}。版本不一致可能导致功能异常，请更新
            App 或实例后再使用。
          </Dialog.Description>
          <label className="mobile-check-row">
            <input
              type="checkbox"
              checked={skipWarning}
              onChange={(event) => setSkipWarning(event.target.checked)}
            />
            该版本不再提醒
          </label>
          <div className="mobile-dialog-actions">
            <Button
              variant="soft"
              onClick={() => {
                setWarning(null);
                setTab("about");
              }}
            >
              检查更新
            </Button>
            <Button
              loading={activeId !== null}
              onClick={async () => {
                if (!warning) return;
                setActiveId(warning.instance.id);
                try {
                  await enter(warning.instance);
                  if (skipWarning)
                    localStorage.setItem(
                      `openfic.mobile.version-warning.${appVersion}.${warning.version}`,
                      "1",
                    );
                  setWarning(null);
                } catch (cause) {
                  toast.error(cause instanceof Error ? cause.message : "打开实例失败。", {
                    id: "mobile-instance-warning-error",
                  });
                } finally {
                  setActiveId(null);
                }
              }}
            >
              确认并进入
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
      <Toaster
        appearance="light"
        position="top-center"
        visibleToasts={1}
      />
    </Theme>
  );
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
