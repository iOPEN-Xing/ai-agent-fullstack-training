import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

export interface TestProcessOptions {
  cwd: string;
  signal?: AbortSignal;
  timeoutMs?: number;
  maxBuffer?: number;
  terminateGraceMs?: number;
}

export interface TestProcessResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  signal: NodeJS.Signals | null;
  cancelled: boolean;
  timedOut: boolean;
}

/** Own the entire POSIX test process group, not only Node's test-runner parent. */
export async function executeTestProcess(
  command: string,
  args: readonly string[],
  options: TestProcessOptions,
): Promise<TestProcessResult> {
  if (options.signal?.aborted) {
    return { stdout: "", stderr: "", exitCode: null, signal: null, cancelled: true, timedOut: false };
  }
  const grouped = process.platform !== "win32";
  const child = spawn(command, [...args], {
    cwd: options.cwd,
    detached: grouped,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const grace = options.terminateGraceMs ?? 300;
  const limit = options.maxBuffer ?? 4 * 1024 * 1024;
  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  let bytes = 0;
  let cancelled = false;
  let timedOut = false;
  let closed = false;
  let terminating = false;
  let failure: Error | undefined;
  let escalation: NodeJS.Timeout | undefined;
  let deadline: NodeJS.Timeout | undefined;
  let cleanupTimeout: NodeJS.Timeout | undefined;
  let rejectCompletion: (error: Error) => void;

  const groupExists = (): boolean => {
    if (!child.pid) return false;
    if (!grouped) return !closed;
    try {
      process.kill(-child.pid, 0);
      return true;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ESRCH") return false;
      // macOS 回收只剩退出进程的组时，killpg(0) 也可能短暂返回 EPERM。
      // 此时仍视为未确认清理，继续轮询；持续 EPERM 会触发下方清理期限。
      // 不能在 exit 回调中抛出，也不能把权限不足误判成“进程已消失”。
      if (code !== "EPERM") failure ??= error instanceof Error ? error : new Error(String(error));
      return true;
    }
  };
  const send = (signal: NodeJS.Signals): void => {
    if (!child.pid) return;
    try {
      if (grouped) process.kill(-child.pid, signal);
      else child.kill(signal);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "ESRCH" && !(grouped && code === "EPERM")) {
        failure ??= error instanceof Error ? error : new Error(String(error));
      }
    }
  };
  const terminate = (): void => {
    if (terminating) return;
    terminating = true;
    send("SIGTERM");
    escalation = setTimeout(() => send("SIGKILL"), grace);
    // 信号被拒绝时，存活的后代还可能一直占着管道，close 永远不触发。
    // 终止等待也必须有期限；失败保留为失败，不声称已清理整个进程组。
    cleanupTimeout = setTimeout(() => {
      rejectCompletion(new Error(`TEST_PROCESS_CLEANUP_FAILED: process group ${child.pid} did not close`));
    }, grace + 5_000);
  };
  const abort = (): void => {
    cancelled = true;
    terminate();
  };
  const collect = (target: Buffer[], chunk: Buffer): void => {
    bytes += chunk.length;
    if (bytes <= limit) target.push(chunk);
    else {
      failure ??= new Error(`TEST_OUTPUT_LIMIT: test output exceeded ${limit} bytes`);
      terminate();
    }
  };
  child.stdout.on("data", (chunk: Buffer) => collect(stdout, chunk));
  child.stderr.on("data", (chunk: Buffer) => collect(stderr, chunk));
  // A normally exited parent can still leave children holding the output pipes.
  child.once("exit", () => {
    if (groupExists()) terminate();
  });
  const completion = new Promise<{ exitCode: number | null; signal: NodeJS.Signals | null }>((resolve, reject) => {
    rejectCompletion = reject;
    child.once("error", (error) => { failure ??= error; });
    child.once("close", (exitCode, signal) => {
      closed = true;
      resolve({ exitCode, signal });
    });
  });
  options.signal?.addEventListener("abort", abort, { once: true });
  if (options.signal?.aborted) abort();
  if (options.timeoutMs !== undefined) {
    deadline = setTimeout(() => {
      timedOut = true;
      terminate();
    }, options.timeoutMs);
  }

  try {
    const result = await completion;
    if (groupExists()) {
      terminate();
      const cleanupDeadline = Date.now() + grace + 5_000;
      while (groupExists()) {
        if (Date.now() >= cleanupDeadline) {
          throw new Error(`TEST_PROCESS_CLEANUP_FAILED: process group ${child.pid} still exists`);
        }
        await delay(20);
      }
    }
    if (failure) throw failure;
    return {
      ...result,
      stdout: Buffer.concat(stdout).toString("utf8"),
      stderr: Buffer.concat(stderr).toString("utf8"),
      cancelled,
      timedOut,
    };
  } finally {
    options.signal?.removeEventListener("abort", abort);
    if (deadline) clearTimeout(deadline);
    if (escalation) clearTimeout(escalation);
    if (cleanupTimeout) clearTimeout(cleanupTimeout);
  }
}
