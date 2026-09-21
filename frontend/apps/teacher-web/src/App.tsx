import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { getHealth } from '@edu/api-client'
import { login } from '@edu/auth-client'
import { systemKeys } from '@edu/query-keys'
import { AppErrorBoundary, ErrorView, HealthView, LoginForm, PortalLayout } from '@edu/ui'

const release = { version: import.meta.env.VITE_APP_VERSION ?? '0.1.0-p00', openapiRevision: import.meta.env.VITE_OPENAPI_REVISION ?? 'v2-p00', gitRevision: import.meta.env.VITE_GIT_REVISION ?? 'development', buildTime: import.meta.env.VITE_BUILD_TIME ?? 'development' }
function LoginPage() { const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const submit = async (email: string, password: string) => { setBusy(true); setError(''); try { await login({ email, password }) } catch { setError('登录请求未完成，请稍后重试。') } finally { setBusy(false) } }; return <LoginForm title="教师端" busy={busy} error={error} onSubmit={submit} /> }
function StatusPage() { const query = useQuery({ queryKey: systemKeys.health(), queryFn: ({ signal }) => getHealth(signal) }); return <HealthView title="教师端" status={query.isPending ? 'loading' : query.isError ? 'error' : 'ok'} detail={query.data ? `${query.data.data.service} · ${query.data.data.openapi_revision}` : query.isError ? '无法连接基础服务' : '正在连接基础服务'} traceId={query.data?.meta.trace_id} retry={() => void query.refetch()} /> }
export function App() { return <BrowserRouter><PortalLayout title="教师端" tone="teacher" release={release}><AppErrorBoundary><Routes><Route path="/" element={<Navigate to="/health" replace />} /><Route path="/login" element={<LoginPage />} /><Route path="/health" element={<StatusPage />} /><Route path="/403" element={<ErrorView code="403" title="无权访问" message="当前会话不能访问此页面。" />} /><Route path="/500" element={<ErrorView code="500" title="服务异常" message="请求未完成，请稍后重试。" />} /><Route path="*" element={<ErrorView code="404" title="页面不存在" message="请求的页面无法找到。" />} /></Routes></AppErrorBoundary></PortalLayout></BrowserRouter> }

