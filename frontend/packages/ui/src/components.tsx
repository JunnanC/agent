import { Component, type ErrorInfo, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { Activity, ArrowRight, BookOpen, LockKeyhole, Mail, Server } from 'lucide-react'

export type PortalTone = 'user' | 'teacher' | 'admin'

export interface ReleaseInfo {
  version: string
  openapiRevision: string
  gitRevision: string
  buildTime: string
}

export function PortalLayout({
  title,
  tone,
  release,
  children,
}: {
  title: string
  tone: PortalTone
  release: ReleaseInfo
  children: ReactNode
}) {
  return (
    <div className={`portal portal--${tone}`}>
      <header className="portal__header">
        <a className="brand" href="/health" aria-label={`${title}首页`}>
          <span className="brand__mark"><BookOpen size={19} aria-hidden="true" /></span>
          <span>
            <strong>教学云实验平台</strong>
            <small>{title}</small>
          </span>
        </a>
        <nav className="portal__nav" aria-label="主导航">
          <a href="/health">状态</a>
          <a href="/login">登录</a>
        </nav>
      </header>
      <main className="portal__main">{children}</main>
      <footer className="portal__footer">
        <span>v{release.version}</span>
        <span>API {release.openapiRevision}</span>
        <span title={release.buildTime}>{release.gitRevision}</span>
      </footer>
    </div>
  )
}

export function TextField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = props.id ?? props.name
  const Icon = props.type === 'password' ? LockKeyhole : Mail
  return (
    <label className="field" htmlFor={id}>
      <span>{label}</span>
      <span className="field__control">
        <Icon size={18} aria-hidden="true" />
        <input id={id} {...props} />
      </span>
    </label>
  )
}

export function LoginForm({
  title,
  busy,
  error,
  onSubmit,
}: {
  title: string
  busy: boolean
  error: string
  onSubmit: (email: string, password: string) => void
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    onSubmit(String(data.get('email') ?? ''), String(data.get('password') ?? ''))
  }
  return (
    <section className="auth-layout" aria-labelledby="login-title">
      <div className="auth-layout__context">
        <span className="eyebrow">EDU LAB CLOUD</span>
        <h1 id="login-title">{title}</h1>
        <p>使用平台账号继续。</p>
        <div className="context-signal"><Server size={18} /> 独立安全会话</div>
      </div>
      <form className="login-form" onSubmit={submit}>
        <h2>账号登录</h2>
        <TextField label="邮箱" name="email" type="email" autoComplete="username" required />
        <TextField label="密码" name="password" type="password" autoComplete="current-password" required />
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="primary-button" type="submit" disabled={busy}>
          <span>{busy ? '正在登录' : '登录'}</span>
          <ArrowRight size={18} aria-hidden="true" />
        </button>
      </form>
    </section>
  )
}

export function HealthView({
  title,
  status,
  detail,
  traceId,
  retry,
}: {
  title: string
  status: 'loading' | 'ok' | 'error'
  detail: string
  traceId?: string
  retry: () => void
}) {
  return (
    <section className="status-page" aria-labelledby="status-title">
      <div>
        <span className="eyebrow">SYSTEM STATUS</span>
        <h1 id="status-title">{title}</h1>
        <p className="status-page__lead">基础服务状态</p>
      </div>
      <div className="status-row">
        <span className={`status-dot status-dot--${status}`} aria-hidden="true" />
        <div>
          <strong>{status === 'loading' ? '正在检查' : status === 'ok' ? '服务正常' : '服务异常'}</strong>
          <p>{detail}</p>
        </div>
        <Activity size={22} aria-hidden="true" />
      </div>
      {traceId ? <p className="trace">Trace ID <code>{traceId}</code></p> : null}
      {status === 'error' ? <button className="secondary-button" onClick={retry}>重新检查</button> : null}
    </section>
  )
}

export function ErrorView({ code, title, message }: { code: string; title: string; message: string }) {
  return (
    <section className="error-page">
      <span className="error-page__code">{code}</span>
      <h1>{title}</h1>
      <p>{message}</p>
      <a className="secondary-button" href="/health">返回状态页</a>
    </section>
  )
}

export class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Application render failed', { error: error.message, componentStack: info.componentStack })
  }

  render() {
    if (this.state.failed) {
      return <ErrorView code="500" title="页面加载失败" message="请求未完成，请稍后重试。" />
    }
    return this.props.children
  }
}
