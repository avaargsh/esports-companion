export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE"

export type HttpRequestOptions = {
  method?: HttpMethod
  data?: string | Record<string, unknown> | ArrayBuffer
  headers?: Record<string, string>
  auth?: boolean
}

export type HttpAuthProvider = {
  getHeaders: () => Promise<Record<string, string>>
  refresh: () => Promise<void>
}

export type HttpClientConfig = {
  baseUrl: string
  auth?: HttpAuthProvider
}

function joinUrl(baseUrl: string, path: string): string {
  const base = baseUrl.replace(/\/+$/, "")
  const suffix = path.startsWith("/") ? path : "/" + path
  return base + suffix
}

function errorMessage(data: unknown): string {
  if (typeof data === "object" && data && "detail" in data) {
    return String((data as { detail: unknown }).detail)
  }
  if (typeof data === "object" && data && "message" in data) {
    return String((data as { message: unknown }).message)
  }
  return "REQUEST_FAILED"
}

export function createHttpClient(config: HttpClientConfig) {
  async function execute<T>(
    path: string,
    options: HttpRequestOptions,
    retryAuth: boolean
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }

    if (options.auth) {
      if (!config.auth) throw new Error("AUTH_PROVIDER_REQUIRED")
      Object.assign(headers, await config.auth.getHeaders())
    }

    const response = await uni.request({
      url: joinUrl(config.baseUrl, path),
      method: options.method ?? "GET",
      data: options.data,
      header: headers
    })

    if (
      response.statusCode === 401 &&
      options.auth &&
      config.auth &&
      retryAuth
    ) {
      await config.auth.refresh()
      return execute<T>(path, options, false)
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw new Error(errorMessage(response.data))
    }

    return response.data as T
  }

  return {
    request<T>(
      path: string,
      options: HttpRequestOptions = {}
    ): Promise<T> {
      return execute<T>(path, options, true)
    }
  }
}
