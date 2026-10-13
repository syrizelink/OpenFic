import { StrictMode, useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { Theme, Button, TextField, Dialog, IconButton } from "@radix-ui/themes";
import { ArrowRight, Check, Globe, Moon, Plus, Server, Sun, Trash2 } from "lucide-react";
import { normalizeInstanceUrl, readInstances, STORAGE_KEY, type Instance } from "./instances.mjs";
import { checkInstance, openInstance } from "./native";
import "../../frontend/src/styles/index.css";
import "./styles.css";

function App() {
  const [instances, setInstances] = useState<Instance[]>(() => readInstances(localStorage));
  const [dark, setDark] = useState(
    () =>
      localStorage.getItem("openfic.mobile.theme") === "dark" ||
      (!localStorage.getItem("openfic.mobile.theme") &&
        matchMedia("(prefers-color-scheme: dark)").matches),
  );
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [adding, setAdding] = useState(instances.length === 0);
  const [removing, setRemoving] = useState<Instance | null>(null);
  useEffect(() => {
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
    localStorage.setItem("openfic.mobile.theme", dark ? "dark" : "light");
  }, [dark]);

  function save(next: Instance[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setInstances(next);
  }
  async function add(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const normalized = normalizeInstanceUrl(url);
      if (instances.some((item) => item.url === normalized))
        throw new Error("这个实例已经添加，可以直接打开。");
      const result = await checkInstance(normalized);
      save([
        ...instances,
        {
          id: crypto.randomUUID(),
          name: name.trim() || new URL(normalized).hostname,
          url: normalized,
        },
      ]);
      setStatus(`连接成功 · OpenFic ${result.version}`);
      setUrl("");
      setName("");
      setAdding(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "连接失败，请检查地址和网络。");
    } finally {
      setBusy(false);
    }
  }
  async function open(instance: Instance) {
    setActiveId(instance.id);
    setError("");
    setStatus("");
    try {
      await checkInstance(instance.url);
      await openInstance(instance.url, instance.name);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "连接失败，请检查服务器是否在线。");
    } finally {
      setActiveId(null);
    }
  }
  return (
    <Theme
      appearance={dark ? "dark" : "light"}
      accentColor="gray"
      grayColor="gray"
      radius="medium"
      scaling="100%"
    >
      <main className="mobile-shell">
        <header className="mobile-header">
          <a className="mobile-brand" href="/" aria-label="OpenFic 首页">
            <img src="/openfic.svg" alt="" />
            OpenFic
          </a>
          <IconButton
            variant="ghost"
            size="3"
            aria-label={dark ? "切换浅色主题" : "切换深色主题"}
            onClick={() => setDark(!dark)}
          >
            {dark ? <Sun size={20} /> : <Moon size={20} />}
          </IconButton>
        </header>
        <div className="mobile-content">
          <div className="mobile-intro">
            <span className="mobile-eyebrow">
              <Globe size={14} />
              移动端
            </span>
            <h1>让创作随你而行</h1>
            <p>连接你的 OpenFic 实例，继续写下一个故事。</p>
          </div>
          {instances.length > 0 && (
            <section aria-labelledby="instances-title" className="mobile-instances">
              <div className="mobile-section-heading">
                <h2 id="instances-title">我的实例</h2>
                <span>{instances.length} 个</span>
              </div>
              <div className="mobile-instance-list">
                {instances.map((instance) => (
                  <article className="mobile-instance" key={instance.id}>
                    <Server size={20} className="mobile-instance-icon" />
                    <button
                      className="mobile-instance-open"
                      disabled={busy || activeId !== null}
                      onClick={() => void open(instance)}
                    >
                      <strong>{instance.name}</strong>
                      <span>{instance.url}</span>
                      <span className="mobile-instance-action">
                        {activeId === instance.id ? "正在连接…" : "打开实例"}
                        <ArrowRight size={14} />
                      </span>
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
          )}
          {!adding && (
            <Button
              className="mobile-add"
              size="3"
              variant="soft"
              disabled={activeId !== null}
              onClick={() => {
                setAdding(true);
                setError("");
              }}
            >
              <Plus size={17} />
              添加远程实例
            </Button>
          )}
          {adding && (
            <section className="mobile-connect" aria-labelledby="connect-title">
              <div className="mobile-section-heading">
                <h2 id="connect-title">连接远程实例</h2>
                <Server size={18} />
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
                  disabled={busy}
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
                  disabled={busy}
                />
                <p className="mobile-field-help">填写实例根地址，也支持局域网 IP 和端口。</p>
                {url.trim().toLowerCase().startsWith("http://") && (
                  <p className="mobile-http-note">HTTP 连接未加密，建议仅在可信局域网内使用。</p>
                )}
                <div className="mobile-form-actions">
                  <Button type="submit" size="3" loading={busy} disabled={activeId !== null}>
                    <Check size={17} />
                    验证并添加
                  </Button>
                  {instances.length > 0 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="3"
                      disabled={busy}
                      onClick={() => setAdding(false)}
                    >
                      取消
                    </Button>
                  )}
                </div>
              </form>
            </section>
          )}
          {error && (
            <div className="mobile-message mobile-error" role="alert">
              {error}
              <p>请确认服务器在线、地址正确，且证书有效。</p>
            </div>
          )}
          {status && (
            <p className="mobile-message" role="status">
              <Check size={16} />
              {status}
            </p>
          )}
          <footer className="mobile-footer">
            <p>创作数据保存在远程实例中。</p>
            <p>此 APP 不会安装或启动本地实例。</p>
          </footer>
        </div>
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
              <Button variant="soft" color="gray">
                取消
              </Button>
            </Dialog.Close>
            <Button
              color="red"
              onClick={() => {
                if (removing) save(instances.filter((item) => item.id !== removing.id));
                setRemoving(null);
              }}
            >
              移除
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
    </Theme>
  );
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
