import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { describe, expect, it, vi } from "vitest";
import { executeTestProcess } from "../src/test-process.js";

// POSIX signal delivery and reaping run outside Vitest's clock; wait for the
// child's ready file instead of assuming a startup delay or using fake timers.
async function waitForPids(file: string): Promise<number[]> {
  for (let attempt = 0; attempt < 250; attempt += 1) {
    try { return JSON.parse(await readFile(file, "utf8")) as number[]; } catch { await delay(20); }
  }
  throw new Error("Child process did not become ready");
}

function alive(pid: number): boolean {
  try { process.kill(pid, 0); return true; } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ESRCH") return false;
    throw error;
  }
}

describe.skipIf(process.platform === "win32")("owned test process group", () => {
  it("waits through a transient EPERM probe while an exited group is being reaped", async () => {
    const kill = process.kill.bind(process);
    let remaining = 3;
    const spy = vi.spyOn(process, "kill").mockImplementation((pid, signal) => {
      if (pid < 0 && signal === 0 && remaining-- > 0) {
        throw Object.assign(new Error("kill EPERM"), { code: "EPERM" });
      }
      return kill(pid, signal);
    });
    try {
      const result = await executeTestProcess(process.execPath, ["-e", "process.exit(0)"], {
        cwd: tmpdir(), terminateGraceMs: 20,
      });
      expect(result.exitCode).toBe(0);
      expect(remaining).toBeLessThan(0);
    } finally {
      spy.mockRestore();
    }
  });

  it("rejects cleanup when EPERM never permits confirming that the group is gone", async () => {
    const kill = process.kill.bind(process);
    const spy = vi.spyOn(process, "kill").mockImplementation((pid, signal) => {
      if (pid < 0 && signal === 0) {
        throw Object.assign(new Error("kill EPERM"), { code: "EPERM" });
      }
      return kill(pid, signal);
    });
    try {
      await expect(executeTestProcess(process.execPath, ["-e", "process.exit(0)"], {
        cwd: tmpdir(), terminateGraceMs: 20,
      })).rejects.toThrow("TEST_PROCESS_CLEANUP_FAILED");
    } finally {
      spy.mockRestore();
    }
  }, 8_000);

  it("bounds cancellation even when signals are denied and the child keeps its pipes open", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "test-denied-"));
    const pidFile = path.join(root, "pid.json");
    const kill = process.kill.bind(process);
    let pid: number | undefined;
    const spy = vi.spyOn(process, "kill").mockImplementation((target, signal) => {
      if (target < 0 && signal !== 0) {
        throw Object.assign(new Error("kill EPERM"), { code: "EPERM" });
      }
      return kill(target, signal);
    });
    const controller = new AbortController();
    const running = executeTestProcess(process.execPath, ["-e", `
      require('node:fs').writeFileSync(${JSON.stringify(pidFile)}, JSON.stringify([process.pid]));
      setInterval(() => {}, 1000);
    `], { cwd: root, signal: controller.signal, terminateGraceMs: 20 });
    const rejected = expect(running).rejects.toThrow("TEST_PROCESS_CLEANUP_FAILED");
    try {
      [pid] = await waitForPids(pidFile);
      controller.abort();
      await rejected;
    } finally {
      spy.mockRestore();
      if (pid && alive(pid)) kill(-pid, "SIGKILL");
      await running.catch(() => undefined);
      await rm(root, { recursive: true, force: true });
    }
  }, 8_000);

  it("waits for a TERM-resistant descendant to be killed and reaped before cancellation settles", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "test-process-"));
    const pidFile = path.join(root, "pids.json");
    const script = path.join(root, "parent.cjs");
    const leaf = `process.on('SIGTERM', () => {}); process.send('ready'); setInterval(() => {}, 1000);`;
    await writeFile(script, `
      const { spawn } = require('node:child_process');
      const { writeFileSync } = require('node:fs');
      const child = spawn(process.execPath, ['-e', ${JSON.stringify(leaf)}], { stdio: ['ignore', 'inherit', 'inherit', 'ipc'] });
      process.on('SIGTERM', () => {});
      child.once('message', () => writeFileSync(${JSON.stringify(pidFile)}, JSON.stringify([process.pid, child.pid])));
      setInterval(() => {}, 1000);
    `);
    const controller = new AbortController();
    const running = executeTestProcess(process.execPath, [script], {
      cwd: root, signal: controller.signal, terminateGraceMs: 60,
    });
    try {
      const pids = await waitForPids(pidFile);
      controller.abort();
      const result = await running;
      expect(result.cancelled).toBe(true);
      expect(result.exitCode).toBeNull();
      expect(result.signal).toBe("SIGKILL");
      expect(pids.map(alive)).toEqual([false, false]);
    } finally {
      controller.abort();
      await running.catch(() => undefined);
      await rm(root, { recursive: true, force: true });
    }
  }, 10_000);

  it("does not report a successful exit while a child remains alive after its parent exits", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "test-orphan-"));
    const pidFile = path.join(root, "pids.json");
    const leaf = `process.on('SIGTERM', () => {}); process.send('ready'); setInterval(() => {}, 1000);`;
    const script = `
      const { spawn } = require('node:child_process');
      const { writeFileSync } = require('node:fs');
      const child = spawn(process.execPath, ['-e', ${JSON.stringify(leaf)}], { stdio: ['ignore', 'inherit', 'inherit', 'ipc'] });
      child.once('message', () => { writeFileSync(${JSON.stringify(pidFile)}, JSON.stringify([child.pid])); process.exit(0); });
    `;
    try {
      const result = await executeTestProcess(process.execPath, ["-e", script], {
        cwd: root, terminateGraceMs: 60, timeoutMs: 5_000,
      });
      const [pid] = await waitForPids(pidFile);
      expect(result.exitCode).toBe(0);
      expect(alive(pid)).toBe(false);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  }, 10_000);
});
