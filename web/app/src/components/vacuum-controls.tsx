import { useEffect, useRef, useState } from "react"
import { apiUrl } from "@/lib/supervisor"
import { Button } from "@/components/ui/button"

interface VacuumStatus {
  enabled: boolean
  commanded_on: boolean | null
  error?: string | null
}

export function VacuumControls({ connected }: { connected: boolean }) {
  const [status, setStatus] = useState<VacuumStatus | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const generation = useRef(0)
  const commandVersion = useRef(0)

  useEffect(() => {
    const current = ++generation.current
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      if (!pending.current) {
        const version = commandVersion.current
        try {
          const response = await fetch(apiUrl("/api/vacuum"), { cache: "no-store" })
          if (!response.ok) throw new Error("Vacuum status unavailable")
          const value: VacuumStatus = await response.json()
          if (
            current === generation.current &&
            version === commandVersion.current &&
            !pending.current
          ) {
            setStatus(value)
            setError(value.error ?? "")
          }
        } catch (err) {
          if (
            current === generation.current &&
            version === commandVersion.current &&
            !pending.current
          ) {
            setStatus(null)
            setError(String(err))
          }
        }
      }
      if (current === generation.current) timer = setTimeout(poll, 1000)
    }
    if (connected) void poll()
    return () => {
      generation.current = current + 1
      clearTimeout(timer)
    }
  }, [connected])

  async function send(on: boolean | "release") {
    if (pending.current) return
    const current = generation.current
    commandVersion.current++
    pending.current = true
    setBusy(true)
    setError("")
    try {
      const response = await fetch(
        apiUrl(on === "release" ? "/api/vacuum/release" : "/api/vacuum"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: on === "release" ? undefined : JSON.stringify({ on }),
        }
      )
      const value = await response.json()
      if (!response.ok) throw new Error(value.detail ?? "Vacuum command failed")
      if (current === generation.current) setStatus(value)
    } catch (err) {
      if (current === generation.current) {
        setStatus(null)
        setError(String(err))
      }
    } finally {
      pending.current = false
      if (current === generation.current) setBusy(false)
    }
  }

  const available = connected && status?.enabled
  return (
    <aside
      className="rounded-xl border border-white/10 bg-white/[0.02] p-4"
      aria-label="Left-arm vacuum"
    >
      <h2 className="text-sm font-medium">Left-arm vacuum</h2>
      <p className="my-3 text-xs text-white/60" aria-live="polite">
        {!connected
          ? "Connect to Axol"
          : !status
            ? "State unknown"
            : !status.enabled
              ? "Vacuum not configured"
              : status.commanded_on === null
                ? "State unknown"
                : status.commanded_on
                  ? "Vacuum ON"
                  : "Vacuum OFF"}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={!available || busy} onClick={() => void send(true)}>
          Vacuum ON
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!connected || status?.enabled === false || busy}
          onClick={() => void send(false)}
        >
          Vacuum OFF
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!available || busy}
          onClick={() => void send("release")}
        >
          Release
        </Button>
      </div>
      <p className="mt-3 text-xs text-white/60">
        Release turns vacuum off and opens the vent for 0.4 seconds.
      </p>
      <p className="mt-3 text-xs text-white/40">Last commanded state; no pressure feedback.</p>
      {error && connected && (
        <p role="alert" className="mt-2 text-xs text-red-300">
          {error}
        </p>
      )}
    </aside>
  )
}
