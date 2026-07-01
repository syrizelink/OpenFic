interface BootPageProps {
  error: string | null;
}

export function BootPage({ error }: BootPageProps) {
  return (
    <section className="content-page content-page-centered">
      <section className="setup-card">
        <p className="eyebrow">OpenFic Desktop</p>
        <h1>正在准备 OpenFic</h1>
        <p className="description">正在检查现有配置与后端状态。</p>
        <div className="boot-state">
          <div className="boot-spinner" aria-hidden="true" />
          {error ? <p className="error">{error}</p> : null}
        </div>
      </section>
    </section>
  );
}
