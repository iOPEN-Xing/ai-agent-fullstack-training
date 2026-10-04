import { appendFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { createExecutionContext } from "../src/run-context.js";
import { DemoToolRuntime } from "../src/runtime.js";
import { makeTempWorkspace, PROJECT_ROOT } from "./support/harness.js";

const workspaces: string[] = [];
afterEach(async () => {
  await Promise.all(workspaces.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe("Runtime 的测试时间预算", () => {
  it.each([0, Infinity])("启动前拒绝无效预算 %s", (testTimeoutMs) => {
    expect(() => createExecutionContext({ testTimeoutMs })).toThrow("testTimeoutMs");
  });

  it("挂起测试会超时清理并留下失败证据，不再等待外部取消", async () => {
    const ws = await makeTempWorkspace("test-budget-");
    workspaces.push(ws.root);
    const marker = path.join(ws.root, "hang");
    await appendFile(path.join(ws.repoRoot, "tests/session-boundary.test.ts"), `
      import { existsSync } from "node:fs";
      import { setTimeout as pause } from "node:timers/promises";
      test("等待外部依赖", async () => { if (existsSync(${JSON.stringify(marker)})) await pause(30000); });
    `);
    await writeFile(marker, "hang");
    const context = createExecutionContext({
      projectRoot: ws.root, repoRoot: ws.repoRoot, runtimeRoot: PROJECT_ROOT,
      artifactRoot: ws.artifactRoot, testTimeoutMs: 1_000,
    });
    const runtime = new DemoToolRuntime();
    const controller = new AbortController();
    // 回归失败时也要清理本测试拥有的子进程，避免把挂起进程遗留在宿主。
    const fallback = setTimeout(() => controller.abort(), 3_000);
    try {
      const result = await runtime.invoke({ toolCallId: "budget", modelName: "run_test",
        args: { scope: "boundary" }, context, signal: controller.signal });
      expect(result.code).toBe("TEST_TIMEOUT");
      expect(result.evidence?.payload).toMatchObject({ passed: false, timedOut: true, cancelled: false });
      expect(runtime.hasUnfinishedTest("budget")).toBe(false);
    } finally {
      clearTimeout(fallback);
      controller.abort();
    }
  }, 10_000);
});
