export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public raw_report?: string,
  ) {
    super(message)
  }
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, body === undefined ? undefined : JSON.stringify(body))
}
export async function request<T>(
  path: string,
  body?: string | FormData,
): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers:
      body === undefined
        ? {}
        : {
            'X-VectorNext-Client': '1',
            ...(typeof body === 'string'
              ? { 'Content-Type': 'application/json' }
              : {}),
          },
    body,
  })
  const value = await response.json()
  if (!response.ok && path !== '/readyz')
    throw new ApiError(
      value.error?.code ?? 'http_error',
      value.error?.message ?? `Request failed (${response.status})`,
      value.error?.raw_report,
    )
  return value
}
export const delay = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms))
