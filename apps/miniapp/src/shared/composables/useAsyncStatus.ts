import { ref } from "vue"

export type AsyncStatus =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "error"

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message
    ? error.message
    : fallback
}

export function useAsyncStatus(initial: AsyncStatus = "idle") {
  const status = ref<AsyncStatus>(initial)
  const message = ref("")

  function start() {
    status.value = "loading"
    message.value = ""
  }

  function succeed(options: { empty?: boolean } = {}) {
    status.value = options.empty ? "empty" : "ready"
    message.value = ""
  }

  function fail(error: unknown, fallback: string) {
    status.value = "error"
    message.value = errorMessage(error, fallback)
  }

  return {
    status,
    message,
    start,
    succeed,
    fail
  }
}
