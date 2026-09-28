import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { VacuumControls } from "./vacuum-controls"
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let root: Root
let container: HTMLDivElement
const response = (commanded_on: boolean | null) =>
  new Response(JSON.stringify({ enabled: true, commanded_on }), { status: 200 })

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

it("does not command hardware on mount and sends explicit on/off actions", async () => {
  const fetcher = vi.fn().mockResolvedValue(response(null))
  vi.stubGlobal("fetch", fetcher)
  await act(async () => root.render(<VacuumControls connected />))
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0][1].method).toBeUndefined()
  const [on, off] = container.querySelectorAll("button")
  fetcher.mockResolvedValueOnce(response(true))
  await act(async () => on.click())
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ on: true })
  fetcher.mockResolvedValueOnce(response(false))
  await act(async () => off.click())
  expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual({ on: false })
})

it("disables commands while disconnected", async () => {
  const fetcher = vi.fn()
  vi.stubGlobal("fetch", fetcher)
  await act(async () => root.render(<VacuumControls connected={false} />))
  expect(fetcher).not.toHaveBeenCalled()
  expect([...container.querySelectorAll("button")].every((button) => button.disabled)).toBe(true)
})

it("keeps OFF available after a command failure and reports unknown state", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(response(false))
    .mockRejectedValueOnce(new Error("unplugged"))
  vi.stubGlobal("fetch", fetcher)
  await act(async () => root.render(<VacuumControls connected />))
  const [on, off] = container.querySelectorAll("button")
  await act(async () => on.click())
  expect(container.textContent).toContain("State unknown")
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("unplugged")
  expect(on.disabled).toBe(true)
  expect(off.disabled).toBe(false)
})

it("sends release to the vent-pulse endpoint", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(response(true))
    .mockResolvedValueOnce(response(false))
  vi.stubGlobal("fetch", fetcher)
  await act(async () => root.render(<VacuumControls connected />))
  const release = [...container.querySelectorAll("button")].find(
    (button) => button.textContent === "Release"
  )!
  await act(async () => release.click())
  expect(fetcher.mock.calls[1][0]).toBe("/api/vacuum/release")
  expect(fetcher.mock.calls[1][1].method).toBe("POST")
  expect(fetcher.mock.calls[1][1].body).toBeUndefined()
})
