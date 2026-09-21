import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ErrorView, HealthView } from './components'

describe('foundation states', () => {
  it('renders the healthy service state with its trace id', () => {
    render(
      <HealthView
        title="用户端"
        status="ok"
        detail="django · v2-p00"
        traceId="abc123"
        retry={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: '用户端' })).toBeInTheDocument()
    expect(screen.getByText('服务正常')).toBeInTheDocument()
    expect(screen.getByText('abc123')).toBeInTheDocument()
  })

  it('renders a navigable error state', () => {
    render(<ErrorView code="403" title="无权访问" message="当前会话不能访问此页面。" />)

    expect(screen.getByRole('heading', { name: '无权访问' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回状态页' })).toHaveAttribute('href', '/health')
  })
})
